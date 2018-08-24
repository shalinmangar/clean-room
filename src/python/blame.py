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

import bootstrap
import solr
import utils
import constants


def blame(config, time_stamp, test_date, test_name, good_sha, bad_sha):
    i = logging.info

    i('Checking out code')
    checkout = solr.LuceneSolrCheckout(config['repo'], config['checkout'])
    checkout.checkout(bad_sha)

    # TODO run the bisect script against the bad_sha first and assert that it
    # TODO fails otherwise the bisection is not likely to be useful

    cmd = [constants.GIT_EXE, 'bisect', 'start', bad_sha, good_sha]
    i('Running command: %s' % cmd)
    output, ret = utils.run_get_output(cmd)
    i(output)

    index = sys.argv.index('-config')
    config_path = sys.argv[index + 1]

    # git bisect run sh -c "ant compile-test || exit 125; python src/python/bisect.py -config %s -test %s"
    cmd = [constants.GIT_EXE, 'bisect', 'run', 'sh', '-c',
           'ant compile-test || exit 125; python src/python/bisect.py -config %s -test %s'
           % (config_path, test_name)]
    i('Running command: %s' % cmd)
    start_time = time.time()
    output, ret = utils.run_get_output(cmd)
    i('Time taken: %d seconds' % (time.time() - start_time))
    i(output)

    # git bisect reset
    cmd = [constants.GIT_EXE, 'bisect', 'reset']
    i('Running command: %s' % cmd)
    output, ret = utils.run_get_output(cmd)
    i(output)


def main():
    start = datetime.datetime.now()
    time_stamp = '%04d.%02d.%02d.%02d.%02d.%02d' % (
        start.year, start.month, start.day, start.hour, start.minute, start.second)

    test_name = None
    if '-test' in sys.argv:
        index = sys.argv.index('-test')
        test_name = sys.argv[index + 1]
    else:
        # status code above 127 will abort a git bisect
        print('No -test specified for blame, exiting.')
        exit(1)

    good_sha = None
    bad_sha = None
    if '-good-sha' in sys.argv:
        index = sys.argv.index('-good-sha')
        good_sha = sys.argv[index + 1]
    if '-bad-sha' in sys.argv:
        index = sys.argv.index('-bad-sha')
        bad_sha = sys.argv[index + 1]

    # in the format 2017-11-21
    test_date = None
    if '-test-date' in sys.argv:
        index = sys.argv.index('-test-date')
        test_date = sys.argv[index + 1]
        test_date = datetime.datetime.strptime(test_date, '%Y.%m.%d.%H.%M.%S')
    else:
        # set to now
        test_date = start

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

    config['time_stamp'] = time_stamp
    bootstrap.setup_logging(output_dir, time_stamp, level)

    blame(config, time_stamp, test_date, test_name, good_sha, bad_sha)


if __name__ == '__main__':
    main()
