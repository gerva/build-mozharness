#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****
"""desktop_l10n.py

This script manages Desktop repacks for nightly builds
"""
import os
import re
import sys

import subprocess
from copy import deepcopy

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.errors import BaseErrorList, MakefileErrorList
from mozharness.base.script import BaseScript
from mozharness.base.transfer import TransferMixin
from mozharness.base.vcs.vcsbase import VCSMixin
from mozharness.mozilla.buildbot import BuildbotMixin
from mozharness.mozilla.building.buildbase import MakeUploadOutputParser
from mozharness.mozilla.l10n.locales import LocalesMixin
from mozharness.mozilla.mar import MarMixin
from mozharness.mozilla.mock import MockMixin
from mozharness.mozilla.purge import PurgeMixin
from mozharness.mozilla.release import ReleaseMixin
from mozharness.mozilla.signing import MobileSigningMixin, SigningMixin
from mozharness.mozilla.updates.balrog import BalrogMixin

try:
    import simplejson as json
    assert json
except ImportError:
    import json


# when running get_output_form_command, pymake has some extra output
# that needs to be filtered out
PyMakeIgnoreList = [
    re.compile(r'''.*make\.py(?:\[\d+\])?: Entering directory'''),
    re.compile(r'''.*make\.py(?:\[\d+\])?: Leaving directory'''),
]


# DesktopSingleLocale {{{1
class DesktopSingleLocale(LocalesMixin, ReleaseMixin, MobileSigningMixin,
                          MockMixin, PurgeMixin, BuildbotMixin, TransferMixin,
                          VCSMixin, SigningMixin, BaseScript, BalrogMixin,
                          MarMixin):
    """Manages desktop repacks"""
    config_options = [[
        ['--locale', ],
        {"action": "extend",
         "dest": "locales",
         "type": "string",
         "help": "Specify the locale(s) to sign and update"}
    ], [
        ['--locales-file', ],
        {"action": "store",
         "dest": "locales_file",
         "type": "string",
         "help": "Specify a file to determine which locales to sign and update"}
    ], [
        ['--tag-override', ],
        {"action": "store",
         "dest": "tag_override",
         "type": "string",
         "help": "Override the tags set for all repos"}
    ], [
        ['--user-repo-override', ],
        {"action": "store",
         "dest": "user_repo_override",
         "type": "string",
         "help": "Override the user repo path for all repos"}
    ], [
        ['--release-config-file', ],
        {"action": "store",
         "dest": "release_config_file",
         "type": "string",
         "help": "Specify the release config file to use"}
    ], [
        ['--keystore', ],
        {"action": "store",
         "dest": "keystore",
         "type": "string",
         "help": "Specify the location of the signing keystore"}
    ], [
        ['--this-chunk', ],
        {"action": "store",
         "dest": "this_locale_chunk",
         "type": "int",
         "help": "Specify which chunk of locales to run"}
    ], [
        ['--total-chunks', ],
        {"action": "store",
         "dest": "total_locale_chunks",
         "type": "int",
         "help": "Specify the total number of chunks of locales"}
    ], [
        ['--partials-from', ],
        {"action": "store",
         "dest": "partials_from",
         "type": "string",
         "help": "Specify the total number of chunks of locales"}
    ]]

    def __init__(self, require_config_file=True):
        LocalesMixin.__init__(self)
        BaseScript.__init__(
            self,
            config_options=self.config_options,
            all_actions=[
                "clobber",
                "pull",
                "list-locales",
                "setup",
                "repack",
                "upload-repacks",
                "submit-to-balrog",
                "summary",
            ],
            require_config_file=require_config_file
        )
        self.buildid = None
        self.make_ident_output = None
        self.repack_env = None
        self.upload_env = None
        self.revision = None
        self.version = None
        self.upload_urls = {}
        self.locales_property = {}
        self.l10n_dir = None
        self.package_urls = {}
        if 'mock_target' in self.config:
            self.enable_mock()

    # Helper methods {{{2
    def query_repack_env(self):
        """returns the env for repacks"""
        if self.repack_env:
            return self.repack_env
        config = self.config
        replace_dict = self.query_abs_dirs()
        if config.get('release_config_file'):
            release_config = self.query_release_config()
            replace_dict['version'] = release_config['version']
            replace_dict['buildnum'] = release_config['buildnum']
        repack_env = self.query_env(partial_env=config.get("repack_env"),
                                    replace_dict=replace_dict)
        if config.get('base_en_us_binary_url') and \
           config.get('release_config_file'):
            binary_url = config['base_en_us_binary_url'] % replace_dict
            repack_env['EN_US_BINARY_URL'] = binary_url
        if 'MOZ_SIGNING_SERVERS' in os.environ:
            sign_cmd = self.query_moz_sign_cmd(formats=None)
            sign_cmd = subprocess.list2cmdline(sign_cmd)
            # windows fix
            repack_env['MOZ_SIGN_CMD'] = sign_cmd.replace('\\', '\\\\\\\\')
        for binary in self._mar_binaries():
            # "mar -> MAR" and 'mar.exe -> MAR' (windows)
            name = binary.replace('.exe', '')
            name = name.upper()
            binary_path = os.path.join(self._mar_tool_dir(), binary)
            # windows fix...
            binary_path.replace("\\", "/")
            repack_env[name] = binary_path

        self.repack_env = repack_env
        return self.repack_env

    def query_upload_env(self):
        if self.upload_env:
            return self.upload_env
        c = self.config
        buildid = self._query_buildid()
        version = self.query_version()
        upload_env = self.query_env(partial_env=c.get("upload_env"),
                                    replace_dict={'buildid': buildid,
                                                  'version': version})
        if 'MOZ_SIGNING_SERVERS' in os.environ:
            upload_env['MOZ_SIGN_CMD'] = subprocess.list2cmdline(self.query_moz_sign_cmd())
        self.upload_env = upload_env
        return self.upload_env

    def _query_make_ident_output(self):
        """Get |make ident| output from the objdir.
        Only valid after setup is run.
       """
        if self.make_ident_output:
            return self.make_ident_output
        dirs = self.query_abs_dirs()
        self.make_ident_output = self._get_output_from_make(
            target=["ident"],
            cwd=dirs['abs_locales_dir'],
            env=self.query_repack_env())
        return self.make_ident_output

    def _query_buildid(self):
        """Get buildid from the objdir.
        Only valid after setup is run.
       """
        if self.buildid:
            return self.buildid
        r = re.compile(r"buildid (\d+)")
        output = self._query_make_ident_output()
        for line in output.splitlines():
            match = r.match(line)
            if match:
                self.buildid = match.groups()[0]
        return self.buildid

    def query_revision(self):
        """Get revision from the objdir.
        Only valid after setup is run.
       """
        if self.revision:
            return self.revision
        r = re.compile(r"^(gecko|fx)_revision ([0-9a-f]{12}\+?)$")
        output = self._query_make_ident_output()
        for line in output.splitlines():
            match = r.match(line)
            if match:
                self.revision = match.groups()[1]
        return self.revision

    def _query_make_variable(self, variable, make_args=None,
                             exclude_lines=PyMakeIgnoreList):
        """returns the value of make echo-variable-<variable>
           it accepts extra make arguements (make_args)
           it also has an exclude_lines from the output filer
           exclude_lines defaults to PyMakeIgnoreList because
           on windows, pymake writes extra output lines that need
           to be filtered out.
        """
        dirs = self.query_abs_dirs()
        make_args = make_args or []
        exclude_lines = exclude_lines or []
        target = ["echo-variable-%s" % variable] + make_args
        cwd = dirs['abs_locales_dir']
        raw_output = self._get_output_from_make(target, cwd=cwd,
                                                env=self.query_repack_env())
        # we want to log all the messages from make/pymake and
        # exlcude some messages from the output ("Entering directory...")
        output = []
        for line in raw_output.split("\n"):
            discard = False
            for element in exclude_lines:
                if element.match(line):
                    discard = True
                    continue
            if not discard:
                output.append(line.strip())
        return " ".join(output).strip()

    def query_base_package_name(self, locale):
        """Gets the package name from the objdir.
        Only valid after setup is run.
        """
        # optimization:
        # replace locale with %(locale)s
        # and store its values.
        args = ['AB_CD=%s' % locale]
        return self._query_make_variable('PACKAGE', make_args=args)

    def query_version(self):
        """Gets the version from the objdir.
        Only valid after setup is run."""
        if self.version:
            return self.version
        config = self.config
        if config.get('release_config_file'):
            release_config = self.query_release_config()
            self.version = release_config['version']
        else:
            self.version = self._query_make_variable("MOZ_APP_VERSION")
        return self.version

    def upload_repacks(self):
        """iterates through the list of locales and calls make upload"""
        self.summarize(self.make_upload, self.query_locales())

    def summarize(self, func, items):
        """runs func for any item in items, calls the add_failure() for each
           error. It assumes that function returns 0 when successful.
           returns a two element tuple with (success_count, total_count)"""
        success_count = 0
        total_count = len(items)
        name = func.__name__
        for item in items:
            result = func(item)
            if result == 0:
                #  success!
                success_count += 1
            else:
                #  func failed...
                message = 'failure: %s(%s)' % (name, item)
                self._add_failure(item, message)
        return (success_count, total_count)

    def _add_failure(self, locale, message, **kwargs):
        self.locales_property[locale] = "Failed"
        prop_key = "%s_failure" % locale
        prop_value = self.query_buildbot_property(prop_key)
        if prop_value:
            prop_value = "%s  %s" % (prop_value, message)
        else:
            prop_value = message
        self.set_buildbot_property(prop_key, prop_value, write_to_file=True)
        BaseScript.add_failure(self, locale, message=message, **kwargs)

    def summary(self):
        """generates a summary"""
        BaseScript.summary(self)
        # TODO we probably want to make this configurable on/off
        locales = self.query_locales()
        for locale in locales:
            self.locales_property.setdefault(locale, "Success")
        self.set_buildbot_property("locales",
                                   json.dumps(self.locales_property),
                                   write_to_file=True)

    # Actions {{{2
    def clobber(self):
        """clobber"""
        self.read_buildbot_config()
        dirs = self.query_abs_dirs()
        config = self.config
        objdir = os.path.join(dirs['abs_work_dir'], config['mozilla_dir'],
                              config['objdir'])
        PurgeMixin.clobber(self, always_clobber_dirs=[objdir])

    def pull(self):
        """pulls source code"""
        config = self.config
        dirs = self.query_abs_dirs()
        repos = []
        replace_dict = {}
        if config.get("user_repo_override"):
            replace_dict['user_repo_override'] = config['user_repo_override']
            # deepcopy() needed because of self.config lock bug :(
            for repo_dict in deepcopy(config['repos']):
                repo_dict['repo'] = repo_dict['repo'] % replace_dict
                repos.append(repo_dict)
        else:
            repos = config['repos']
        self.vcs_checkout_repos(repos, parent_dir=dirs['abs_work_dir'],
                                tag_override=config.get('tag_override'))
        self.pull_locale_source()

    def _setup_configure(self, buildid=None):
        """configuration setup"""
        if self._make_configure():
            self.fatal("Configure failed!")
        if self._make_dirs():
            self.fatal("make dir failed!")
        # do we need it?
        if self.make_export(buildid):
            self.fatal("make export failed!")

    def setup(self):
        """setup step"""
        dirs = self.query_abs_dirs()
        self._copy_mozconfig()
        self._setup_configure()
        self.make_wget_en_US()
        self.make_unpack()
        revision = self.query_revision()
        if not revision:
            self.fatal("Can't determine revision!")
        #  TODO do this through VCSMixin instead of hardcoding hg
        #  self.update(dest=dirs["abs_mozilla_dir"], revision=revision)
        hg = self.query_exe("hg")
        self.run_command([hg, "update", "-r", revision],
                         cwd=dirs["abs_mozilla_dir"],
                         env=self.query_repack_env(),
                         error_list=BaseErrorList,
                         halt_on_failure=True, fatal_exit_code=3)
        # if checkout updates CLOBBER file with a newer timestamp,
        # next make -f client.mk configure  will delete archives
        # downloaded with make wget_en_US, so just touch CLOBBER file
        _clobber_file = self._clobber_file()
        if os.path.exists(_clobber_file):
            self._touch_file(_clobber_file)
        # Configure again since the hg update may have invalidated it.
        buildid = self._query_buildid()
        self._setup_configure(buildid=buildid)

    def _clobber_file(self):
        """returns the full path of the clobber file"""
        config = self.config
        dirs = self.query_abs_dirs()
        return os.path.join(dirs['abs_objdir'], config.get('clobber_file'))

    def _copy_mozconfig(self):
        """copies the mozconfig file into abs_mozilla_dir/.mozconfig
           and logs the content
        """
        config = self.config
        dirs = self.query_abs_dirs()
        src = os.path.join(dirs['abs_work_dir'], config['mozconfig'])
        dst = os.path.join(dirs['abs_mozilla_dir'], '.mozconfig')
        self.copyfile(src, dst)

        # STUPID HACK HERE
        # should we update the mozconfig so it has the right value?
        with self.opened(src, 'r') as (in_mozconfig, in_error):
            if in_error:
                self.fatal('cannot open {0}'.format(src))
            with self.opened(dst, open_mode='w') as (out_mozconfig, out_error):
                if out_error:
                    self.fatal('cannot write {0}'.format(dst))
                for line in in_mozconfig:
                    if 'with-l10n-base' in line:
                        line = 'ac_add_options --with-l10n-base=../../l10n\n'
                        self.l10n_dir = line.partition('=')[2].strip()
                    out_mozconfig.write(line)
        # now log
        with self.opened(dst, 'r') as (mozconfig, in_error):
            if in_error:
                self.fatal('cannot open {0}'.format(dst))
            for line in mozconfig:
                self.info(line.strip())

    def _make(self, target, cwd, env, error_list=MakefileErrorList,
              halt_on_failure=True, output_parser=None):
        """Runs make. Returns the exit code"""
        make = self.query_exe("make", return_type="list")
        self.info("**** target: {0}".format(target))
        self.info("**** cwd: {0}".format(cwd))
        self.info("**** env: {0}".format(env))
        return self.run_command(make + target,
                                cwd=cwd,
                                env=env,
                                error_list=error_list,
                                halt_on_failure=halt_on_failure,
                                output_parser=output_parser)

    def _get_output_from_make(self, target, cwd, env, halt_on_failure=True):
        """runs make and returns the output of the command"""
        make = self.query_exe("make", return_type="list")
        return self.get_output_from_command(make + target,
                                            cwd=cwd,
                                            env=env,
                                            silent=True,
                                            halt_on_failure=halt_on_failure)

    def _make_configure(self):
        """calls make -f client.mk configure"""
        env = self.query_repack_env()
        dirs = self.query_abs_dirs()
        cwd = dirs['abs_mozilla_dir']
        target = ["-f", "client.mk", "configure"]
        return self._make(target=target, cwd=cwd, env=env)

    def _make_dirs(self):
        """calls make <dirs>
           dirs is defined in configuration"""
        config = self.config
        env = self.query_repack_env()
        dirs = self.query_abs_dirs()
        target = []
        for make_dir in config.get('make_dirs', []):
            cwd = os.path.join(dirs['abs_objdir'], make_dir)
            self._make(target=target, cwd=cwd, env=env, halt_on_failure=True)

    def make_export(self, buildid):
        """calls make export <buildid>"""
        #  is it really needed ???
        if buildid is None:
            return
        dirs = self.query_abs_dirs()
        cwd = dirs['abs_locales_dir']
        env = self.query_repack_env()
        target = ["export", 'MOZ_BUILD_DATE=%s' % str(buildid)]
        return self._make(target=target, cwd=cwd, env=env)

    def make_unpack(self):
        """wrapper for make unpack"""
        config = self.config
        dirs = self.query_abs_dirs()
        env = self.query_repack_env()
        cwd = os.path.join(dirs['abs_objdir'], config['locales_dir'])
        return self._make(target=["unpack"], cwd=cwd, env=env)

    def make_wget_en_US(self):
        """wrapper for make wget-en-US"""
        env = self.query_repack_env()
        dirs = self.query_abs_dirs()
        cwd = dirs['abs_locales_dir']
        return self._make(target=["wget-en-US"], cwd=cwd, env=env)

    def _get_installer_file_path(self):
        config = self.config
        version = self.query_version()
        installer_file = config['installer_file'] % {'version': version}
        return os.path.join(self._abs_dist_dir(), installer_file)

    def _get_installer_local_copy(self):
        config = self.config
        version = self.query_version()
        installer_file = config['installer_file'] % {'version': version}
        return os.path.join(self._abs_dist_dir(), 'tmp', installer_file)

    def make_upload(self, locale):
        """wrapper for make upload command"""
        config = self.config
        env = self.query_upload_env()
        dirs = self.query_abs_dirs()
        buildid = self._query_buildid()
        try:
            env['POST_UPLOAD_CMD'] = config['base_post_upload_cmd'] % {'buildid': buildid}
        except KeyError:
            # no base_post_upload_cmd in configuration, just skip it
            pass
        target = ['upload', 'AB_CD=%s' % (locale)]
        cwd = dirs['abs_locales_dir']
        parser = MakeUploadOutputParser(config=self.config,
                                        log_obj=self.log_obj)
        retval = self._make(target=target, cwd=cwd, env=env,
                            halt_on_failure=False, output_parser=parser)
        if locale not in self.package_urls:
            self.package_urls[locale] = parser.matches
        else:
            self.package_urls[locale].update(parser.matches)
        self.info("parser: %s" % parser)
        self.info("parser matches: %s" % parser.matches)
        if retval != 0:
            self.error('failed to upload %s' % (locale))
        else:
            self.info('Upload successful (%s)' % (locale))
        return retval

    def make_installers(self, locale):
        """wrapper for make installers-(locale)"""
        # TODO... don't download the same file again, store it locally
        # and move it again where make_installer expects it
        env = self.query_repack_env()
        self._copy_mozconfig()
        env['L10NBASEDIR'] = self.l10n_dir
        # make.py: error: l10n-base required when using locale-mergedir
        # adding a replace(...) because make.py doesn't like
        # --locale-mergedir=e:\...\...\...
        # replacing \ with /
        # this kind of hacks makes me sad
        # env['LOCALE_MERGEDIR'] = env['LOCALE_MERGEDIR'].replace("\\", "/")
        dirs = self.query_abs_dirs()
        cwd = os.path.join(dirs['abs_locales_dir'])
        cmd = ["installers-%s" % locale,
               "LOCALE_MERGEDIR=%s" % env["LOCALE_MERGEDIR"], ]
        return self._make(target=cmd, cwd=cwd,
                          env=env, halt_on_failure=False)

    def generate_complete_mar(self, locale):
        """creates a complete mar file"""
        config = self.config
        dirs = self.query_abs_dirs()
        self._create_mar_dirs()
        self.download_mar_tools()
        package_basedir = os.path.join(dirs['abs_objdir'],
                                       config['package_base_dir'])
        env = self.query_repack_env()
        cmd = os.path.join(dirs['abs_objdir'], config['update_packaging_dir'])
        cmd = ['-C', cmd, 'full-update', 'AB_CD=%s' % locale,
               'PACKAGE_BASE_DIR=%s' % package_basedir]
        return self._make(target=cmd, cwd=dirs['abs_mozilla_dir'], env=env)

    def repack_locale(self, locale):
        """wraps the logic for comapare locale, make installers and generate
           partials"""
        self.info("========================")
        self.info("========================")
        self.info("base package name: %s" % (self.query_base_package_name(locale)))
        self.info("========================")
        self.info("========================")
        if self.run_compare_locales(locale) != 0:
            self.error("compare locale %s failed" % (locale))
            return

        if self.make_installers(locale) != 0:
            self.error("make installers-%s failed" % (locale))
            return

        if self.generate_complete_mar(locale) != 0:
            self.error("generate complete %s mar failed" % (locale))
            return

        if self.generate_partials(locale) != 0:
            self.error("generate partials %s failed" % (locale))
            return
        return 0

    def repack(self):
        """creates the repacks and udpates"""
        self.summarize(self.repack_locale, self.query_locales())

    def localized_marfile(self, locale):
        config = self.config
        version = self.query_version()
        localized_mar = config['localized_mar'] % {'version': version,
                                                   'locale': locale}
        localized_mar = os.path.join(self._mar_dir('update_mar_dir'),
                                     localized_mar)
        return localized_mar

    def create_partial_updates(self, locale):
        # clean up any left overs from previous locales
        # remove current/ current.work/ previous/ directories
        self._delete_mar_dirs()
        # and recreate current/ previous/
        self._create_mar_dirs()
        # download mar and mbsdiff executables
        self.download_mar_tools()
        # get the previous mar file
        previous_marfile = self._get_previous_mar(locale)
        # and unpack it
        previous_mar_dir = self._previous_mar_dir()
        result = self._unpack_mar(previous_marfile, previous_mar_dir, prettynames=1)
        if result != 0:
            self.error('failed to unpack %s to %s' % (previous_marfile,
                                                      previous_mar_dir))
            return result

        current_marfile = self._get_current_mar()
        current_mar_dir = self._current_mar_dir()
        result = self._unpack_mar(current_marfile, current_mar_dir, prettynames=1)
        if result != 0:
            self.error('failed to unpack %s to %s' % (current_marfile,
                                                      current_mar_dir))
            return result
        # partial filename
        config = self.config
        version = self.query_version()
        previous_mar_buildid = self.query_build_id(previous_mar_dir, prettynames=1)
        current_mar_buildid = self._query_buildid()
        partial_filename = config['partial_mar'] % {'version': version,
                                                    'locale': locale,
                                                    'from_buildid': current_mar_buildid,
                                                    'to_buildid': previous_mar_buildid}
        if locale not in self.package_urls:
            self.package_urls[locale] = {}
        self.package_urls[locale]['partial_filename'] = partial_filename
        self.package_urls[locale]['previous_buildid'] = previous_mar_buildid
        self._delete_pgc_files()
        return self.do_incremental_update(previous_mar_dir, current_mar_dir,
                                          partial_filename, prettynames=0)

    def generate_partials(self, locale):
        """generate partial files"""
        return self.create_partial_updates(locale)

    def _query_objdir(self):
        if self.objdir:
            return self.objdir

        self.objdir = self.config['objdir']
        return self.objdir

    def query_abs_dirs(self):
        if self.abs_dirs:
            return self.abs_dirs
        abs_dirs = super(DesktopSingleLocale, self).query_abs_dirs()
        dirs = {}
        dirs['abs_tools_dir'] = os.path.join(abs_dirs['abs_work_dir'], 'tools')

        for key in dirs.keys():
            if key not in abs_dirs:
                abs_dirs[key] = dirs[key]
        self.abs_dirs = abs_dirs
        return self.abs_dirs

    def submit_to_balrog(self):
        """submit to barlog"""
        # we need some properties from buildbot e.g. platform
        self.read_buildbot_config()
        self.summarize(self.submit_locale_to_balrog, self.query_locales())

    def submit_locale_to_balrog(self, locale):
        """submit a single locale to balrog"""
        if not self.query_is_nightly():
            self.info("Not a nightly build")
            # extra safe
            # return

        if not self.config.get("balrog_api_root"):
            self.info("balrog_api_root not set; skipping balrog submission.")
            return

        # complete mar file
        config = self.config
        c_marfile = self._query_complete_mar_filename(locale)
        c_mar_url = self._query_complete_mar_url(locale)

        # partial mar file
        p_marfile = self._query_partial_mar_filename(locale)
        p_mar_url = self._query_previous_mar_buildid(locale)
        p_buildid = self._query_previous_mar_buildid(locale)

        # get platform, appName and hashType from configuration
        platform = config["platform"]
        appName = config['appName']
        hashType = config['hashType']

        # try to read buildbot props, if any
        self.info("Reading buildbot build properties...")
        self.read_buildbot_config()

        try:
            properties = self.query_buildbot_property("properties")
        except AttributeError:
            # no properties set for buildbot, initialize to empty dict
            self.buildbot_properties = {}

#        self.info(" ****** buildbot properties: {0}".format(properties))
        # balrog submitter requires buildbot['properties']['product']
        # if it does not exist the submission will fail.
        # set it to "Firefox" if does not exist
        if not properties or ('product' not in properties):
            # do not hard code it, read from configuration
            properties = {"product": "Firefox"}
            self.set_buildbot_property('properties', properties)

        # Set other necessary properties for Balrog submission. None need to
        # be passed back to buildbot, so we won't write them to the properties
        # files
        # Locale is hardcoded to en-US, for silly reasons
        self.set_buildbot_property("locale", "en-US")
        self.set_buildbot_property("appVersion", self.query_version())
        # The Balrog submitter translates this platform into a build target
        # via https://github.com/mozilla/build-tools/blob/master/lib/python/release/platforms.py#L23
        self.set_buildbot_property("platform", platform)
        self.set_buildbot_property("appName", appName)
        self.set_buildbot_property("buildid", self._query_buildid())
        self.set_buildbot_property("previous_buildid", p_buildid)
        self.set_buildbot_property("hashType", hashType)
        self.set_buildbot_property("completeMarSize", self.query_filesize(c_marfile))
        self.set_buildbot_property("completeMarHash", self.query_sha512sum(c_marfile))
        self.set_buildbot_property("completeMarUrl", c_mar_url)
        self.set_buildbot_property("partialMarSize", self.query_filesize(p_marfile))
        self.set_buildbot_property("partialMarHash", self.query_sha512sum(p_marfile))
        self.set_buildbot_property("partialMarUrl", p_mar_url)
        self.set_buildbot_property("locale", locale)

        result = 0
        try:
            self.submit_balrog_updates()
        except Exception as error:
            self.error("submit to balrog failed: %s" % (str(error)))
            result = 1
        return result

    def _query_complete_mar_filename(self, locale):
        """returns the full path to a localized complete mar file"""
        config = self.config
        version = self.query_version()
        complete_mar_name = config['localized_mar'] % {'version': version,
                                                       'locale': locale}
        return os.path.join(self._update_mar_dir(), complete_mar_name)

    def _query_complete_mar_url(self, locale):
        """returns the complete mar url taken from self.package_urls[locale]
           this value is available only after make_upload"""
        if "complete_mar_url" in self.config:
            return self.config["complete_mar_url"]
        if "completeMarUrl" in self.package_urls[locale]:
            return self.package_urls[locale]["completeMarUrl"]
        # XXX: remove this after everything is uploading publicly
        url = self.config.get("update", {}).get("mar_base_url")
        if url:
            url += os.path.basename(self.query_marfile_path())
            return url.format(branch=self.query_branch())
        self.fatal("Couldn't find complete mar url in config or package_urls")

    def _query_partial_mar_filename(self, locale):
        """returns the full path to a partial, it returns a valid path only
           after make upload"""
        partial_mar_name = self.package_urls[locale]['partial_filename']
        return os.path.join(self._update_mar_dir(), partial_mar_name)

    def _query_previous_mar_buildid2(self, locale):
        """returns the partial mar upload url. This is valid only after
           make upload"""
        if "partial_mar_url" in self.config:
            return self.config["complete_mar_url"]
        if "partialMarUrl" in self.package_urls[locale]:
            return self.package_urls[locale]["partialMarUrl"]
        # XXX: remove this after everything is uploading publicly
        url = self.config.get("update", {}).get("mar_base_url")
        if url:
            url += os.path.basename(self.query_marfile_path())
            return url.format(branch=self.query_branch())
        self.fatal("Couldn't find complete mar url in config or package_urls")

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

    def _delete_pgc_files(self):
        """deletes pgc files"""
        for directory in (self._previous_mar_dir(),
                          self._current_mar_dir()):
            for pcg_file in self._pgc_files(directory):
                self.info("removing %s" % pcg_file)
                self.rmtree(pcg_file)

    def _current_mar_url(self):
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

    def _get_previous_mar(self, locale):
        """downloads the previous mar file"""
        self.mkdir_p(self._previous_mar_dir())
        self.download_file(self._previous_mar_url(locale),
                           self._previous_mar_filename())
        return self._previous_mar_filename()

    def _current_mar_name(self):
        config = self.config
        version = self.query_version()
        return config["current_mar_filename"] % {'version': version}

    def _localized_mar_name(self, locale):
        """returns localized mar name"""
        config = self.config
        version = self.query_version()
        return config["localized_mar"] % {'version': version, 'locale': locale}

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

    def _mar_tool_dir(self):
        """full path to the tools/ directory"""
        config = self.config
        dirs = self.query_abs_dirs()
        return os.path.join(dirs['abs_objdir'], config["local_mar_tool_dir"])

    def _incremental_update_script(self):
        """incremental update script"""
        config = self.config
        dirs = self.query_abs_dirs()
        return os.path.join(dirs['abs_mozilla_dir'],
                            config['incremental_update_script'])

    def _unpack_script(self):
        """unpack script full path"""
        config = self.config
        dirs = self.query_abs_dirs()
        return os.path.join(dirs['abs_mozilla_dir'], config['unpack_script'])

    def _previous_mar_dir(self):
        """returns the full path of the previous/ directory"""
        return self._mar_dir('previous_mar_dir')

    def _abs_dist_dir(self):
        """returns the full path to abs_objdir/dst"""
        dirs = self.query_abs_dirs()
        return os.path.join(dirs['abs_objdir'], 'dist')

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
        return os.path.join(self._get_objdir(), config.get(dirname))

    def _get_objdir(self):
        """returns full path to objdir"""
        dirs = self.query_abs_dirs()
        return dirs['abs_objdir']

    def _pgc_files(self, basedir):
        """returns a list of .pcf files in basedir"""
        pgc_files = []
        for dirpath, dirnames, filenames in os.walk(basedir):
            for pgc in filenames:
                if pgc.endswith('.pgc'):
                    pgc_files.append(os.path.join(dirpath, pgc))
        return pgc_files


# main {{{
if __name__ == '__main__':
    single_locale = DesktopSingleLocale()
    single_locale.run_and_exit()
