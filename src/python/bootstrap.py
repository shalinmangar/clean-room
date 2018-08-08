#!/bin/python


import sys
import json
import os
import shutil
import datetime
import logging
import fnmatch

import solr


def load_overrides(config, cmd_params):
    """Overrides configuration parameters (at the first level only) with the given cmd_params
    :rtype: dict
    :param config: a python dict containing the configuration parameters
    :param cmd_params: a python list containing the overriding key, values i.e. value follows key in the list
    :return: a python dict containing the overridden configuration parameters
    """
    if cmd_params is None or len(cmd_params) == 0:
        return config
    modified = {}
    for k in config:
        modified[k] = config[k]
    for p in cmd_params:
        p = str(p)
        if p.startswith('-'):
            index = cmd_params.index(p)
            k,v = p[1:], cmd_params[index + 1]
            if k in modified:
                print('Overriding configuration key: %s value: %s with provided value: %s' % (k, modified[k], v))
                modified[k] = v
    return modified


def load_config(config_path):
    """Loads json configuration from the given config_path"""
    if config_path is None:
        raise Exception('-config cannot be null')
    if not os.path.exists(config_path):
        raise Exception('-config points to non-existent path: %s' % config_path)
    config = None
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config


def setup_logging(output_dir, time_stamp):
    # fix logging paths
    run_log_dir = '%s/%s' % (output_dir, time_stamp)
    run_log_file = '%s/output.txt' % run_log_dir
    if '-logFile' in sys.argv:
        index = sys.argv.index('-logFile')
        run_log_file = sys.argv[index + 1]
    else:
        os.makedirs(run_log_dir)
    print('Logging to %s' % run_log_file)
    # setup logger configuration
    log_formatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(run_log_file)
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)


def main():
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)

    print('Running bootstrap with parameters: %s' % sys.argv)
    config_path = None
    if '-config' in sys.argv:
        index = sys.argv.index('-config')
        config_path = sys.argv[index + 1]
    config = load_config(config_path)
    config = load_overrides(config, sys.argv[1:])
    print('Running bootstrap with configuration: %s' % json.dumps(config, indent=4))

    # setup output directory
    output_dir = config['output']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    setup_logging(output_dir, time_stamp)

    logger = logging.getLogger()
    i = logger.info
    w = logger.warn
    e = logger.error

    checkout_dir = config['checkout']
    if os.path.exists(checkout_dir):
        i('Deleting checkout directory contents at %s' % checkout_dir)
        shutil.rmtree(checkout_dir)

    reports_dir = config['report']
    if not os.path.exists(reports_dir):
        i('Make directory: %s' % reports_dir)
        os.makedirs(reports_dir)

    # load test names in clean room and detention respectively
    clean_room_data_path = '%s/clean_room_data.json' % output_dir
    detention_data_path = '%s/detention_data.json' % output_dir
    clean_room_data = {}
    detention_data = {}
    if os.path.exists(clean_room_data_path):
        i('Loading clean room data from %s' % clean_room_data_path)
        with open(clean_room_data_path, 'r') as f:
            clean_room_data = json.load(f)
    if os.path.exists(detention_data_path):
        i('Loading detention data from %s' % detention_data_path)
        with open(detention_data_path, 'r') as f:
            detention_data = json.load(f)

    # checkout project code
    i('Checking out project source code from %s in %s' % (config['repo'], checkout_dir))
    checkout = solr.LuceneSolrCheckout(config['repo'], checkout_dir)
    checkout.checkout()

    include = config['include'].split('|') if config['include'] is not None else ['*']
    exclude = config['exclude'].split('|') if config['exclude'] is not None else []

    # todo make test directory configurable
    i('Reading test names from test directories matching: src/test')
    test_dirs = []
    # load all test directories in the project
    for root, dirs, files in os.walk(checkout_dir):
        if dirs.count('src') != 0 and os.path.exists(os.path.join(root, os.path.join('src', 'test'))):
            test_dirs.append(os.path.join(root, os.path.join('src', 'test')))

    # key is module name, value is a list of test names
    run_tests = {}
    for d in test_dirs:
        tests = []
        for root, dirs, files in os.walk(d):
            full_paths_to_files = [os.path.join(root, f) for f in files]
            included_tests = []
            for pattern in include:
                included_tests.extend(fnmatch.filter(full_paths_to_files, pattern))
            excluded_tests = []
            for pattern in exclude:
                excluded_tests.extend(fnmatch.filter(included_tests, pattern))
            tests.extend([test for test in included_tests if test not in excluded_tests])
        if len(tests) > 0:
            run_tests[d] = tests

    i('Found test names: %s' % run_tests)


if __name__ == '__main__':
    main()
