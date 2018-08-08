#!/bin/python

import os
import subprocess
import datetime
import time
import logging


def info(message):
    print('[%s] %s' % (datetime.datetime.now(), message))


def run_get_output(command):
    return str(subprocess.check_output(command))


def run_command(command, logger=logging.getLogger()):
    from StringIO import StringIO
    logger.info('RUN: %s' % command)
    t0 = time.time()
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output, error = process.communicate()

        logger.info(StringIO(output))
        logger.error(StringIO(error))
    except (OSError, subprocess.CalledProcessError) as exception:
        logger.error('Exception occurred: ' + str(exception))
        logger.error('Subprocess failed')
    else:
        # no exception was raised
        logger.info('Subprocess finished')
        logger.info('Took %.1f sec' % (time.time() - t0))
