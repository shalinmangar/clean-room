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

import subprocess
import time
import logging

GOOD_STATUS = 0
BAD_STATUS = 1
SKIP_STATUS = 125
ABORT_STATUS = 128


def run_get_output(command):
    try:
        return str(subprocess.check_output(command, stderr=subprocess.STDOUT)), 0
    except subprocess.CalledProcessError as exception:
        return exception.output, exception.returncode


def run_command(command, logger=logging.getLogger()):
    logger.info('RUN: %s' % command)
    t0 = time.time()
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output, _ = process.communicate()
        logger.info(output)
    except (OSError, subprocess.CalledProcessError) as exception:
        logger.error('Exception occurred: ' + str(exception))
        logger.error('Subprocess failed')
        raise exception
    except Exception as exception:
        raise exception
    else:
        # no exception was raised
        logger.info('Subprocess finished')
        logger.info('Took %.1f sec' % (time.time() - t0))
