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
import json

import bootstrap
import clean_room
import solr
import constants
import utils


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

    # checkout project code
    i('Checking out project source code from %s in %s revision: %s' % (config['repo'], checkout_dir, revision))
    checkout = solr.LuceneSolrCheckout(config['repo'], checkout_dir, revision)
    checkout.checkout()

    # find the sha for the given test_date and check it out
    start_date = test_date.replace(hour=0, minute=0, second=0)
    end_date = test_date.replace(hour=23, minute=59, second=59)
    shas = generate_shas(start_date, end_date, checkout)
    revision = shas[-1]
    i('Generated shas:  %s' % shas)
    i('Using revision %s for test_date %s' % (revision, test_date_str))

    checkout = solr.LuceneSolrCheckout(config['repo'], checkout_dir, revision)
    checkout.checkout()
    git_sha, commit_date = checkout.get_git_rev()
    i('Checked out lucene/solr artifacts from GIT SHA %s with date %s' % (git_sha, commit_date))

    clean_room_data, detention_data = bootstrap.load_validate_room_data(config, output_dir, revision)
    clean = clean_room.Room('clean-room', clean_room_data)
    detention = clean_room.Room('detention', detention_data)

    include = config['include'].split('|') if 'include' in config else ['*.java']
    exclude = config['exclude'].split('|') if 'exclude' in config else []

    i('Reading test names from test directories matching: src/test')
    run_tests = bootstrap.gather_interesting_tests(checkout_dir, exclude, include)

    num_tests = 0
    for k in run_tests:
        num_tests += len(run_tests[k])
    i('Found %d interesting tests in %d modules' % (num_tests, len(run_tests)))
    logger.debug('Test names: %s' % run_tests)

    commit_date_str = commit_date.strftime('%Y-%m-%d %H-%M-%S')
    if clean.num_tests() == 0 and detention.num_tests() == 0:
        w('no clean room data detected, promoting all interesting tests to the clean room')
        for k in run_tests:
            for t in run_tests[k]:
                i('test %s entering clean room on %s on git sha %s' % (t, commit_date_str, git_sha))
                clean.enter(t, commit_date_str, git_sha)
    else:
        # find new tests that have been added since the last run
        for m in run_tests:
            for t in run_tests[m]:
                if not clean.has(t) and not detention.has(t):
                    i('Promoting new test %s to the clean room' % t)
                    i('test %s entering clean room on %s on git sha %s' % (t, commit_date_str, git_sha))
                    clean.enter(t, commit_date_str, git_sha)

    with gzip.open(fail_report_path, 'rb') as f:
        jenkins_jobs = config['jenkins_jobs']

        for line in f:
            test_name, method_name, jenkins = line.strip().split(',')
            test_name = str(test_name)
            test_name = test_name.split('.')[-1]
            for j in jenkins_jobs:
                if jenkins.count(j) > 0:
                    if clean.exit(test_name):
                        i('test %s exited clean room on %s on git sha %s' % (test_name, commit_date_str, git_sha))
                    i('test %s entering detention on %s on git sha %s' % (test_name, commit_date_str, git_sha))
                    detention.enter(test_name, commit_date_str, git_sha)

    # a test that hasn't failed in N days, should be promoted to clean room
    i('Finding tests that have not failed for the past %d days since %s'
      % (config['promote_if_not_failed_days'], test_date_str))
    detained = detention.get_data()['tests']
    promote = []
    for test in detained:
        # {'name': name, 'entry_date': date_s, 'git_sha' : git_sha}
        data = detained[test]
        entry_date = datetime.datetime.strptime(data['entry_date'], '%Y-%m-%d %H-%M-%S')
        if entry_date < test_date - datetime.timedelta(days=config['promote_if_not_failed_days']):
            promote.append(data)
            i('%s last failed at %s' % (data['name'], data['entry_date']))
    for p in promote:
        i('test %s exiting detention on %s on git sha %s' % (p['name'], commit_date_str, git_sha))
        detention.exit(p['name'])
        clean.enter(p['name'], commit_date_str, git_sha)
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

    report_path = os.path.join(reports_dir, test_date.strftime('%Y.%m.%d.%H.%M.%S'))
    if not os.path.exists(report_path):
        os.makedirs(report_path)
    report_file = os.path.join(report_path, 'report.json')
    report = {'time_stamp': config['time_stamp'],
              'num_clean': clean.num_tests(),
              'num_detention': detention.num_tests(),
              'clean': clean.get_data(),
              'detention': detention.get_data(),
              # promotions are the tests that exit detention and enter clean room
              # we cannot use clean.get_entered to count promotions because that also includes
              # new tests that we haven't seen previously
              'num_promotions': len(detention.get_exited()),
              # demotions are the tests that exit clean room and enter detention
              # we cannot use detention.get_entered here because that may count
              # failures on tests that were already in detention
              'num_demotions': len(clean.get_exited()),
              'promotions': detention.get_exited(),
              'demotions': clean.get_exited(),
              'test_date' : test_date_str}
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=8, sort_keys=True)
    i('Report written to: %s' % report_file)
    run_log_dir = '%s/%s' % (output_dir, config['time_stamp'])
    run_log_file = '%s/output.txt' % run_log_dir
    i('Logs written to: %s' % run_log_file)
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
