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

import bootstrap
import room_filter


GOOD = 0
BAD = 1
SKIP = 125
ABORT = 128


def test(config, test_name):
    checkout_dir = config['checkout']

    filters = []
    for f in config['filters']:
        ff = room_filter.Filter(f['name'], f['test'], tests_jvms=config['tests_jvms'])
        filters.append(ff)

    include = config['include'].split('|') if 'include' in config else ['*.java']
    exclude = config['exclude'].split('|') if 'exclude' in config else []

    print('Reading test names from test directories matching: src/test')
    run_tests = bootstrap.gather_interesting_tests(checkout_dir, exclude, include)

    test_module = None
    for module in run_tests:
        for t in run_tests[module]:
            if t == test_name:
                test_module = module
                break

    if test_module is None:
        # maybe the test is new?
        print('No test module could be found for test %s, exiting' % test_name)
        return SKIP

    promote = True
    for f in filters:
        if not f.filter(test_module, test_name):
            promote = False
            break

    return GOOD if promote else BAD


def main():
    test_name = None
    if '-test' in sys.argv:
        index = sys.argv.index('-test')
        test_name = sys.argv[index + 1]
    else:
        # status code above 127 will abort a git bisect
        print('No -test specified for testing, exiting.')
        exit(ABORT)

    config = bootstrap.get_config()
    exit(test(config, test_name))


if __name__ == '__main__':
    main()