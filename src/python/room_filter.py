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

import os
import logging
import time
import re
from string import Template

import utils
import constants


class Filter:
    re_no_test_executed = re.compile('Not even a single test was executed')
    re_beast_no_test_executed = re.compile('Beasting executed no tests')
    
    # [junit4] ERROR: JVM J1 ended with an exception, command line: [...]
    # [junit4] ERROR: JVM J1 ended with an exception: Forked process returned with error code: 134. Very likely a JVM crash.  See process stdout at: [...]
    re_jvm_exception = re.compile(r'ERROR: JVM J\d+ ended with an exception')

    def __init__(self, name, filter_command, log_command_output_level=logging.INFO, beast_iters=None, tests_jvms=None, tests_dups=None, tests_iters=None, logger = logging.getLogger()):
        self.name = name
        self.filter_command = filter_command
        self.log_command_output_level = log_command_output_level
        m = {'ant': constants.ANT_EXE, 'beast_iters': beast_iters, 'tests_dups' : tests_dups, 'tests_jvms': tests_jvms, 'tests_iters': tests_iters}
        rm = []
        for k in m:
            if m[k] is None:
                rm.append(k)
        for k in rm:
            m.pop(k)
        self.variables = m
        self.logger = logger

    def filter(self, test_dir, test_name):
        self.logger.info('Running module: %s test: %s through filter: %s' % (test_dir, test_name, self.name))
        x = os.getcwd()
        try:
            self.logger.info('Changing cwd to %s' % test_dir)
            os.chdir(test_dir)
            return self.__filter__(test_name)
        except Exception as e:
            self.logger.exception(e)
            return utils.BAD_STATUS
        finally:
            self.logger.info('Changing cwd back to %s' % x)
            os.chdir(x)

    def __filter__(self, test_name):
        template = Template(self.filter_command.strip())
        variables = {'test_name': test_name}
        variables.update(self.variables)
        command = template.substitute(variables)
        cmd = command.strip().split(' ')
        self.logger.info('RUN: %s' % cmd)
        t0 = time.time()
        output = ''
        exitcode = None
        try:
            output, exitcode = utils.run_get_output(cmd)
        except Exception as e:
            self.logger.exception('Exception running command %s' % cmd, e)
        self.logger.info('Took %.1f sec' % (time.time() - t0))
        if self.log_command_output_level is not None and output != '':
            self.logger.log(self.log_command_output_level, output)
        if self.re_no_test_executed.search(output) is not None or self.re_beast_no_test_executed.search(output) is not None:
            self.logger.warn('No tests were executed.  Skipping this revision.')
            return utils.SKIP_STATUS
        if self.re_jvm_exception.search(output) is not None:
            self.logger.warn("A filter's JVM ended with an exception.  Skipping this revision.")
            return utils.SKIP_STATUS

        return utils.GOOD_STATUS if exitcode == 0 else utils.BAD_STATUS


def main():
    pass


if __name__ == '__main__':
    main()
