#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****
"""desktop_l10n.py

Firefox repacks
"""

from copy import deepcopy
import os
import re
import subprocess
import sys
import tempfile
import ConfigParser

try:
    import simplejson as json
    assert json
except ImportError:
    import json

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.log import OutputParser
from mozharness.base.transfer import TransferMixin
from mozharness.base.errors import BaseErrorList, MakefileErrorList
from mozharness.mozilla.release import ReleaseMixin
from mozharness.mozilla.signing import MobileSigningMixin
from mozharness.mozilla.signing import SigningMixin
from mozharness.base.vcs.vcsbase import VCSMixin
from mozharness.mozilla.l10n.locales import LocalesMixin
from mozharness.mozilla.buildbot import BuildbotMixin
from mozharness.mozilla.purge import PurgeMixin
from mozharness.mozilla.mock import MockMixin
from mozharness.base.script import BaseScript

# when running get_output_form_command, pymake has some extra output
# that needs to be filtered out
PyMakeIgnoreList = [
    re.compile(r'''.*make\.py(?:\[\d+\])?: Entering directory'''),
    re.compile(r'''.*make\.py(?:\[\d+\])?: Leaving directory'''),
]


# DesktopSingleLocale {{{1
class DesktopSingleLocale(LocalesMixin, ReleaseMixin, MobileSigningMixin,
                          MockMixin, PurgeMixin, BuildbotMixin, TransferMixin,
                          VCSMixin, SigningMixin, BaseScript):
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
                "generate-complete-mar",
                "generate-partials",
                "create-nightly-snippets",
                "upload-nightly-repacks",
                "upload-snippets",
                "summary",
            ],
            require_config_file=require_config_file
        )
        self.base_package_name = None
        self.buildid = None
        self.make_ident_output = None
        self.repack_env = None
        self.complete_mar_env = None
        self.upload_env = None
        self.revision = None
        self.upload_env = None
        self.version = None
        self.latest_version = None
        self.upload_urls = {}
        self.locales_property = {}

        if 'mock_target' in self.config:
            self.enable_mock()

    # Helper methods {{{2
    def query_repack_env(self):
        """returns the env for repacks"""
        if self.repack_env:
            return self.repack_env
        c = self.config
        replace_dict = {}
        if c.get('release_config_file'):
            rc = self.query_release_config()
            replace_dict = {
                'version': rc['version'],
                'buildnum': rc['buildnum']
            }
        repack_env = self.query_env(partial_env=c.get("repack_env"),
                                    replace_dict=replace_dict)
        if c.get('base_en_us_binary_url') and c.get('release_config_file'):
            rc = self.query_release_config()
            binary_url = c['base_en_us_binary_url'] % replace_dict
            repack_env['EN_US_BINARY_URL'] = binary_url
        if 'MOZ_SIGNING_SERVERS' in os.environ:
            sign_cmd = self.query_moz_sign_cmd(formats=None)
            sign_cmd = subprocess.list2cmdline(sign_cmd)
            repack_env['MOZ_SIGN_CMD'] = sign_cmd
        self.repack_env = repack_env
        return self.repack_env

    def query_complete_mar_env(self):
        if self.complete_mar_env:
            return self.complete_mar_env
        c = self.config
        replace_dict = self.query_abs_dirs()
        replace_dict['buildid'] = self.query_buildid()
        replace_dict['version'] = self.query_version()
        complete_mar_env = self.query_env(partial_env=c.get("upload_env"),
                                          replace_dict=replace_dict)
        self.complete_mar_env = complete_mar_env
        return self.complete_mar_env

    def query_upload_env(self):
        if self.upload_env:
            return self.upload_env
        c = self.config
        buildid = self.query_buildid()
        version = self.query_version()
        upload_env = self.query_env(partial_env=c.get("upload_env"),
                                    replace_dict={'buildid': buildid,
                                                  'version': version})
        if 'MOZ_SIGNING_SERVERS' in os.environ:
            upload_env['MOZ_SIGN_CMD'] = subprocess.list2cmdline(self.query_moz_sign_cmd(formats=None))
        self.upload_env = upload_env
        return self.upload_env

    def _query_make_ident_output(self):
        """Get |make ident| output from the objdir.
        Only valid after setup is run.
       """
        if self.make_ident_output:
            return self.make_ident_output
        env = self.query_repack_env()
        dirs = self.query_abs_dirs()
        make = self.query_exe("make", return_type="list")
        output = self.get_output_from_command(make + ["ident"],
                                              cwd=dirs['abs_locales_dir'],
                                              env=env,
                                              silent=True,
                                              halt_on_failure=True)
        parser = OutputParser(config=self.config, log_obj=self.log_obj,
                              error_list=MakefileErrorList)
        parser.add_lines(output)
        self.make_ident_output = output
        return output

    def query_buildid(self):
        """Get buildid from the objdir.
        Only valid after setup is run.
       """
        if self.buildid:
            return self.buildid
        r = re.compile("buildid (\d+)")
        output = self._query_make_ident_output()
        for line in output.splitlines():
            m = r.match(line)
            if m:
                self.buildid = m.groups()[0]
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
            m = r.match(line)
            if m:
                self.revision = m.groups()[1]
        return self.revision

    def _query_make_variable(self, variable, make_args=None, exclude_lines=[]):
        make = self.query_exe('make', return_type="list")
        env = self.query_repack_env()
        dirs = self.query_abs_dirs()
        make_args = make_args or []
        # TODO error checking
        raw_output = self.get_output_from_command(
            make + ["echo-variable-%s" % variable] + make_args,
            cwd=dirs['abs_locales_dir'],
            silent=True,
            env=env
        )
        # we want to log all the messages from make/pymake and
        # exlcude some messages from the output ("Entering directory...")
        parser = OutputParser(config=self.config, log_obj=self.log_obj,
                              error_list=MakefileErrorList)
        parser.add_lines(raw_output)
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

    def query_base_package_name(self):
        """Get the package name from the objdir.
        Only valid after setup is run.
       """
        if self.base_package_name:
            return self.base_package_name
        self.base_package_name = self._query_make_variable(
            "PACKAGE",
            make_args=['AB_CD=%(locale)s'],
            exclude_lines=PyMakeIgnoreList,)
        return self.base_package_name

    def query_version(self):
        """Get the package name from the objdir.
        Only valid after setup is run.
       """
        if self.version:
            return self.version
        c = self.config
        if c.get('release_config_file'):
            rc = self.query_release_config()
            self.version = rc['version']
            self.info("Made it query_version, c['release_config_file true {}".format(self.version))
        else:
            self.version = self._query_make_variable("MOZ_APP_VERSION")
        return self.version

    def query_upload_url(self, locale):
        if locale in self.upload_urls:
            return self.upload_urls[locale]
        if 'snippet_base_url' in self.config:
            return self.config['snippet_base_url'] % {'locale': locale}
        self.error("Can't determine the upload url for %s!" % locale)
        self.error("You either need to run --upload-repacks before --create-nightly-snippets, or specify the 'snippet_base_url' in self.config!")

    def add_failure(self, locale, message, **kwargs):
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
        BaseScript.summary(self)
        # TODO we probably want to make this configurable on/off
        locales = self.query_locales()
        for locale in locales:
            self.locales_property.setdefault(locale, "Success")
        self.set_buildbot_property("locales", json.dumps(self.locales_property), write_to_file=True)

    # Actions {{{2
    def clobber(self):
        self.read_buildbot_config()
        dirs = self.query_abs_dirs()
        c = self.config
        objdir = os.path.join(dirs['abs_work_dir'], c['mozilla_dir'],
                              c['objdir'])
        PurgeMixin.clobber(self, always_clobber_dirs=[objdir])

    def pull(self):
        c = self.config
        dirs = self.query_abs_dirs()
        repos = []
        replace_dict = {}
        if c.get("user_repo_override"):
            replace_dict['user_repo_override'] = c['user_repo_override']
            # deepcopy() needed because of self.config lock bug :(
            for repo_dict in deepcopy(c['repos']):
                repo_dict['repo'] = repo_dict['repo'] % replace_dict
                repos.append(repo_dict)
        else:
            repos = c['repos']
        self.vcs_checkout_repos(repos, parent_dir=dirs['abs_work_dir'],
                                tag_override=c.get('tag_override'))
        self.pull_locale_source()

    # list_locales() is defined in LocalesMixin.

    def _setup_configure(self, buildid=None):
        self.enable_mock()
        if self.make_configure():
            self.fatal("Configure failed!")
        self.make_dirs()
        self.make_export(buildid)

    def print_dirs(self):
        #REMOVE ME
        dirs = self.query_abs_dirs()
        for i in dirs:
            self.info("%s  -> %s" % (i, dirs[i]))

    def setup(self):
        self.enable_mock()
        dirs = self.query_abs_dirs()
        self.copy_mozconfig()
        self._setup_configure()
        self.make_wget_en_US()
        self.make_unpack()
        revision = self.query_revision()
        if not revision:
            self.fatal("Can't determine revision!")
        # TODO do this through VCSMixin instead of hardcoding hg
        #self.update(dest=dirs["abs_mozilla_dir"], revision=revision)
        hg = self.query_exe("hg")
        self.run_command([hg, "update", "-r", revision],
                         cwd=dirs["abs_mozilla_dir"],
                         env=self.query_repack_env(),
                         error_list=BaseErrorList,
                         halt_on_failure=True)
        # if checkout updates CLOBBER file with a newer timestamp,
        # next make -f client.mk configure  will delete archives
        # downloaded with make wget_en_US, so just touch CLOBBER file
        clobber_file = self.clobber_file()
        if os.path.exists(clobber_file):
            self._touch_file(clobber_file)
        # Configure again since the hg update may have invalidated it.
        buildid = self.query_buildid()
        self._setup_configure(buildid=buildid)

    def clobber_file(self):
        c = self.config
        dirs = self.query_abs_dirs()
        return os.path.join(dirs['abs_objdir'], c.get('clobber_file'))

    def copy_mozconfig(self):
        c = self.config
        dirs = self.query_abs_dirs()
        src = os.path.join(dirs['abs_work_dir'], c['mozconfig'])
        dst = os.path.join(dirs['abs_mozilla_dir'], '.mozconfig')
        self.copyfile(src, dst)
        with open(dst, 'r') as f:
            for line in f:
                self.info(line.strip())

    def _make(self, target, cwd, env, error_list=MakefileErrorList,
              halt_on_failure=True, return_type="list", silent=False):
        """a wrapper for make calls"""
        make = self.query_exe("make", return_type=return_type)
        return self.run_command(make + target,
                                cwd=cwd,
                                env=env,
                                error_list=error_list,
                                halt_on_failure=halt_on_failure)

    def make_configure(self):
        """calls make -f client.mk configure"""
        env = self.query_repack_env()
        dirs = self.query_abs_dirs()
        cwd = dirs['abs_mozilla_dir']
        target = ["-f", "client.mk", "configure"]
        return self._make(target=target, cwd=cwd, env=env)

    def make_dirs(self):
        """calls make <dirs>
           dirs is defined in configuration"""
        c = self.config
        env = self.query_repack_env()
        dirs = self.query_abs_dirs()
        target = []
        for make_dir in c.get('make_dirs', []):
            cwd = os.path.join(dirs['abs_objdir'], make_dir)
            self._make(target=target, cwd=cwd, env=env, halt_on_failure=True)

    def make_export(self, buildid):
        """calls make export <buildid>"""
        #is it really needed ???
        if buildid is None:
            return
        dirs = self.query_abs_dirs()
        cwd = dirs['abs_locales_dir']
        env = self.query_repack_env()
        target = ["export", 'MOZ_BUILD_DATE=%s' % str(buildid)]
        return self._make(target=target, cwd=cwd, env=env)

    def make_unpack(self):
        """wrapper for make unpack"""
        c = self.config
        dirs = self.query_abs_dirs()
        env = self.query_repack_env()
        cwd = os.path.join(dirs['abs_objdir'], c['locales_dir'])
        return self._make(target=["unpack"], cwd=cwd, env=env)

    def make_wget_en_US(self):
        """wrapper for make wget-en-US"""
        env = self.query_repack_env()
        dirs = self.query_abs_dirs()
        cwd = dirs['abs_locales_dir']
        return self._make(target=["wget-en-US"], cwd=cwd, env=env)

    def make_installers(self, locale):
        """wrapper for make installers-(locale)"""
        env = self.query_repack_env()
        dirs = self.query_abs_dirs()
        cwd = os.path.join(dirs['abs_locales_dir'])
        target = ["installers-%s" % locale,
                  "LOCALE_MERGEDIR=%s" % env["LOCALE_MERGEDIR"]]
        return self._make(target=target, cwd=cwd,
                          env=env, halt_on_failure=False)

    def generate_complete_mar(self):
        """creates a complete mar file"""
        c = self.config
        dirs = self.query_abs_dirs()
        self.create_mar_dirs()
        mt = MarTool(c, dirs)
        mt.download()
        package_basedir = os.path.join(dirs['abs_objdir'], c['package_base_dir'])
        success_count = 0
        total_count = 0
        env = {'MOZ_PKG_PRETTYNAMES': "1"}
        env = {'DIST': dirs['abs_objdir']}
        for locale in self.locales:
            total_count += 1
            cmd = os.path.join(dirs['abs_objdir'], c['update_packaging_dir'])
            cmd = ['-C', cmd, 'full-update', 'AB_CD=%s' % locale,
                   'PACKAGE_BASE_DIR=%s' % package_basedir]
            if self._make(target=cmd, cwd=dirs['abs_mozilla_dir'], env=env):
                self.add_failure(locale, message="%s failed in create complete mar!" % locale)
            else:
                success_count += 1
        self.summarize_success_count(success_count, total_count,
                                     message="Created %d of %d complete mar sucessfully.")

    def repack(self):
        """creates the repacks and udpates"""
        # TODO per-locale logs and reporting.
        self.enable_mock()
        locales = self.query_locales()
        success_count = total_count = 0
        for locale in locales:
            total_count += 1
            result = self.run_compare_locales(locale)
            if result:
                self.add_failure(locale, message="%s failed in compare-locales!" % locale)
                continue
            if self.make_installers(locale):
                self.add_failure(locale, message="%s failed in make installers-%s!" % (locale, locale))
            else:
                success_count += 1
        self.summarize_success_count(success_count, total_count,
                                     message="Repacked %d of %d binaries successfully.")

    def upload_repacks(self):
        """calls make upload <locale>"""
        c = self.config
        dirs = self.query_abs_dirs()
        locales = self.query_locales()
        make = self.query_exe("make", return_type="list")
        base_package_name = self.query_base_package_name()
        version = self.query_version()
        upload_env = self.query_upload_env()
        success_count = total_count = 0
        #buildnum = None
        #if c.get('release_config_file'):
        #    rc = self.query_release_config()
        #    buildnum = rc['buildnum']
        for locale in locales:
            if self.query_failure(locale):
                self.warning("Skipping previously failed locale %s." % locale)
                continue
            total_count += 1
            if c.get('base_post_upload_cmd'):
                upload_env['POST_UPLOAD_CMD'] = c['base_post_upload_cmd'] % {'version': version, 'locale': locale}
            output = self.get_output_from_command(
                # Ugly hack to avoid |make upload| stderr from showing up
                # as get_output_from_command errors
                #
                #
                # how does 2&1 works under windows?
                # removing it for now
                #"%s upload AB_CD=%s 2>&1" % (make, locale),
                make + ["upload", "AB_CD={}".format(locale)],
                cwd=dirs['abs_locales_dir'],
                env=upload_env,
                silent=True
            )
            parser = OutputParser(config=self.config, log_obj=self.log_obj,
                                  error_list=MakefileErrorList)
            parser.add_lines(output)
            if parser.num_errors:
                self.add_failure(locale, message="%s failed in make upload!" % (locale))
                continue
            package_name = base_package_name % {'locale': locale}
            r = re.compile("(http.*%s)" % package_name)
            success = False
            for line in output.splitlines():
                m = r.match(line)
                if m:
                    self.upload_urls[locale] = m.groups()[0]
                    self.info("Found upload url %s" % self.upload_urls[locale])
                    success = True
            if not success:
                self.add_failure(locale, message="Failed to detect %s url in make upload!" % (locale))
                print output
                continue
            success_count += 1
        self.summarize_success_count(success_count, total_count,
                                     message="Uploaded %d of %d binaries successfully.")

    def create_nightly_snippets(self):
        """create snippets for nightly"""
        c = self.config
        dirs = self.query_abs_dirs()
        locales = self.query_locales()
        base_package_name = self.query_base_package_name()
        buildid = self.query_buildid()
        version = self.query_version()
        binary_dir = os.path.join(dirs['abs_objdir'], 'dist')
        success_count = total_count = 0
        replace_dict = {
            'buildid': buildid,
            'build_target': c['build_target'],
        }
        for locale in locales:
            total_count += 1
            replace_dict['locale'] = locale
            aus_basedir = c['aus_base_dir'] % replace_dict
            aus_abs_dir = os.path.join(dirs['abs_work_dir'], 'update',
                                       aus_basedir)
            binary_path = os.path.join(binary_dir,
                                       base_package_name % {'locale': locale})
            # for win repacks
            binary_path = binary_path.replace(os.sep, "/")
            url = self.query_upload_url(locale)
            if not url:
                self.add_failure(locale, "Can't create a snippet for %s without an upload url." % locale)
                continue
            if not self.create_complete_snippet(binary_path, version, buildid, url, aus_abs_dir):
                self.add_failure(locale, message="Errors creating snippet for %s!  Removing snippet directory." % locale)
                self.rmtree(aus_abs_dir)
                continue
            self._touch_file(os.path.join(aus_abs_dir, "partial.txt"))
            success_count += 1
        self.summarize_success_count(success_count, total_count,
                                     message="Created %d of %d snippets successfully.")

    def upload_nightly_snippets(self):
        """uploads nightly snippets"""
        c = self.config
        dirs = self.query_abs_dirs()
        update_dir = os.path.join(dirs['abs_work_dir'], 'update')
        if not os.path.exists(update_dir):
            self.error("No such directory %s! Skipping..." % update_dir)
            return
        if self.rsync_upload_directory(update_dir, c['aus_ssh_key'],
                                       c['aus_user'], c['aus_server'],
                                       c['aus_upload_basedir']):
            self.return_code += 1

    def generate_partials(self):
        """generate partial files"""
        f = self.get_previous_mar()
        partials = [f]
        c = self.config
        dirs = self.query_abs_dirs()
        platform = c['platform']
        version = self.query_version()
        update_mar_dir = self.update_mar_dir()
        for locale in self.locales:
            localized_mar = c['localized_mar'] % {'platform': platform,
                                                  'version': version,
                                                  'locale': locale}
            localized_mar = os.path.join(update_mar_dir, localized_mar)
            to_mar = MarFile(c, dirs, localized_mar)
            for partial in partials:
                # TODO avoid unpacking the same same files multiple times
                from_mar = MarFile(c, dirs, partial)
                archive = c['partial_mar'] % {'version': version,
                                              'locale': locale,
                                              'from_buildid': from_mar.buildid(),
                                              'to_buildid': to_mar.buildid()}
                archive = os.path.join(update_mar_dir, archive)
                to_mar.incremental_update(from_mar, archive)

    def delete_pgc_files(self):
        """deletes pgc files"""
        for d in (self.previous_mar_dir(), self.current_mar_dir()):
            for f in self.pgc_files(d):
                self.info("removing %f" % f)
                #os.remove(f)

    def current_mar_filename(self):
        """retruns the full path to complete.mar"""
        c = self.config
        version = self.query_version()
        update_env = self.query_env(partial_env=c.get("update_env"))
        platform = update_env['MOZ_PKG_PLATFORM']
        version = self.query_version()
        filename = c["complete_mar"] % {'version': version,
                                        'platform': platform}
        return os.path.join(self.get_objdir(), 'dist', filename)

    def query_latest_version(self):
        """find latest available version from candidates_base_url"""
        if self.version:
            return self.version
        c = self.config
        url = c.get('candidates_base_url')
        temp_dir = tempfile.mkdtemp()
        temp_out = os.path.join(temp_dir, 'versions')
        self.download_file(url, temp_out)
        self.version = "27.0a1"  # hardcoded... too bad
        self.rmtree(temp_dir)
        return self.version

    def previous_mar_url(self):
        """returns the url for previous mar"""
        c = self.config
        update_env = self.query_env(partial_env=c.get("update_env"))
        # why from env?
        base_url = update_env['EN_US_BINARY_URL']
        platform = update_env['MOZ_PKG_PLATFORM']
        version = self.query_version()
        remote_filename = c["complete_mar"] % {'version': version,
                                               'platform': platform}
        #remote_filename = "".join(("firefox-", version, ".en-US.", platform, ".complete.mar"))
        return "/".join((base_url, remote_filename))

    def get_previous_mar(self):
        """downloads the previous mar file"""
        dirs = self.query_abs_dirs()
        self.mkdir_p(dirs['local_mar_dir'])
        self.download_file(self.previous_mar_url(),
                           self._previous_mar_filename())
        return self._previous_mar_filename()

    def _previous_mar_filename(self):
        """returns the complete path to previous.mar"""
        c = self.config
        return os.path.join(self.previous_mar_dir(), c['previous_mar_filename'])

    def create_mar_dirs(self):
        """creates mar directories: previous/ current/"""
        for d in (self.previous_mar_dir(),
                  self.current_mar_dir()):
            self.info("creating: %s" % d)
            self.mkdir_p(d)

    def delete_mar_dirs(self):
        """delete mar directories: previous, current"""
        for d in (self.previous_mar_dir(),
                  self.current_mar_dir(),
                  self.current_work_mar_dir()):
            self.info("deleting: %s" % d)
            if os.path.exists(d):
                self.rmtree(d)

    def incremental_update_script(self):
        """returns the full path to the script for creating
           incremental updates"""
        return self._update_packaging_script('incremental_update_script')

    def previous_mar_dir(self):
        """returns the full path of the previous/ directory"""
        return self._mar_dir('previous_mar_dir')

    def update_mar_dir(self):
        """returns the full path of the update/ directory"""
        return self._mar_dir('update_mar_dir')

    def current_mar_dir(self):
        """returns the full path of the current/ directory"""
        return self._mar_dir('current_mar_dir')

    def current_work_mar_dir(self):
        """returns the full path to current.work"""
        return self._mar_dir('current_work_mar_dir')

    def _mar_dir(self, dirname):
        """returns the full path of dirname;
            dirname is an entry in configuration"""
        c = self.config
        return os.path.join(self.get_objdir(), c.get(dirname))

    def get_objdir(self):
        """returns full path to objdir"""
        dirs = self.query_abs_dirs()
        return dirs['abs_objdir']

    def pgc_files(self, basedir):
        """returns a list of .pcf files in basedir"""
        pgc_files = []
        for dirpath, files, dirs in os.walk(basedir):
            for f in files:
                if f.endswith('.pgc'):
                    pgc_files.append(os.path.join(dirpath, f))
        return pgc_files


class MarTool(BaseScript):
    """manages the mar tools executables"""
    def __init__(self, config, dirs):
        self.config = config
        self.dirs = dirs
        self.log_obj = None
        self.binaries = {'mar': None,
                         'mbsdiff': None}
        super(BaseScript, self).__init__()
                       #     require_config_file=False)

    def local_dir(self):
        """full path to the directory that contains
           mar and mbsdiff executables"""
        c = self.config
        return os.path.join(self.dirs['abs_objdir'],
                            c.get("local_mar_tool_dir"))

    def download(self):
        """downloads mar tools executables (mar,mbsdiff)
           and stores them local_dir()"""
        c = self.config
        self.info("getting mar tools")
        partials_url = c["partials_url"] % {'base_url': c.get('candidates_base_url')}
        url = c["mar_tools_url"] % {'partials_url': partials_url}
        self.mkdir_p(self.local_dir())
        for binary in self.binaries:
            from_url = "/".join((url, binary))
            full_path = self._query_bin(binary)
            if not os.path.exists(full_path):
                self.download_file(from_url, file_name=full_path)
                self.info("downloaded %s" % full_path)
            else:
                self.info("found %s, skipping download" % full_path)
            self.chmod(full_path, 0755)

    def _query_bin(self, bin_name):
        """returns the full path to bin_name"""
        if not self.binaries[bin_name]:
            c = self.config
            self.binaries[bin_name] = os.path.join(self.local_dir(),
                                                   c.get(bin_name))
        return self.binaries[bin_name]

    def env(self):
        """returns the env setting required to run mar and/or mbsdiff"""
        env = {}
        for binary in self.binaries:
            env[binary.upper()] = self._query_bin(binary)
        return env


class MarFile(BaseScript):
    """manages the downlad/unpack and incremental updates of mar files"""
    def __init__(self, config, dirs, filename=None):
        self.config = config
        self.dirs = dirs
        self.dst_dir = None
        self.filename = filename
        self.url = None
        self.version = None
        self.log_obj = None
        self.mt = MarTool(self.config, dirs)
        super(BaseScript, self).__init__()

    def unpack(self, dst_dir):
        """unpacks a mar file into dst_dir"""
        self.download()
        # downloading mar tools
        mt = self.mt
        mt.download()
        cmd = ['perl', self.unpack_script(), self.filename]
        env = mt.env()
        env["MOZ_PKG_PRETTYNAMES"] = "1"
        self.mkdir_p(dst_dir)
        self.run_command(cmd,
                         cwd=dst_dir,
                         env=env,
                         halt_on_failure=True)

    def download(self):
        """downloads mar file - not implemented yet"""
        if not os.path.exists(self.filename):
            pass
        return self.filename

    def _update_packaging_script(self, script):
        """returns the full path of script"""
        c = self.config
        return os.path.join(self.update_packaging_dir(), c.get(script))

    def incremental_update_script(self):
        """full path to the incremental update script"""
        return self._update_packaging_script('incremental_update_script')

    def unpack_script(self):
        """returns the full path to the unpack script """
        return self._update_packaging_script('unpack_script')

    def incremental_update(self, other, partial_filename):
        """create an incremental update from the current mar to the
          other mar object. It stores the result in partial_filename"""
        fromdir = tempfile.mkdtemp()
        todir = tempfile.mkdtemp()
        self.unpack(fromdir)
        other.unpack(todir)
        # Usage: make_incremental_update.sh [OPTIONS] ARCHIVE FROMDIR TODIR
        cmd = [self.incremental_update_script(), partial_filename,
               fromdir, todir]
        mt = self.mt
        env = mt.env()
        self.run_command(cmd, cwd=None, env=env)
        self.rmtree(todir)
        self.rmtree(fromdir)

    def buildid(self):
        """returns the buildid of the current mar file"""
        if self.buildid is not None:
            return self.buildid
        temp_dir = tempfile.mkdtemp()
        self.unpack(temp_dir)
        ini_file = self.application_ini_file(temp_dir)
        self.buildid = self.get_buildid_form_ini(ini_file)
        return self.buildid

    def application_ini_file(self, basedir):
        """returns the full path of the application.ini file"""
        c = self.config
        ini_file = os.path.join(basedir, c.get('application_ini'))
        self.info("application.ini file: %s" % ini_file)
        return ini_file

    def get_buildid_form_ini(self, ini_file):
        """reads an ini_file and returns the buildid"""
        c = self.config
        ini = ConfigParser.SafeConfigParser()
        ini.read(ini_file)
        return ini.get(c.get('buildid_section'),
                       c.get('buildid_option'))

    def update_packaging_dir(self):
        """returns the full path to update packaging directory"""
        c = self.config
        dirs = self.dirs
        return os.path.join(dirs['abs_mozilla_dir'], c.get('update_packaging_dir'))

# main {{{
if __name__ == '__main__':
    single_locale = DesktopSingleLocale()
    single_locale.run()
