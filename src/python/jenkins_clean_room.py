#!/bin/python

import sys
import datetime
import os
import logging
import shutil

import bootstrap
import clean_room
import solr
import constants
import utils


def generate_shas(start_date, end_date, delta_date_time, checkout):
    x = os.getcwd()
    try:
        os.chdir(checkout.checkout_dir)
        shas = []
        st = start_date
        while st < end_date:
            cmd = [constants.GIT_EXE,
                   'rev-list', '-n', '1', '--before="%s"' % st.strftime('%Y-%m-%d %H:%M:%S'), 'master']
            sha, _ = utils.run_get_output(cmd)
            sha = sha.strip()
            if sha not in shas:
                shas.append(sha)
            st = st + delta_date_time
        print('Generated %d SHAs to backtest' % len(shas))
    finally:
        os.chdir(x)


def do_work(test_date, config):
    test_date_str = test_date.strftime('%Y-%m-%d %H-%M-%S')

    fail_report_path = None
    if '-fail-report-path' in sys.argv:
        index = sys.argv.index('-fail-report-path')
        fail_report_path = sys.argv[index + 1]

    if fail_report_path is None or not os.path.exists(fail_report_path):
        print('Report at %s does not exist' % fail_report_path)
        exit(0)

    checkout_dir = config['checkout']
    output_dir = config['output']
    reports_dir = config['report']

    logger = logging.getLogger()
    i = logger.info
    w = logger.warn
    e = logger.error

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

    clean_room_data, detention_data = bootstrap.load_validate_room_data(config, output_dir, revision)
    clean = clean_room.Room('clean-room', clean_room_data)
    detention = clean_room.Room('detention', detention_data)

    include = config['include'].split('|') if 'include' in config else ['*']
    exclude = config['exclude'].split('|') if 'exclude' in config else []

    # checkout project code
    i('Checking out project source code from %s in %s revision: %s' % (config['repo'], checkout_dir, revision))
    checkout = solr.LuceneSolrCheckout(config['repo'], checkout_dir, revision)
    checkout.checkout()

    # find the sha for the given test_date and check it out
    start_date = test_date.replace(hour=0, minute=0, second=0)
    end_date = test_date.replace(hour=11, minute=59, second=59)
    delta_date_time = datetime.timedelta(hours=1)
    shas = generate_shas(start_date, end_date, delta_date_time, checkout)
    revision = shas[-1]
    print('Generated shas:  %s' % shas)
    print('Using revision %s for test_date %s' % (revision, test_date_str))

    checkout = solr.LuceneSolrCheckout(config['repo'], checkout_dir, revision)
    checkout.checkout()
    git_sha, commit_date = checkout.get_git_rev()
    i('Checked out lucene/solr artifacts from GIT SHA %s with date %s' % (git_sha, commit_date))

    i('Reading test names from test directories matching: src/test')
    run_tests = bootstrap.gather_interesting_tests(checkout_dir, exclude, include)

    num_tests = 0
    for k in run_tests:
        num_tests += len(run_tests[k])
    i('Found %d interesting tests in %d modules. Test names: %s' % (num_tests, len(run_tests), run_tests))

    if clean.num_tests() == 0:
        w('no clean room data detected, promoting all interesting tests to the clean room')
        for k in run_tests:
            for t in run_tests[k]:
                i('test %s entering clean room on %s on git sha %s' % (t, test_date_str, git_sha))
                clean.enter(t, test_date_str, git_sha)

    with open(fail_report_path, 'r') as f:
        jenkins_runs = ['sarowe/Lucene-Solr-tests-master', 'thetaphi/Lucene-Solr-master-Linux']
        # 'sarowe/Lucene-Solr-Nightly-master', 'thetaphi/Lucene-Solr-master-MacOSX',
        # 'thetaphi/Lucene-Solr-master-Windows'

        for line in f:
            test_name, method_name, jenkins = line.strip().split(',')
            test_name = str(test_name)
            test_name = test_name.split('.')[-1]
            for j in jenkins_runs:
                if jenkins.count(j) > 0:
                    if clean.exit(test_name):
                        i('test %s exited clean room on %s on git sha %s' % (test_name, test_date_str, git_sha))
                    i('test %s entering detention on %s on git sha %s' % (test_name, test_date_str, git_sha))
                    detention.enter(test_name, test_date_str, git_sha)

    # to be extra safe, assert that no test clean room is also in detention and vice-versa
    for t in clean.get_tests():
        print('checking %s' % t)
        if detention.has(t):
            print('test %s is in both clean room and detention. This isn\'t supposed to happen' % t)
            exit(1)
    for t in detention.get_tests():
        if clean.has(t):
            print('test %s is in both clean room and detention. This isn\'t supposed to happen' % t)
            exit(1)

    bootstrap.save_detention_data(config['name'], detention.get_data(), '%s/detention_data.json' % output_dir)
    bootstrap.save_clean_room_data(config['name'], clean.get_data(), '%s/clean_room_data.json' % output_dir)


def main():
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)

    # in the format 2017-11-21
    test_date = None
    if '-test-date' in sys.argv:
        index = sys.argv.index('-test-date')
        test_date = sys.argv[index + 1]
        test_date = datetime.datetime.strptime(test_date, '%Y-%m-%d')

    config = bootstrap.get_config()

    # setup output directory
    output_dir = config['output']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    bootstrap.setup_logging(output_dir, time_stamp)
    do_work(test_date, config)


if __name__ == '__main__':
    main()