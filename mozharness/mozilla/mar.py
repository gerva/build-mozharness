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

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))


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


# MarMixin {{{1
class MarMixin(object):
    def download_mar_tools(self):
        """downloads mar tools executables (mar,mbsdiff)
           and stores them local_dir()"""
        self.info("getting mar tools")
        dst_dir = self._mar_tool_dir()
        self.mkdir_p(dst_dir)
        config = self.config
        url = config['mar_tools_url']
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
        dirs = self.query_abs_dirs()
        return dirs['abs_objdir']

    def _temp_mar_dir(self, name):
        """creates a temporary directory for mar unpack"""
        # tempfile.makedir() and TemporaryDir() work great outside mock envs
        mar_dir = os.path.join(self._temp_mar_base_dir(), name)
        # delete mar_dir, it prints a message if temp_dir does not exist..
        self.rmtree(self._temp_mar_dir())
        self.mkdir_p(mar_dir)
        self.info("temporary mar dir: %s" % (mar_dir))
        return mar_dir

    def _unpack_mar(self, mar_file, dst_dir, prettynames):
        """unpacks a mar file into dst_dir"""
        cmd = ['perl', self._unpack_script(), mar_file]
        tools_dir = self._mar_tool_dir()
        env = tools_environment(tools_dir,
                                self._mar_binaries(),
                                self.query_repack_env())
        env["MOZ_PKG_PRETTYNAMES"] = str(prettynames)
        self.info("unpacking %s" % mar_file)
        self.mkdir_p(dst_dir)
        return self.run_command(cmd,
                                cwd=dst_dir,
                                env=env,
                                halt_on_failure=True)

    def do_incremental_update(self, src_mar, dst_mar, partial_filename, prettynames):
        """create an incremental update from src_mar to dst_src.
           It stores the result in partial_filename"""
        fromdir = self._temp_mar_dir('current')
        todir = self._temp_mar_dir('previous')
        self._unpack_mar(src_mar, fromdir, prettynames)
        self._unpack_mar(dst_mar, todir, prettynames)
        # Usage: make_incremental_update.sh [OPTIONS] ARCHIVE FROMDIR TODIR
        cmd = [self._incremental_update_script(), partial_filename,
               fromdir, todir]
        tools_dir = self._mar_tool_dir()
        env = tools_environment(tools_dir,
                                self._mar_binaries(),
                                self.query_repack_env())
        result = self.run_command(cmd, cwd=None, env=env)
        self.rmtree(src_mar)
        self.rmtree(dst_mar)
        return result

    def query_build_id(self, mar_file, prettynames):
        """returns the buildid of the current mar file"""
        temp_dir = self._temp_mar_dir('temp_dir')
        self._unpack_mar(mar_file=mar_file, dst_dir=temp_dir,
                         prettynames=prettynames)
        config = self.config
        ini_file = config['application_ini']
        ini_file = os.path.join(temp_dir, ini_file)
        self.info("application.ini file: %s" % ini_file)

        # log the content of application.ini
        with self.opened(ini_file, 'r') as (ini, error):
            if error:
                self.fatal('cannot open {0}'.format(ini_file))
            self.debug(ini.read())
        # delete temp_dir
        _buildid = buildid_from_ini(ini_file)
        self.rmtree(temp_dir)
        return _buildid
