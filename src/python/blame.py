#!/bin/python

# Copyright 2018 Shalin Shekhar Mangar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import sys
import os
import logging
import time
import re
import json

import bootstrap
import solr
import utils
import constants


# # first bad commit: [a2d927667418d17a1f5f31a193092d5b04a4219e] LUCENE-8335: Enforce soft-deletes field up-front.
reBadCommit = re.compile(r'^# first bad commit: \[(.*)\] (.*)$', re.MULTILINE)


def blame(config, time_stamp, test_date, test_name, good_sha, bad_sha, new_test=False):
    i = logging.info

    i('Checking out code')
    checkout = solr.LuceneSolrCheckout(config['repo'], config['checkout'])
    checkout.checkout()

    # TODO run the bisect script against the bad_sha first and assert that it
    # TODO fails otherwise the bisection is not likely to be useful

    x = os.getcwd()
    try:
        os.chdir(config['checkout'])
        try:
            if new_test:
                # no need to bisect, we can find the commit that introduced the test
                # git log --diff-filter=A -- */AutoScalingHandlerTest.java
                cmd = [constants.GIT_EXE, 'log', '--diff-filter=A', '--', '*/%s.java' % test_name]
                i('Running command: %s' % cmd)
                output, ret = utils.run_get_output(cmd)
                i(output)
                exit(0)

            # git bisect start bad good
            cmd = [constants.GIT_EXE, 'bisect', 'start', bad_sha, good_sha]
            i('Running command: %s' % cmd)
            output, ret = utils.run_get_output(cmd)
            i(output)

            index = sys.argv.index('-config')
            config_path = sys.argv[index + 1]

            # git bisect run sh -c "ant compile-test || exit 125; python src/python/bisect.py -config %s -test %s"
            cmd = [constants.GIT_EXE, 'bisect', 'run', 'sh', '-c',
                   'ant clean clean-jars compile-test || exit 125; python %s/src/python/bisect.py -config %s/%s -test %s'
                   % (x, x, config_path, test_name)]
            i('Running command: %s' % cmd)
            start_time = time.time()
            output, ret = utils.run_get_output(cmd)
            i('Time taken: %d seconds' % (time.time() - start_time))
            i(output)

            # git bisect log
            cmd = [constants.GIT_EXE, 'bisect', 'log']
            i('Running command: %s' % cmd)
            output, ret = utils.run_get_output(cmd)
            i(output)
            result = reBadCommit.search(output)
            if result is not None:
                print('Found bad commit SHA: %s commit message: %s' % (result.group(1), result.group(2)))
            else:
                print('Bisect unsuccessful!')
        finally:
            # git bisect reset
            cmd = [constants.GIT_EXE, 'bisect', 'reset']
            i('Running command: %s' % cmd)
            output, ret = utils.run_get_output(cmd)
            i(output)
    finally:
        os.chdir(x)


def find_tests(config, test_date):
    i = logging.info

    i('Checking out code')
    checkout = solr.LuceneSolrCheckout(config['repo'], config['checkout'])
    checkout.checkout()

    reports_dir = config['report']
    if not os.path.exists(reports_dir):
        return []

    test_date_str = test_date.strftime('%Y.%m.%d.%H.%M.%S')

    report = None
    with open(os.path.join(os.path.join(reports_dir, test_date_str), 'report.json')) as f:
        report = json.load(f)
    test_data = report['detention']['tests']
    new_tests = report['new_tests']
    result = []
    for t in test_data:
        test = test_data[t]
        module = test['module'] if 'module' in test and test['module'] is not None else ''
        idx = module.find(config['checkout'])
        if idx != -1:
            module = module[idx + len(config['checkout']) + 1:]
        reproducible = str(test['extra_info']['reproducible']) if 'extra_info' in test and 'reproducible' in test[
            'extra_info'] else 'Unknown'
        good_sha = test['extra_info']['good_sha'] if 'extra_info' in test and 'good_sha' in test['extra_info'] and \
                                                     test['extra_info']['good_sha'] is not None else 'Unknown'
        if reproducible == 'True' and good_sha != 'Unknown':
            result.append((test['name'], module, good_sha, test['git_sha'], test['name'] in new_tests))
    return result


def main():
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)

    test_name = None
    good_sha = None
    bad_sha = None
    if '-test' in sys.argv:
        index = sys.argv.index('-test')
        test_name = sys.argv[index + 1]
        if '-good-sha' in sys.argv:
            index = sys.argv.index('-good-sha')
            good_sha = sys.argv[index + 1]
        else:
            print('No -good-sha specified for test %s, exiting' % test_name)
            exit(1)
        if '-bad-sha' in sys.argv:
            index = sys.argv.index('-bad-sha')
            bad_sha = sys.argv[index + 1]
        else:
            print('No -bad-sha specified for test %s, exiting' % test_name)
            exit(1)

    test_date = None
    if '-test-date' in sys.argv:
        index = sys.argv.index('-test-date')
        test_date = sys.argv[index + 1]
        test_date = datetime.datetime.strptime(test_date, '%Y.%m.%d.%H.%M.%S')
    else:
        # set to now - 1DAY
        # see related comment in jenkins_clean_room.py
        test_date = start - datetime.timedelta(days=1)

    # overridable so we log to the same log file?
    if '-timestamp' in sys.argv:
        index = sys.argv.index('-timestamp')
        time_stamp = sys.argv[index + 1]

    config = bootstrap.get_config()

    # setup output directory
    output_dir = config['output']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    level = logging.INFO
    if '-debug' in sys.argv:
        level = logging.DEBUG

    new_test = False
    if '-new-test' in sys.argv:
        new_test = True

    config['time_stamp'] = time_stamp
    bootstrap.setup_logging(output_dir, time_stamp, level)

    tests = [(test_name, None, good_sha, bad_sha, new_test)] if test_name is not None else find_tests(config, test_date)
    for test in tests:
        t, m, g, b, nt = test
        print('running blame for test %s in module %s good_sha %s bad_sha %s is_new: %s' % (t, m, g, b, str(nt)))
        # blame(config, time_stamp, test_date, t, g, b, nt)


if __name__ == '__main__':
    main()
