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
import json
import os
import shutil
import datetime
import logging
import fnmatch

import solr
import room_filter
import constants
import clean_room


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


def setup_logging(output_dir, time_stamp, level=logging.INFO):
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
    root_logger.setLevel(level)
    file_handler = logging.FileHandler(run_log_file)
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)


def load_detention_data(file_path):
    detention_data = {}
    if os.path.exists(file_path):
        logging.info('Loading detention data from %s' % file_path)
        with open(file_path, 'r') as f:
            detention_data = json.load(f)
    return detention_data


def load_detention_data_for_room(room_name, file_path):
    data = load_detention_data(file_path)
    return data[room_name] if room_name in data else {}


def save_detention_data(room_name, detention_data, file_path):
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)
    detention_data['last_updated'] = time_stamp
    latest_data = load_detention_data(file_path)
    latest_data[room_name] = detention_data
    logging.info('Saving detention data at %s' % file_path)
    with open(file_path, 'w') as f:
        json.dump(latest_data, f, indent=4)


def load_clean_room_data(file_path):
    clean_room_data = {}
    if os.path.exists(file_path):
        logging.info('Loading clean room data from %s' % file_path)
        with open(file_path, 'r') as f:
            clean_room_data = json.load(f)
    return clean_room_data


def load_clean_room_data_for_room(room_name, file_path):
    data = load_clean_room_data(file_path)
    return data[room_name] if room_name in data else {}


def save_clean_room_data(room_name, clean_room_data, file_path):
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)
    clean_room_data['last_updated'] = time_stamp
    latest_data = load_clean_room_data(file_path)
    latest_data[room_name] = clean_room_data
    logging.info('Saving clean room data at %s' % file_path)
    with open(file_path, 'w') as f:
        json.dump(latest_data, f, indent=4)


def gather_interesting_tests(checkout_dir, exclude, include):
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
    return run_tests


def get_config():
    print('Running with parameters: %s' % sys.argv)
    config_path = None
    if '-config' in sys.argv:
        index = sys.argv.index('-config')
        config_path = sys.argv[index + 1]
    config = load_config(config_path)
    config = load_overrides(config, sys.argv[1:])
    print('Running with configuration: %s' % json.dumps(config, indent=4))
    return config


def load_validate_room_data(config, output_dir, revision):
    logger = logging.getLogger()
    i = logger.info
    w = logger.warn
    e = logger.error

    # load test names in clean room and detention respectively
    clean_room_data = load_clean_room_data_for_room(config['name'], '%s/clean_room_data.json' % output_dir)
    detention_data = load_detention_data_for_room(config['name'], '%s/detention_data.json' % output_dir)
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

    if 'tests' in clean_room_data:
        i('Found %d tests in clean room' % len(clean_room_data['tests']))
    else:
        clean_room_data['tests'] = {}
    if 'tests' in detention_data:
        i('Found %d tests in detention' % len(detention_data['tests']))
    else:
        detention_data['tests'] = {}
    return clean_room_data, detention_data


def write_report(config, clean, detention, test_date):
    test_date_str = test_date.strftime('%Y-%m-%d %H-%M-%S')
    reports_dir = config['report']
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
              'test_date': test_date_str}
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=8, sort_keys=True)
    return report_file


def main():
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)

    config = get_config()

    # setup output directory
    output_dir = config['output']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    level = logging.INFO
    if '-debug' in sys.argv:
        level = logging.DEBUG

    setup_logging(output_dir, time_stamp, level)

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

    clean_room_data, detention_data = load_validate_room_data(config, output_dir, revision)
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
    clean = clean_room.Room('clean-room', clean_room_data)
    detention = clean_room.Room('detention', detention_data)

    include = config['include'].split('|') if config['include'] is not None else ['*.java']
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
    run_tests = gather_interesting_tests(checkout_dir, exclude, include)

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
            if clean.has(test_name) or detention.has(test_name):
                run = False
            if run:
                promote = True
                for f in filters:
                    if not f.filter(test_module, test_name):
                        promote = False
                        break
                date_str = commit_date.strftime('%Y-%m-%d %H:%M:%S')
                if promote:
                    i('Permitting test %s to clean-room' % test_name)
                    clean.enter(test_name, date_str, git_sha)
                    save_clean_room_data(config['name'], clean.get_data(), '%s/clean_room_data.json' % output_dir)
                else:
                    i('Sending test %s to detention' % test_name)
                    detention.enter(test_name, date_str, git_sha)
                    save_detention_data(config['name'], detention.get_data(), '%s/detention_data.json' % output_dir)
            else:
                i('Skipping test %s' % test_name)

    report_file = write_report(config, clean, detention, commit_date)
    i('Report written to: %s' % report_file)


if __name__ == '__main__':
    main()
