#!/bin/python

import sys
import datetime
import os
import logging
import shutil

import bootstrap


def do_work(test_date, config):
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

    include = config['include'].split('|') if config['include'] is not None else ['*']
    exclude = config['exclude'].split('|') if config['exclude'] is not None else []

    i('Reading test names from test directories matching: src/test')
    run_tests = bootstrap.gather_interesting_tests(checkout_dir, exclude, include)

    num_tests = 0
    for k in run_tests:
        num_tests += len(run_tests[k])
    i('Found %d interesting tests in %d modules. Test names: %s' % (num_tests, len(run_tests), run_tests))


def main():
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)

    # in the format 2017-11-21
    test_date = None
    if '-test-date' in sys.argv:
        index = sys.argv.index('-test-date')
        test_date = sys.argv[index + 1]

    config = bootstrap.get_config()

    # setup output directory
    output_dir = config['output']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    bootstrap.setup_logging(output_dir, time_stamp)
    do_work(test_date, config)


if __name__ == '__main__':
    main()