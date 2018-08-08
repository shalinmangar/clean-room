#!/bin/python

import os
import utils
import constants
import glob
import datetime
import logging


class LuceneSolrCheckout:
    def __init__(self, git_repo, checkout_dir, revision='LATEST', logger=logging.getLogger()):
        self.git_repo = git_repo
        self.checkout_dir = checkout_dir
        self.revision = revision
        self.logger = logger

    def checkout(self):
        logger = self.logger
        logger.info(
            'Attempting to checkout Lucene/Solr revision: %s into directory: %s' % (
                self.revision, self.checkout_dir))
        if not os.path.exists(self.checkout_dir):
            os.makedirs(self.checkout_dir)
        f = os.listdir(self.checkout_dir)
        x = os.getcwd()
        try:
            os.chdir(self.checkout_dir)
            if len(f) == 0:
                # clone
                utils.run_command([constants.GIT_EXE, 'clone', self.git_repo, '.'])
                if not self.revision == 'LATEST':
                    self.update_to_revision()
                try:
                    utils.run_command(['rm', '-r', '~/.ant/lib/ivy-*.jar'])
                except:
                    logger.warn('Unable to remove previous ivy-2.3.0.jar')
                utils.run_command([constants.ANT_EXE, 'ivy-bootstrap'])
            else:
                self.update_to_revision()
        finally:
            os.chdir(x)

    def update_to_revision(self):
        # resets any staged changes (there shouldn't be any though)
        utils.run_command([constants.GIT_EXE, 'reset', '--hard'])
        # clean ANY files not tracked in the repo -- this effectively restores pristine state
        utils.run_command([constants.GIT_EXE, 'clean', '-xfd', '.'])
        utils.run_command([constants.GIT_EXE, 'checkout', 'origin/master'])
        if self.revision == 'LATEST':
            utils.run_command([constants.GIT_EXE, 'pull', 'origin', 'master'])
        else:
            utils.run_command([constants.GIT_EXE, 'checkout', self.revision])

    def build(self):
        x = os.getcwd()
        try:
            os.chdir('%s' % self.checkout_dir)
            utils.run_command([constants.ANT_EXE, 'clean', 'clean-jars'])
            os.chdir('%s/solr' % self.checkout_dir)
            utils.run_command([constants.ANT_EXE, 'compile-test', 'create-package'])
            packaged = os.path.join(os.getcwd(), "package")
            files = glob.glob(os.path.join(packaged, '*.tgz'))
            if len(files) == 0:
                raise RuntimeError('No tgz file found at %s' % packaged)
            elif len(files) > 1:
                raise RuntimeError('More than 1 tgz file found at %s' % packaged)
            else:
                return files[0]
        finally:
            os.chdir(x)

    def get_git_rev(self):
        x = os.getcwd()
        try:
            os.chdir(self.checkout_dir)
            s = utils.run_get_output([constants.GIT_EXE, 'show', '-s', '--format=%H,%ci'])
            sha, date = s.split(',')
            date_parts = date.split(' ')
            return sha, datetime.datetime.strptime('%s %s' % (date_parts[0], date_parts[1]), '%Y-%m-%d %H:%M:%S')
        finally:
            os.chdir(x)
