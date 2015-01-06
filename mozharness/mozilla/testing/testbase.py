#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****

import copy
import os
import platform
import re
import urllib2
import getpass

from mozharness.base.config import ReadOnlyDict, parse_config_file
from mozharness.base.errors import BaseErrorList
from mozharness.base.log import FATAL
from mozharness.base.python import (
    ResourceMonitoringMixin,
    VirtualenvMixin,
    virtualenv_config_options,
)
from mozharness.mozilla.buildbot import BuildbotMixin
from mozharness.mozilla.proxxy import Proxxy
from mozharness.mozilla.structuredlog import StructuredOutputParser
from mozharness.mozilla.testing.unittest import DesktopUnittestOutputParser

from mozharness.lib.python.authentication import get_credentials

INSTALLER_SUFFIXES = ('.tar.bz2', '.zip', '.dmg', '.exe', '.apk', '.tar.gz')

testing_config_options = [
    [["--installer-url"],
     {"action": "store",
     "dest": "installer_url",
     "default": None,
     "help": "URL to the installer to install",
      }],
    [["--installer-path"],
     {"action": "store",
     "dest": "installer_path",
     "default": None,
     "help": "Path to the installer to install.  This is set automatically if run with --download-and-extract.",
      }],
    [["--binary-path"],
     {"action": "store",
     "dest": "binary_path",
     "default": None,
     "help": "Path to installed binary.  This is set automatically if run with --install.",
      }],
    [["--exe-suffix"],
     {"action": "store",
     "dest": "exe_suffix",
     "default": None,
     "help": "Executable suffix for binaries on this platform",
      }],
    [["--test-url"],
     {"action": "store",
     "dest": "test_url",
     "default": None,
     "help": "URL to the zip file containing the actual tests",
      }],
    [["--jsshell-url"],
     {"action": "store",
     "dest": "jsshell_url",
     "default": None,
     "help": "URL to the jsshell to install",
      }],
    [["--download-symbols"],
     {"action": "store",
     "dest": "download_symbols",
     "type": "choice",
     "choices": ['ondemand', 'true'],
     "help": "Download and extract crash reporter symbols.",
      }],
] + copy.deepcopy(virtualenv_config_options)


# TestingMixin {{{1
class TestingMixin(VirtualenvMixin, BuildbotMixin, ResourceMonitoringMixin):
    """
    The steps to identify + download the proper bits for [browser] unit
    tests and Talos.
    """

    installer_url = None
    installer_path = None
    binary_path = None
    test_url = None
    test_zip_path = None
    tree_config = ReadOnlyDict({})
    symbols_url = None
    symbols_path = None
    jsshell_url = None
    minidump_stackwalk_path = None
    default_tools_repo = 'https://hg.mozilla.org/build/tools'
    proxxy = None

    def _query_proxxy(self):
        """manages the proxxy"""
        if not self.proxxy:
            self.proxxy = Proxxy(self.config, self.log_obj)
        return self.proxxy

    def download_proxied_file(self, url, file_name=None, parent_dir=None,
                              create_parent_dir=True, error_level=FATAL,
                              exit_code=3):
        proxxy = self._query_proxxy()
        return proxxy.download_proxied_file(url=url, file_name=file_name,
                                            parent_dir=parent_dir,
                                            create_parent_dir=create_parent_dir,
                                            error_level=error_level,
                                            exit_code=exit_code)

    def download_file(self, *args, **kwargs):
        '''
        This function helps not to use download of proxied files
        since it does not support authenticated downloads.
        This could be re-factored and fixed in bug 1087664.
        '''
        if self.config.get("developer_mode"):
            return super(TestingMixin, self).download_file(*args, **kwargs)
        else:
            return self.download_proxied_file(*args, **kwargs)

    def query_value(self, key):
        """
        This function allows us to check for a value
        in the self.tree_config first and then on self.config
        """
        return self.tree_config.get(key, self.config.get(key))

    def query_jsshell_url(self):
        """
        Attempt to determine the url of the js shell package given
        the installer url.
        """
        if self.jsshell_url:
            return self.jsshell_url
        if not self.installer_url:
            self.fatal("Can't figure out jsshell without an installer_url!")

        last_slash = self.installer_url.rfind('/')
        base_url = self.installer_url[:last_slash]

        for suffix in INSTALLER_SUFFIXES:
            if self.installer_url.endswith(suffix):
                no_suffix = self.installer_url[:-len(suffix)]
                last_dot = no_suffix.rfind('.')
                pf = no_suffix[last_dot + 1:]

                self.jsshell_url = base_url + '/jsshell-' + pf + '.zip'
                return self.jsshell_url
        else:
            self.fatal("Can't figure out jsshell from installer_url %s!" % self.installer_url)

    def query_symbols_url(self):
        if self.symbols_url:
            return self.symbols_url
        if not self.installer_url:
            self.fatal("Can't figure out symbols_url without an installer_url!")
        for suffix in INSTALLER_SUFFIXES:
            if self.installer_url.endswith(suffix):
                self.symbols_url = self.installer_url[:-len(suffix)] + '.crashreporter-symbols.zip'
                return self.symbols_url
        else:
            self.fatal("Can't figure out symbols_url from installer_url %s!" % self.installer_url)

    def _pre_config_lock(self, rw_config):
        for i, (target_file, target_dict) in enumerate(rw_config.all_cfg_files_and_dicts):
            if 'developer_config' in target_file:
                self._developer_mode_changes(rw_config)

    def _developer_mode_changes(self, rw_config):
        """ This function is called when you append the config called
            developer_config.py. This allows you to run a job
            outside of the Release Engineering infrastructure.

            What this functions accomplishes is:
            * read-buildbot-config is removed from the list of actions
            * --installer-url is set
            * --test-url is set if needed
            * every url is substituted by another external to the
                Release Engineering network
        """
        c = self.config
        orig_config = copy.deepcopy(c)
        self.warning("When you use developer_config.py, we drop " \
                "'read-buildbot-config' from the list of actions.")
        if "read-buildbot-config" in rw_config.actions:
            rw_config.actions.remove("read-buildbot-config")
        self.actions = tuple(rw_config.actions)

        def _replace_url(url, changes):
            for from_, to_ in changes:
                if url.startswith(from_):
                    new_url = url.replace(from_, to_)
                    self.info("Replacing url %s -> %s" % (url, new_url))
                    return new_url
            return url

        assert c["installer_url"], "You must use --installer-url with developer_config.py"
        if c.get("require_test_zip"):
            assert c["test_url"], "You must use --test-url with developer_config.py"

        c["installer_url"] = _replace_url(c["installer_url"], c["replace_urls"])
        if c.get("test_url"):
            c["test_url"] = _replace_url(c["test_url"], c["replace_urls"])

        for key, value in self.config.iteritems():
            if type(value) == str and value.startswith("http"):
                self.config[key] = _replace_url(value, c["replace_urls"])

        # Any changes to c means that we need credentials
        if not c == orig_config:
            get_credentials()

    def _urlopen(self, url, **kwargs):
        '''
        This function helps dealing with downloading files while outside
        of the releng network.
        '''
        # Code based on http://code.activestate.com/recipes/305288-http-basic-authentication
        def _urlopen_basic_auth(url, **kwargs):
            self.info("We want to download this file %s" % url)
            if not hasattr(self, "https_username"):
                self.info("NOTICE: Files downloaded from outside of "
                          "Release Engineering network require LDAP "
                          "credentials.")

            self.https_username, self.https_password = get_credentials()
            # This creates a password manager
            passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            # Because we have put None at the start it will use this username/password combination from here on
            passman.add_password(None, url, self.https_username, self.https_password)
            authhandler = urllib2.HTTPBasicAuthHandler(passman)

            return urllib2.build_opener(authhandler).open(url, **kwargs)

        # If we have the developer_run flag enabled then we will switch
        # URLs to the right place and enable http authentication
        if "developer_config.py" in self.config["config_files"]:
            return _urlopen_basic_auth(url, **kwargs)
        else:
            return urllib2.urlopen(url, **kwargs)

    # read_buildbot_config is in BuildbotMixin.

    def postflight_read_buildbot_config(self):
        """
        Determine which files to download from the buildprops.json file
        created via the buildbot ScriptFactory.
        """
        if self.buildbot_config:
            c = self.config
            message = "Unable to set %s from the buildbot config"
            if c.get("installer_url"):
                self.installer_url = c['installer_url']
            if c.get("test_url"):
                self.test_url = c['test_url']
            try:
                files = self.buildbot_config['sourcestamp']['changes'][-1]['files']
                buildbot_prop_branch = self.buildbot_config['properties']['branch']

                # Bug 868490 - Only require exactly two files if require_test_zip;
                # otherwise accept either 1 or 2, since we'll be getting a
                # test_zip url that we don't need.
                expected_length = [1, 2, 3]
                if c.get("require_test_zip") and not self.test_url:
                    expected_length = [2, 3]
                if buildbot_prop_branch.startswith('gaia-try'):
                    expected_length = range(1, 1000)
                actual_length = len(files)
                if actual_length not in expected_length:
                    self.fatal("Unexpected number of files in buildbot config %s.\nExpected these number(s) of files: %s, but got: %d" %
                               (c['buildbot_json_path'], str(expected_length), actual_length))
                for f in files:
                    if f['name'].endswith('tests.zip'):  # yuk
                        if not self.test_url:
                            # str() because of unicode issues on mac
                            self.test_url = str(f['name'])
                            self.info("Found test url %s." % self.test_url)
                    elif f['name'].endswith('crashreporter-symbols.zip'):  # yuk
                        self.symbols_url = str(f['name'])
                        self.info("Found symbols url %s." % self.symbols_url)
                    else:
                        if not self.installer_url:
                            self.installer_url = str(f['name'])
                            self.info("Found installer url %s." % self.installer_url)
            except IndexError:
                if c.get("require_test_zip"):
                    message = message % ("installer_url+test_url")
                else:
                    message = message % ("installer_url")
            missing = []
            if not self.installer_url:
                missing.append("installer_url")
            if c.get("require_test_zip") and not self.test_url:
                missing.append("test_url")
            if missing:
                self.fatal("%s!" % (message % ('+'.join(missing))))
        else:
            self.fatal("self.buildbot_config isn't set after running read_buildbot_config!")

    def _query_binary_version(self, regex, cmd):
        output = self.get_output_from_command(cmd, silent=False)
        return regex.search(output).group(0)

    def preflight_download_and_extract(self):
        message = ""
        if not self.installer_url:
            message += """installer_url isn't set!

You can set this by:

1. specifying --installer-url URL, or
2. running via buildbot and running the read-buildbot-config action

"""
        if self.config.get("require_test_zip") and not self.test_url:
            message += """test_url isn't set!

You can set this by:

1. specifying --test-url URL, or
2. running via buildbot and running the read-buildbot-config action

"""
        if message:
            self.fatal(message + "Can't run download-and-extract... exiting")

        if self.config.get("developer_mode") and self._is_darwin():
            # Bug 1066700 only affects Mac users that try to run mozharness locally
            version = self._query_binary_version(
                    regex=re.compile("UnZip\ (\d+\.\d+)\ .*",re.MULTILINE),
                    cmd=[self.query_exe('unzip'), '-v']
            )
            if not version >= 6:
                self.fatal("We require a more recent version of unzip to unpack our tests.zip files.\n" \
                        "You are currently using version %s. Please update to at least 6.0.\n" \
                        "You can visit http://www.info-zip.org/UnZip.html" % version)

    def _download_test_zip(self):
        dirs = self.query_abs_dirs()
        file_name = None
        if self.test_zip_path:
            file_name = self.test_zip_path
        # try to use our proxxy servers
        # create a proxxy object and get the binaries from it
        source = self.download_file(self.test_url, file_name=file_name,
                                            parent_dir=dirs['abs_work_dir'],
                                            error_level=FATAL)
        self.test_zip_path = os.path.realpath(source)

    def _download_unzip(self, url, parent_dir):
        """Generic download+unzip.
        This is hardcoded to halt on failure.
        We should probably change some other methods to call this."""
        dirs = self.query_abs_dirs()
        zipfile = self.download_file(url, parent_dir=dirs['abs_work_dir'],
                                             error_level=FATAL)
        command = self.query_exe('unzip', return_type='list')
        command.extend(['-q', '-o', zipfile])
        self.run_command(command, cwd=parent_dir, halt_on_failure=True,
                         fatal_exit_code=3, output_timeout=1760)

    def _extract_test_zip(self, target_unzip_dirs=None):
        dirs = self.query_abs_dirs()
        unzip = self.query_exe("unzip")
        test_install_dir = dirs.get('abs_test_install_dir',
                                    os.path.join(dirs['abs_work_dir'], 'tests'))
        self.mkdir_p(test_install_dir)
        # adding overwrite flag otherwise subprocess.Popen hangs on waiting for
        # input in a hidden pipe whenever this action is run twice without
        # clobber
        unzip_cmd = [unzip, '-q', '-o', self.test_zip_path]
        if target_unzip_dirs:
            unzip_cmd.extend(target_unzip_dirs)
        # TODO error_list
        # unzip return code 11 is 'no matching files were found'
        self.run_command(unzip_cmd, cwd=test_install_dir,
                         halt_on_failure=True, success_codes=[0, 11],
                         fatal_exit_code=3)

    def _read_tree_config(self):
        """Reads an in-tree config file"""
        dirs = self.query_abs_dirs()
        test_install_dir = dirs.get('abs_test_install_dir',
                                    os.path.join(dirs['abs_work_dir'], 'tests'))

        if 'in_tree_config' in self.config:
            rel_tree_config_path = self.config['in_tree_config']
            tree_config_path = os.path.join(test_install_dir, rel_tree_config_path)

            if not os.path.isfile(tree_config_path):
                self.fatal("The in-tree configuration file '%s' does not exist!"
                           "It must be added to '%s'. See bug 1035551 for more details." %
                           (tree_config_path, os.path.join('gecko', 'testing', rel_tree_config_path)))

            try:
                self.tree_config.update(parse_config_file(tree_config_path))
            except:
                msg = "There was a problem parsing the in-tree configuration file '%s'!" % \
                      os.path.join('gecko', 'testing', rel_tree_config_path)
                self.exception(message=msg, level=FATAL)

            self.dump_config(file_path=os.path.join(dirs['abs_log_dir'], 'treeconfig.json'),
                             config=self.tree_config)
        self.tree_config.lock()

    def structured_output(self, suite_category):
        """Defines whether structured logging is in use in this configuration. This
        may need to be replaced with data from a different config at the resolution
        of bug 1070041 and related bugs.
        """
        return ('structured_suites' in self.tree_config and
                suite_category in self.tree_config['structured_suites'])

    def get_test_output_parser(self, suite_category, strict=False,
                               fallback_parser_class=DesktopUnittestOutputParser,
                               **kwargs):
        """Derive and return an appropriate output parser, either the structured
        output parser or a fallback based on the type of logging in use as determined by
        configuration.
        """
        if not self.structured_output(suite_category):
            if fallback_parser_class is DesktopUnittestOutputParser:
                return DesktopUnittestOutputParser(suite_category=suite_category, **kwargs)
            return fallback_parser_class(**kwargs)
        self.info("Structured output parser in use for %s." % suite_category)
        return StructuredOutputParser(suite_category=suite_category, strict=strict, **kwargs)

    def _download_installer(self):
        file_name = None
        if self.installer_path:
            file_name = self.installer_path
        dirs = self.query_abs_dirs()
        source = self.download_file(self.installer_url,
                                            file_name=file_name,
                                            parent_dir=dirs['abs_work_dir'],
                                            error_level=FATAL)
        self.installer_path = os.path.realpath(source)
        self.set_buildbot_property("build_url", self.installer_url, write_to_file=True)

    def _download_and_extract_symbols(self):
        dirs = self.query_abs_dirs()
        self.symbols_url = self.query_symbols_url()
        if self.config.get('download_symbols') == 'ondemand':
            self.symbols_path = self.symbols_url
            return
        if not self.symbols_path:
            self.symbols_path = os.path.join(dirs['abs_work_dir'], 'symbols')
        self.mkdir_p(self.symbols_path)
        source = self.download_file(self.symbols_url,
                                            parent_dir=self.symbols_path,
                                            error_level=FATAL)
        self.set_buildbot_property("symbols_url", self.symbols_url,
                                   write_to_file=True)
        self.run_command(['unzip', '-q', source], cwd=self.symbols_path,
                         halt_on_failure=True, fatal_exit_code=3)

    def download_and_extract(self, target_unzip_dirs=None):
        """
        download and extract test zip / download installer
        """
        # Swap plain http for https when we're downloading from ftp
        # See bug 957502 and friends
        from_ = "http://ftp.mozilla.org"
        to_ = "https://ftp-ssl.mozilla.org"
        for attr in 'test_url', 'symbols_url', 'installer_url':
            url = getattr(self, attr)
            if url and url.startswith(from_):
                new_url = url.replace(from_, to_)
                self.info("Replacing url %s -> %s" % (url, new_url))
                setattr(self, attr, new_url)

        if self.test_url:
            self._download_test_zip()
            self._extract_test_zip(target_unzip_dirs=target_unzip_dirs)
            self._read_tree_config()
        self._download_installer()
        if self.config.get('download_symbols'):
            self._download_and_extract_symbols()

    # create_virtualenv is in VirtualenvMixin.

    def preflight_install(self):
        if not self.installer_path:
            if self.config.get('installer_path'):
                self.installer_path = self.config['installer_path']
            else:
                self.fatal("""installer_path isn't set!

You can set this by:

1. specifying --installer-path PATH, or
2. running the download-and-extract action
""")
        if not self.is_python_package_installed("mozInstall"):
            self.fatal("""Can't call install() without mozinstall!
Did you run with --create-virtualenv? Is mozinstall in virtualenv_modules?""")

    def install(self):
        """ Dependent on mozinstall """
        # install the application
        cmd = self.query_exe("mozinstall", default=self.query_python_path("mozinstall"), return_type="list")
        if self.config.get('application'):
            cmd.extend(['--app', self.config['application']])
        # Remove the below when we no longer need to support mozinstall 0.3
        self.info("Detecting whether we're running mozinstall >=1.0...")
        output = self.get_output_from_command(cmd + ['-h'])
        if '--source' in output:
            cmd.append('--source')
        # End remove
        dirs = self.query_abs_dirs()
        target_dir = dirs.get('abs_app_install_dir',
                              os.path.join(dirs['abs_work_dir'],
                              'application'))
        self.mkdir_p(target_dir)
        cmd.extend([self.installer_path,
                    '--destination', target_dir])
        # TODO we'll need some error checking here
        self.binary_path = self.get_output_from_command(cmd, halt_on_failure=True,
                                                        fatal_exit_code=3)

    def install_minidump_stackwalk(self):
        dirs = self.query_abs_dirs()

        if not os.path.isdir(os.path.join(dirs['abs_work_dir'], 'tools', 'breakpad')):
            # clone hg.m.o/build/tools
            repos = [{
                'repo': self.config.get('tools_repo') or self.default_tools_repo,
                'vcs': 'hg',
                'dest': os.path.join(dirs['abs_work_dir'], "tools")
            }]
            self.vcs_checkout(**repos[0])

    def query_minidump_stackwalk(self):
        if self.minidump_stackwalk_path:
            return self.minidump_stackwalk_path

        dirs = self.query_abs_dirs()
        env = self.query_env()
        if os.path.isdir(os.path.join(dirs['abs_work_dir'], 'tools', 'breakpad')):
            # find binary for platform/architecture
            path = os.path.join(dirs['abs_work_dir'], 'tools', 'breakpad', '%s', 'minidump_stackwalk')
            pltfrm = platform.platform().lower()
            arch = platform.architecture()
            if 'linux' in pltfrm:
                if '64' in arch:
                    self.minidump_stackwalk_path = path % 'linux64'
                else:
                    self.minidump_stackwalk_path = path % 'linux'
            elif any(s in pltfrm for s in ('mac', 'osx', 'darwin')):
                if '64' in arch:
                    self.minidump_stackwalk_path = path % 'osx64'
                else:
                    self.minidump_stackwalk_path = path % 'osx'
            elif 'win' in pltfrm:
                self.minidump_stackwalk_path = path % 'win32' + '.exe'
        elif os.path.isfile(env.get('MINIDUMP_STACKWALK', '')):
            self.minidump_stackwalk_path = env['MINIDUMP_STACKWALK']
        elif os.path.isfile(os.path.join(dirs['abs_work_dir'], 'minidump_stackwalk')):
            self.minidump_stackwalk_path = os.path.join(dirs['abs_work_dir'], 'minidump_stackwalk')

        return self.minidump_stackwalk_path

    def _run_cmd_checks(self, suites):
        if not suites:
            return
        dirs = self.query_abs_dirs()
        for suite in suites:
            # XXX platform.architecture() may give incorrect values for some
            # platforms like mac as excutable files may be universal
            # files containing multiple architectures
            # NOTE 'enabled' is only here while we have unconsolidated configs
            if not suite['enabled']:
                continue
            if suite.get('architectures'):
                arch = platform.architecture()[0]
                if arch not in suite['architectures']:
                    continue
            cmd = suite['cmd']
            name = suite['name']
            self.info("Running pre test command %(name)s with '%(cmd)s'"
                      % {'name': name, 'cmd': ' '.join(cmd)})
            if self.buildbot_config:  # this cmd is for buildbot
                # TODO rather then checking for formatting on every string
                # in every preflight enabled cmd: find a better solution!
                # maybe I can implement WithProperties in mozharness?
                cmd = [x % (self.buildbot_config.get('properties'))
                       for x in cmd]
            self.run_command(cmd,
                             cwd=dirs['abs_work_dir'],
                             error_list=BaseErrorList,
                             halt_on_failure=suite['halt_on_failure'],
                             fatal_exit_code=suite.get('fatal_exit_code', 3))

    def preflight_run_tests(self):
        """preflight commands for all tests"""
        # If the in tree config hasn't been loaded by a previous step, load it here.
        if len(self.tree_config) == 0:
            self._read_tree_config()

        c = self.config
        if c.get('run_cmd_checks_enabled'):
            self._run_cmd_checks(c.get('preflight_run_cmd_suites', []))
        elif c.get('preflight_run_cmd_suites'):
            self.warning("Proceeding without running prerun test commands."
                         " These are often OS specific and disabling them may"
                         " result in spurious test results!")

    def postflight_run_tests(self):
        """preflight commands for all tests"""
        c = self.config
        if c.get('run_cmd_checks_enabled'):
            self._run_cmd_checks(c.get('postflight_run_cmd_suites', []))
