#!/bin/python

import os
import logging
from string import Template

import utils
import constants


class Filter:
    def __init__(self, name, filter_command, beast_iters=None, tests_jvms=None, tests_dups=None, tests_iters=None, logger = logging.getLogger()):
        self.name = name
        self.filter_command = filter_command
        m = {'ant': constants.ANT_EXE, 'beast_iters': beast_iters, 'tests_dups' : tests_dups, 'tests_jvms': tests_jvms, 'tests_iters': tests_iters}
        for k in m:
            if m[k] is None:
                m.pop(k)
        self.variables = m
        self.logger = logger

    def filter(self, test_dir, test_name):
        self.logger.info('Running module: %s test: %s through filter: %s' % (test_dir, test_name, self.name))
        x = os.getcwd()
        try:
            os.chdir(test_dir)
            return self.__filter__(test_name)
        except Exception as e:
            self.logger.exception(e)
            return False
        finally:
            os.chdir(x)

    def __filter__(self, test_name):
        template = Template(self.filter_command.strip())
        variables = {'test_name': test_name}
        variables.update(self.variables)
        command = template.substitute(variables)
        cmd = command.strip().split(' ')
        utils.run_command(cmd)
        return True


def main():
    pass


if __name__ == '__main__':
    main()