#!/bin/python

import subprocess
import time
import logging


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
