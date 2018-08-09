#!/bin/python

import os
import logging
import time
from string import Template

import utils
import constants


class Filter:
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
            return False
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
        exitcode = None
        try:
            output, exitcode = utils.run_get_output(cmd)
            if self.log_command_output_level is not None:
                self.logger.log(self.log_command_output_level, output)
        except Exception as e:
            self.logger.exception('Exception running command %s' % cmd, e)
        self.logger.info('Took %.1f sec' % (time.time() - t0))
        # todo should we introduce an indeterminate stage?
        return True if exitcode == 0 else False


def main():
    pass


if __name__ == '__main__':
    main()
