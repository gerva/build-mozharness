#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****
"""MarMixin, manages mar files"""

import os
import sys
import ConfigParser
from mozharness.base.script import ScriptMixin
from mozharness.base.log import LogMixin
from mozharness.mozilla.mock import MockMixin

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))


CONFIG = {
    "buildid_section": 'App',
    "buildid_option": "BuildID",
}


def query_ini_file(ini_file, section, option):
    ini = ConfigParser.SafeConfigParser()
    ini.read(ini_file)
    return ini.get(section, option)


def buildid_from_ini(ini_file):
    """reads an ini_file and returns the buildid"""
    return query_ini_file(ini_file,
                          CONFIG.get('buildid_section'),
                          CONFIG.get('buildid_option'))


# MarMixin {{{1
class Mar(ScriptMixin, LogMixin, MockMixin):
    log_obj = None
    config = {}

    def __init__(self, config, log_obj, abs_dirs):
        for key, value in config.iteritems():
            self.config[key] = value
        if 'volatile_config' in self.config:
            self.config['volatile_config'] = {}
        self.log_obj = log_obj
        self.abs_dirs = abs_dirs
        self.version = None
        self.package_urls = {}
        super(Mar, self).__init__()
        if 'mock_target' in self.config:
            self.enable_mock()

    def _mar_tool_dir(self):
        """returns the path or the mar tool directory"""
        return os.path.join(self.abs_dirs['abs_objdir'],
                            self.config["local_mar_tool_dir"])

    def _incremental_update_script(self):
        """returns the path of incremental update script"""
        return os.path.join(self.abs_dirs['abs_mozilla_dir'],
                            self.config['incremental_update_script'])

    def download_mar_tools(self):
        """downloads mar tools executables (mar,mbsdiff)
           and stores them local_dir()"""
        self.info("getting mar tools")
        dst_dir = self._mar_tool_dir()
        self.mkdir_p(dst_dir)
        config = self.config
        replace_dict = {'platform': config['platform'],
                        'branch': config['branch']}
        url = config['mar_tools_url'] % replace_dict
        binaries = (config['mar'], config['mbsdiff'])
        for binary in binaries:
            from_url = "/".join((url, binary))
            full_path = os.path.join(dst_dir, binary)
            if not os.path.exists(full_path):
                self.download_file(from_url, file_name=full_path)
                self.info("downloaded %s" % full_path)
            else:
                self.info("found %s, skipping download" % full_path)
            self.chmod(full_path, 0755)

    def _temp_mar_base_dir(self):
        """a base dir for unpacking mars"""
        return self.abs_dirs['abs_objdir']

    def _temp_mar_dir(self, name):
        """creates a temporary directory for mar unpack"""
        # tempfile.makedir() and TemporaryDir() work great outside mock envs
        mar_dir = os.path.join(self._temp_mar_base_dir(), name)
        # delete mar_dir, it prints a message if temp_dir does not exist..
        self.rmtree(self._temp_mar_dir())
        self.mkdir_p(mar_dir)
        self.info("temporary mar dir: %s" % (mar_dir))
        return mar_dir

    def _unpack_script(self):
        """unpack script full path"""
        return os.path.join(self.abs_dirs['abs_mozilla_dir'],
                            self.config['unpack_script'])

    def _unpack_mar(self, mar_file, dst_dir, env):
        """unpacks a mar file into dst_dir"""
        cmd = ['perl', self._unpack_script(), mar_file]
        self.info("unpacking %s" % mar_file)
        self.mkdir_p(dst_dir)
        return self.run_command(cmd,
                                cwd=dst_dir,
                                env=env,
                                halt_on_failure=True)

    def do_incremental_update(self, previous_dir, current_dir, partial_filename,
                              env):
        """create an incremental update from src_mar to dst_src.
           It stores the result in partial_filename"""
        # Usage: make_incremental_update.sh [OPTIONS] ARCHIVE FROMDIR TODIR
        cmd = [self._incremental_update_script(), partial_filename,
               current_dir, previous_dir]
        cwd = self._mar_dir('update_mar_dir')
        self.mkdir_p(cwd)
        result = self.run_command(cmd, cwd=cwd, env=env)
        return result

    def get_buildid_from_mar_dir(self, mar_unpack_dir):
        """returns the buildid of the current mar file"""
        config = self.config
        ini_file = config['application_ini']
        ini_file = os.path.join(mar_unpack_dir, ini_file)
        self.info("application.ini file: %s" % ini_file)

        # log the content of application.ini
        with self.opened(ini_file, 'r') as (ini, error):
            if error:
                self.fatal('cannot open %s' % ini_file)
            self.debug(ini.read())
        return buildid_from_ini(ini_file)

    def _query_complete_mar_url(self, locale):
        """returns the complete mar url taken from self.package_urls[locale]
           this value is available only after make_upload"""
        if "complete_mar_url" in self.config:
            return self.config["complete_mar_url"]
        if "completeMarUrl" in self.package_urls[locale]:
            return self.package_urls[locale]["completeMarUrl"]
        # url = self.config.get("update", {}).get("mar_base_url")
        # if url:
        #    url += os.path.basename(self.query_marfile_path())
        #    return url.format(branch=self.query_branch())
        self.fatal("Couldn't find complete mar url in config or package_urls")

    def _update_mar_dir(self):
        """returns the full path of the update/ directory"""
        return self._mar_dir('update_mar_dir')

    def _current_mar_dir(self):
        """returns the full path of the current/ directory"""
        return self._mar_dir('current_mar_dir')

    def _current_work_mar_dir(self):
        """returns the full path to current.work"""
        return self._mar_dir('current_work_mar_dir')

    def _mar_binaries(self):
        """returns a tuple with mar and mbsdiff paths"""
        config = self.config
        return (config['mar'], config['mbsdiff'])

    def _mar_dir(self, dirname):
        """returns the full path of dirname;
            dirname is an entry in configuration"""
        config = self.config
        return os.path.join(self.abs_dirs['abs_objdir'], config.get(dirname))

    def _query_complete_mar_filename(self, locale):
        """returns the full path to a localized complete mar file"""
        config = self.config
        complete_mar_name = config['localized_mar'] % {'version': self.version,
                                                       'locale': locale}
        return os.path.join(self._update_mar_dir(), complete_mar_name)

    def _query_partial_mar_url(self, locale):
        """returns partial mar url"""
        try:
            return self.package_urls[locale]["partialMarUrl"]
        except KeyError:
            msg = "Couldn't find package_urls: %s %s" % (locale, self.package_urls)
            self.error("package_urls: %s" % (self.package_urls))
            self.fatal(msg)

    def _query_partial_mar_filename(self, locale):
        """returns the full path to a partial, it returns a valid path only
           after make upload"""
        partial_mar_name = self.package_urls[locale]['partial_filename']
        return os.path.join(self._update_mar_dir(), partial_mar_name)

    def _query_previous_mar_buildid(self, locale):
        """return the partial mar buildid,
        this method returns a valid buildid only after generate partials,
        it raises an exception when buildid is not available
        """
        try:
            return self.package_urls[locale]["previous_buildid"]
        except KeyError:
            self.error("no previous mar buildid")
            raise

    def _previous_mar_dir(self):
        """returns the full path of the previous/ directory"""
        return self._mar_dir('previous_mar_dir')

    def _get_previous_mar(self, locale):
        """downloads the previous mar file"""
        self.mkdir_p(self._previous_mar_dir())
        self.download_file(self._previous_mar_url(locale),
                           self._previous_mar_filename())
        return self._previous_mar_filename()

    def _current_mar_name(self):
        """returns current mar file name"""
        config = self.config
        return config["current_mar_filename"] % {'version': self.version}

    def _localized_mar_name(self, locale):
        """returns localized mar name"""
        config = self.config
        return config["localized_mar"] % {'version': self.version, 'locale': locale}

    def _previous_mar_filename(self):
        """returns the complete path to previous.mar"""
        config = self.config
        return os.path.join(self._previous_mar_dir(),
                            config['previous_mar_filename'])

    def _current_mar_filename(self):
        """returns the complete path to current.mar"""
        return os.path.join(self._current_mar_dir(), self._current_mar_name())

    def _create_mar_dirs(self):
        """creates mar directories: previous/ current/"""
        for directory in (self._previous_mar_dir(),
                          self._current_mar_dir()):
            self.info("creating: %s" % directory)
            self.mkdir_p(directory)

    def _delete_mar_dirs(self):
        """delete mar directories: previous, current"""
        for directory in (self._previous_mar_dir(),
                          self._current_mar_dir(),
                          self._current_work_mar_dir()):
            self.info("deleting: %s" % directory)
            if os.path.exists(directory):
                self.rmtree(directory)

    def _current_mar_url(self):
        """returns current mar url"""
        config = self.config
        base_url = config['current_mar_url']
        return "/".join((base_url, self._current_mar_name()))

    def _previous_mar_url(self, locale):
        """returns the url for previous mar"""
        config = self.config
        base_url = config['previous_mar_url']
        return "/".join((base_url, self._localized_mar_name(locale)))

    def _get_current_mar(self):
        """downloads the current mar file"""
        self.mkdir_p(self._previous_mar_dir())
        if not os.path.exists(self._current_mar_filename()):
            self.download_file(self._current_mar_url(),
                               self._current_mar_filename())
        else:
            self.info('%s already exists, skipping download' % (self._current_mar_filename()))
        return self._current_mar_filename()

    def localized_marfile(self, version, locale):
        """returns the localized mar file name"""
        config = self.config
        localized_mar = config['localized_mar'] % {'version': version,
                                                   'locale': locale}
        localized_mar = os.path.join(self._mar_dir('update_mar_dir'),
                                     localized_mar)
        return localized_mar
