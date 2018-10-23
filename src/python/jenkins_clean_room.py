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

import sys
import datetime
import os
import logging
import shutil
import requests
import gzip

import bootstrap
import clean_room
import solr
import constants
import utils
import room_filter
from bootstrap import get_module_for_test


def generate_shas(start_date, end_date, checkout):
    x = os.getcwd()
    try:
        os.chdir(checkout.checkout_dir)
        shas = []
        cmd = [constants.GIT_EXE,
               'rev-list',
               '--after="%s"' % start_date.strftime('%Y-%m-%d %H:%M:%S'),
               '--before="%s"' % end_date.strftime('%Y-%m-%d %H:%M:%S'),
               'master']
        output, _ = utils.run_get_output(cmd)
        for line in output.split('\n'):
            logging.debug(line)
            if len(line.strip()) > 0 and line.strip() not in shas:
                shas.append(line.strip())
        return shas
    finally:
        os.chdir(x)


def do_work(test_date, config):
    logger = logging.getLogger()
    i = logger.info
    w = logger.warn
    e = logger.error

    test_date_str = test_date.strftime('%Y-%m-%d %H-%M-%S')

    fail_report_path = None
    if '-fail-report-path' in sys.argv:
        index = sys.argv.index('-fail-report-path')
        fail_report_path = sys.argv[index + 1]
    else:
        # download the jenkins failure report if not exists
        jenkins_archive = os.path.join(config['output'], 'jenkins-archive')
        if not os.path.exists(jenkins_archive):
            os.makedirs(jenkins_archive)
        fail_report_path = os.path.join(jenkins_archive, '%s.method-failures.csv.gz' % test_date.strftime('%Y-%m-%d'))
        if not os.path.exists(fail_report_path):
            # http://fucit.org/solr-jenkins-reports/reports/archive/daily/2017-11-21.method-failures.csv.gz
            failure_report_url = '%s/%s.method-failures.csv.gz' \
                                 % (config['failure_report_url'], test_date.strftime('%Y-%m-%d'))
            r = requests.get(failure_report_url)
            with open(fail_report_path, 'wb') as f:
                f.write(r.content)

    if fail_report_path is None or not os.path.exists(fail_report_path):
        e('Report at %s does not exist' % fail_report_path)
        exit(0)

    checkout_dir = config['checkout']
    output_dir = config['output']
    reports_dir = config['report']

    if '-clean-build' in sys.argv:
        if os.path.exists(checkout_dir):
            w('Deleting checkout directory: %s' % checkout_dir)
            shutil.rmtree(checkout_dir)

    if not os.path.exists(reports_dir):
        i('Make directory: %s' % reports_dir)
        os.makedirs(reports_dir)

    revision = 'LATEST'
    if '-revision' in sys.argv:
        index = sys.argv.index('-revision')
        revision = sys.argv[index + 1]

    run_filters = True
    if '-skip-filters' in sys.argv:
        run_filters = False

    # checkout project code
    i('Checking out project source code from %s in %s revision: %s' % (config['repo'], checkout_dir, revision))
    checkout = solr.LuceneSolrCheckout(config['repo'], checkout_dir, revision)
    checkout.checkout()

    # find the sha for the given test_date and check it out
    start_date = test_date.replace(hour=0, minute=0, second=0)
    end_date = test_date.replace(hour=23, minute=59, second=59)
    i('Finding commits between %s and %s' % (start_date.strftime('%Y-%m-%d %H:%M:%S'),
                                             end_date.strftime('%Y-%m-%d %H:%M:%S')))
    shas = generate_shas(start_date, end_date, checkout)
    i('Found SHAs: %s' % ','.join(shas))
    if len(shas) == 0:
        i('No commits found on test_date %s, skipping.' % test_date_str)
        return
    revision = shas[-1]
    i('Generated shas:  %s' % shas)
    i('Using revision %s for test_date %s' % (revision, test_date_str))

    checkout = solr.LuceneSolrCheckout(config['repo'], checkout_dir, revision)
    checkout.checkout()
    git_sha, commit_date = checkout.get_git_rev()
    i('Checked out lucene/solr artifacts from GIT SHA %s with date %s' % (git_sha, commit_date))

    include = config['include'].split('|') if 'include' in config else ['*.java']
    exclude = config['exclude'].split('|') if 'exclude' in config else []

    i('Reading test names from test directories matching: src/test')
    run_tests = bootstrap.gather_interesting_tests(checkout_dir, exclude, include)

    clean_room_data, detention_data = bootstrap.load_validate_room_data(config, output_dir, revision)

    for test in clean_room_data['tests']:
        if 'module' not in clean_room_data['tests'][test]:
            clean_room_data['tests'][test]['module'] = get_module_for_test(run_tests, test)
    for test in detention_data['tests']:
        if 'module' not in detention_data['tests'][test]:
            detention_data['tests'][test]['module'] = get_module_for_test(run_tests, test)

    clean = clean_room.Room('clean-room', clean_room_data)
    detention = clean_room.Room('detention', detention_data)

    # Building filters
    filters = []
    for f in config['filters']:
        ff = room_filter.Filter(f['name'], f['test'], tests_jvms=config['tests_jvms'])
        filters.append(ff)

    num_tests = 0
    for k in run_tests:
        num_tests += len(run_tests[k])
    i('Found %d interesting tests in %d modules' % (num_tests, len(run_tests)))
    logger.debug('Test names: %s' % run_tests)

    commit_date_str = commit_date.strftime('%Y-%m-%d %H-%M-%S')
    # keep track of newly added (module, test) tuples
    new_tests = []
    if clean.num_tests() == 0 and detention.num_tests() == 0:
        w('no clean room data detected, promoting all interesting tests to the clean room')
        for k in run_tests:
            for t in run_tests[k]:
                i('test %s in module %s entering clean room on %s on git sha %s' % (t, k, commit_date_str, git_sha))
                clean.enter(t, k, commit_date_str, git_sha)
    else:
        # find new tests that have been added since the last run
        for m in run_tests:
            for t in run_tests[m]:
                if not clean.has(t) and not detention.has(t):
                    i('Promoting new test %s to the clean room' % t)
                    i('test %s in module %s entering clean room on %s on git sha %s' % (t, m, commit_date_str, git_sha))
                    clean.enter(t, m, commit_date_str, git_sha)
                    new_tests.append((m, t))

    with gzip.open(fail_report_path, 'rb') as f:
        jenkins_jobs = config['jenkins_jobs']
        uniq_failed_tests = set()
        for line in f:
            test_name, method_name, jenkins = line.strip().split(',')
            test_name = str(test_name)
            test_name = test_name.split('.')[-1]
            for j in jenkins_jobs:
                if jenkins.count(j) > 0:
                    if clean.exit(test_name):
                        i('test %s exited clean room on %s on git sha %s' % (test_name, commit_date_str, git_sha))
                    i('test %s entering detention on %s on git sha %s' % (test_name, commit_date_str, git_sha))
                    test_module = get_module_for_test(run_tests, test_name)
                    if test_name not in uniq_failed_tests:
                        reproducible = False
                        if run_filters:
                            i('test %s set to enter detention, running filters to see '
                              'if we can reproduce the failure seen on jenkins' % test_name)
                            for ff in filters:
                                filter_result = ff.filter(test_module, test_name)
                                if filter_result != utils.GOOD_STATUS:
                                    reproducible = True
                                    break
                        i('test %s failure is %s' % (test_name, 'reproducible' if reproducible else 'not reproducible'))
                        uniq_failed_tests.add(test_name)
                        detention.enter(test_name, test_module, commit_date_str, git_sha,
                                        extra_info={'reproducible': reproducible})

    # a test that hasn't failed in N days, should be promoted to clean room
    i('Finding tests that have not failed for the past %d days since %s'
      % (config['promote_if_not_failed_days'], test_date_str))
    detained = detention.get_data()['tests']
    promote = []
    for test in detained:
        # {'name': name, 'entry_date': date_s, 'git_sha' : git_sha, 'module': test_module}
        data = detained[test]
        entry_date = datetime.datetime.strptime(data['entry_date'], '%Y-%m-%d %H-%M-%S')
        if entry_date < test_date - datetime.timedelta(days=config['promote_if_not_failed_days']):
            promote.append(data)
            i('%s last failed at %s' % (data['name'], data['entry_date']))

    for p in promote:
        promotable = True
        if run_filters:
            i('test %s set to exit detention, running filters to see if it is worthy' % p['name'])
            for f in filters:
                if not f.filter(p['module'], p['name']) == utils.GOOD_STATUS:
                    promotable = False
                    break
        if promotable:
            i('test %s exiting detention on %s on git sha %s' % (p['name'], commit_date_str, git_sha))
            detention.exit(p['name'])
            clean.enter(p['name'], p['module'], commit_date_str, git_sha)
            i('test %s entering clean room on %s on git sha %s' % (p['name'], commit_date_str, git_sha))

    # to be extra safe, assert that no test clean room is also in detention and vice-versa
    for t in clean.get_tests():
        logger.debug('checking %s' % t)
        if detention.has(t):
            e('test %s is in both clean room and detention. This isn\'t supposed to happen' % t)
            exit(1)
    for t in detention.get_tests():
        if clean.has(t):
            e('test %s is in both clean room and detention. This isn\'t supposed to happen' % t)
            exit(1)

    bootstrap.save_detention_data(config['name'], detention.get_data(), '%s/detention_data.json' % output_dir)
    bootstrap.save_clean_room_data(config['name'], clean.get_data(), '%s/clean_room_data.json' % output_dir)

    report_file = bootstrap.write_report(config, clean, detention, test_date, [x[1] for x in new_tests])
    i('Report written to: %s' % report_file)
    run_log_dir = '%s/%s' % (output_dir, config['time_stamp'])
    run_log_file = '%s/output.txt' % run_log_dir
    i('Logs written to: %s' % run_log_file)


def main():
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)

    # in the format 2017-11-21
    test_date = None
    if '-test-date' in sys.argv:
        index = sys.argv.index('-test-date')
        test_date = sys.argv[index + 1]
        test_date = datetime.datetime.strptime(test_date, '%Y.%m.%d.%H.%M.%S')
    else:
        # set to now
        test_date = start

    config = bootstrap.get_config()

    # setup output directory
    output_dir = config['output']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    level = logging.INFO
    if '-debug' in sys.argv:
        level = logging.DEBUG

    config['time_stamp'] = time_stamp
    bootstrap.setup_logging(output_dir, time_stamp, level)
    do_work(test_date, config)


if __name__ == '__main__':
    main()
