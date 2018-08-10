#!/bin/python


import sys
import json
import os
import shutil
import datetime
import logging
import fnmatch

import solr
import room_filter
import constants


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
            k, v = p[1:], cmd_params[index + 1]
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


def load_detention_data(input_dir):
    detention_data_path = '%s/detention_data.json' % input_dir
    detention_data = {}
    if os.path.exists(detention_data_path):
        logging.info('Loading detention data from %s' % detention_data_path)
        with open(detention_data_path, 'r') as f:
            detention_data = json.load(f)
    return detention_data


def load_detention_data_for_room(room_name, input_dir):
    data = load_detention_data(input_dir)
    return data[room_name] if room_name in data else {}


def save_detention_data(room_name, detention_data, output_dir):
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)
    detention_data['last_updated'] = time_stamp
    latest_data = load_detention_data(output_dir)
    latest_data[room_name] = detention_data
    detention_data_path = '%s/detention_data.json' % output_dir
    logging.info('Saving detention data at %s' % detention_data_path)
    with open(detention_data_path, 'w') as f:
        json.dump(latest_data, f, indent=4)


def load_clean_room_data(input_dir):
    clean_room_data_path = '%s/clean_room_data.json' % input_dir
    clean_room_data = {}
    if os.path.exists(clean_room_data_path):
        logging.info('Loading clean room data from %s' % clean_room_data_path)
        with open(clean_room_data_path, 'r') as f:
            clean_room_data = json.load(f)
    return clean_room_data


def load_clean_room_data_for_room(room_name, input_dir):
    data = load_clean_room_data(input_dir)
    return data[room_name] if room_name in data else {}


def save_clean_room_data(room_name, clean_room_data, output_dir):
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)
    clean_room_data['last_updated'] = time_stamp
    latest_data = load_clean_room_data(output_dir)
    latest_data[room_name] = clean_room_data
    clean_room_data_path = '%s/clean_room_data.json' % output_dir
    logging.info('Saving clean room data at %s' % clean_room_data_path)
    with open(clean_room_data_path, 'w') as f:
        json.dump(latest_data, f, indent=4)


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

    if '-clean-build' in sys.argv:
        if os.path.exists(checkout_dir):
            w('Deleting checkout directory: %s' % checkout_dir)
            shutil.rmtree(checkout_dir)
        if os.path.exists(constants.ANT_LIB_DIR):
            print('Deleting ant lib directory: %s' % constants.ANT_LIB_DIR)
            shutil.rmtree(constants.ANT_LIB_DIR)
        if os.path.exists(constants.IVY_LIB_CACHE):
            print('Deleting ivy lib directory: %s' % constants.IVY_LIB_CACHE)
            shutil.rmtree(constants.IVY_LIB_CACHE)

    reports_dir = config['report']
    if not os.path.exists(reports_dir):
        i('Make directory: %s' % reports_dir)
        os.makedirs(reports_dir)

    revision = 'LATEST'
    if '-revision' in sys.argv:
        index = sys.argv.index('-revision')
        revision = sys.argv[index + 1]

    # load test names in clean room and detention respectively
    clean_room_data = load_clean_room_data_for_room(config['name'], output_dir)
    detention_data = load_detention_data_for_room(config['name'], output_dir)
    if 'name' in clean_room_data:
        if clean_room_data['name'] != config['name']:
            e('clean room data is for room %s. It cannot be used for %s' % (clean_room_data['name'], config['name']))
            exit(1)
    else:
        clean_room_data['name'] = config['name']

    if 'name' in detention_data:
        if detention_data['name'] != config['name']:
            e('detention data is for room %s. It cannot be used for %s' % (detention_data['name'], config['name']))
            exit(1)
    else:
        detention_data['name'] = config['name']

    if revision is not 'LATEST':
        # we are doing an initial bootstrap so validate that previously recorded git SHA are the same as current one
        if 'sha' in clean_room_data and clean_room_data['sha'] != revision:
            e('clean room sha %s does not match given revision %s' % (clean_room_data['sha'], revision))
            exit(1)
        if 'sha' in detention_data and detention_data['sha'] != revision:
            e('detention room sha %s does not match given revision %s' % (detention_data['sha'], revision))
            exit(1)

    clean_room_data['sha'] = revision
    detention_data['sha'] = revision

    if 'tests' in clean_room_data:
        i('Found %d tests in clean room' % len(clean_room_data['tests']))
    else:
        clean_room_data['tests'] = []

    if 'tests' in detention_data:
        i('Found %d tests in detention' % len(detention_data['tests']))
    else:
        detention_data['tests'] = []

    include = config['include'].split('|') if config['include'] is not None else ['*']
    exclude = config['exclude'].split('|') if config['exclude'] is not None else []

    # checkout project code
    i('Checking out project source code from %s in %s revision: %s' % (config['repo'], checkout_dir, revision))
    checkout = solr.LuceneSolrCheckout(config['repo'], checkout_dir, revision)
    checkout.checkout()
    git_sha, commit_date = checkout.get_git_rev()
    i('Checked out lucene/solr artifacts from GIT SHA %s with date %s' % (git_sha, commit_date))

    if revision is not 'LATEST' and git_sha != revision:
        e('Checked out git sha %s not the same as given revision %s' % (git_sha, revision))
        exit(1)

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
            run_tests[d.replace('src/test', '')[:-1]] = [os.path.splitext(os.path.basename(t))[0] for t in tests]

    num_tests = 0
    for k in run_tests:
        num_tests += len(run_tests[k])
    i('Found %d tests in %d modules. Test names: %s' % (num_tests, len(run_tests), run_tests))

    i('Compiling lucene/solr tests')
    checkout.compile_tests()

    if '-build-artifacts' in sys.argv:
        i('Building lucene/solr artifacts')
        checkout.build()

    # Building filters
    filters = []
    for f in config['filters']:
        ff = room_filter.Filter(f['name'], f['test'], tests_jvms=config['tests_jvms'])
        filters.append(ff)

    for test_module in run_tests:
        i('Bootstrapping tests in %s' % test_module)
        for test_name in run_tests[test_module]:
            run = True
            clean_tests = clean_room_data['tests']
            detention_tests = detention_data['tests']
            if clean_tests is not None and test_name in clean_tests:
                run = False
            if detention_tests is not None and test_name in detention_tests:
                run = False
            if run:
                promote = True
                for f in filters:
                    if not f.filter(test_module, test_name):
                        promote = False
                        break
                if promote:
                    i('Permitting test %s to clean-room' % test_name)
                    clean_tests.append(test_name)
                    save_clean_room_data(config['name'], clean_room_data, output_dir)
                else:
                    i('Sending test %s to detention' % test_name)
                    detention_tests.append(test_name)
                    save_detention_data(config['name'], detention_data, output_dir)
                i('Finished')
                exit(0)
            else:
                i('Skipping test %s' % test_name)


if __name__ == '__main__':
    main()
