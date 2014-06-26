#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****
"""desktop_l10n.py

Firefox repacks
"""

import os
import sys
import tempfile
import ConfigParser
import copy

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.log import LogMixin
from mozharness.base.script import ScriptMixin
from mozharness.mozilla.mock import MockMixin


CONFIG = {
    "buildid_section": 'App',
    "buildid_option": "BuildID",
    "unpack_script": "unwrap_full_update.pl",
    "incremental_update_script": "make_incremental_update.sh",
    "update_packaging_dir": "tools/update-packaging",
}


def tools_environment(base_dir, binaries, env):
    """returns the env setting required to run mar and/or mbsdiff"""
    # bad code here - FIXIT
    for binary in binaries:
        binary_name = binary.replace(".exe", "").upper()
        env[binary_name] = os.path.join(base_dir, binary)
        # windows -> python -> perl -> sh
        # windows fix...
        env[binary_name] = env[binary_name].replace("\\", "/")
    return env


def query_ini_file(ini_file, section, option):
    ini = ConfigParser.SafeConfigParser()
    ini.read(ini_file)
    return ini.get(section, option)


def buildid_from_ini(ini_file):
    """reads an ini_file and returns the buildid"""
    return query_ini_file(ini_file,
                          CONFIG.get('buildid_section'),
                          CONFIG.get('buildid_option'))


# MarTool {{{1
class MarTool(ScriptMixin, LogMixin, MockMixin, object):
    """manages the mar tools executables"""
    def __init__(self, config, dst_dir, log_obj, binaries):
        self.url = config['mar_tools_url']
        self.dst_dir = dst_dir
        self.binaries = binaries
        self.log_obj = log_obj
        self.config = config
        # enable mock
        if config.get('enable_mock'):
            self.mock_enable()

        super(MarTool, self).__init__()

    def download(self):
        """downloads mar tools executables (mar,mbsdiff)
           and stores them local_dir()"""
        self.info("getting mar tools")
        self.mkdir_p(self.dst_dir)
        for binary in self.binaries:
            from_url = "/".join((self.url, binary))
            full_path = os.path.join(self.dst_dir, binary)
            if not os.path.exists(full_path):
                self.download_file(from_url, file_name=full_path)
                self.info("downloaded %s" % full_path)
            else:
                self.info("found %s, skipping download" % full_path)
            self.chmod(full_path, 0755)


# MarFile {{{1
class MarFile(ScriptMixin, LogMixin, object):
    """manages the downlad/unpack and incremental updates of mar files"""
    def __init__(self, config, mar_scripts, log_obj, filename=None,
                 prettynames=0):
        self.filename = filename
        self.log_obj = log_obj
        self.build_id = None
        self.mar_scripts = mar_scripts
        self.prettynames = str(prettynames)
        self.config = config
        # enable mock
        if config.get('enable_mock'):
            self.mock_enable()
        super(MarFile, self).__init__()

    def unpack_mar(self, dst_dir):
        """unpacks a mar file into dst_dir"""
        self.download()
        # downloading mar tools
        cmd = ['perl', self._unpack_script(), self.filename]
        mar_scripts = self.mar_scripts
        tools_dir = mar_scripts.tools_dir
        env = tools_environment(tools_dir,
                                mar_scripts.mar_binaries,
                                mar_scripts.env)
        env["MOZ_PKG_PRETTYNAMES"] = self.prettynames
        self.mkdir_p(dst_dir)
        return self.run_command(cmd,
                                cwd=dst_dir,
                                env=env,
                                halt_on_failure=True)

    def download(self):
        """downloads mar file - not implemented yet"""
        if not os.path.exists(self.filename):
            pass
        return self.filename

    def _incremental_update_script(self):
        """full path to the incremental update script"""
        scripts = self.mar_scripts
        return scripts.incremental_update

    def _unpack_script(self):
        """returns the full path to the unpack script """
        scripts = self.mar_scripts
        return scripts.unpack

    def incremental_update(self, other, partial_filename):
        """create an incremental update from the current mar to the
          other mar object. It stores the result in partial_filename"""
        fromdir = tempfile.mkdtemp()
        todir = tempfile.mkdtemp()
        self.unpack_mar(fromdir)
        other.unpack_mar(todir)
        # Usage: make_incremental_update.sh [OPTIONS] ARCHIVE FROMDIR TODIR
        cmd = [self._incremental_update_script(), partial_filename,
               fromdir, todir]
        mar_scripts = self.mar_scripts
        tools_dir = mar_scripts.tools_dir
        env = tools_environment(tools_dir,
                                mar_scripts.mar_binaries,
                                mar_scripts.env)
        result = self.run_command(cmd, cwd=None, env=env)
        self.rmtree(todir)
        self.rmtree(fromdir)
        return result

    def buildid(self):
        """returns the buildid of the current mar file"""
        if self.build_id is not None:
            return self.build_id
        temp_dir = tempfile.mkdtemp()
        self.unpack_mar(temp_dir)
        files = self.mar_scripts
        ini_file = os.path.join(temp_dir, files.ini_file)
        self.info("application.ini file: %s" % ini_file)

        # log the content of application.ini
        with self.opened(ini_file, 'r') as (ini, error):
            if error:
                self.fatal('cannot open {0}'.format(ini_file))
            self.debug(ini.read())
        # delete temp_dir
        self.build_id = buildid_from_ini(ini_file)
        self.rmtree(temp_dir)
        return self.build_id


class MarScripts(object):
    """holds the information on scripts and directories paths needed
       by MarTool and MarFile"""
    def __init__(self, config, unpack, incremental_update,
                 tools_dir, mar_binaries,
                 env):
        self.ini_file = config['application_ini']
        self.config = config
        self.unpack = unpack
        self.incremental_update = incremental_update
        self.tools_dir = tools_dir
        self.mar_binaries = mar_binaries
        # what happens in mar.py stays in mar.py
        self.env = copy.deepcopy(env)
