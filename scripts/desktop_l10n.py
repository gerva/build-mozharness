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

try:
    import simplejson as json
    assert json
except ImportError:
    import json

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.errors import BaseErrorList, MakefileErrorList
from mozharness.base.log import OutputParser
from mozharness.base.transfer import TransferMixin
from mozharness.mozilla.release import ReleaseMixin
from mozharness.mozilla.signing import MobileSigningMixin
from mozharness.mozilla.signing import SigningMixin
from mozharness.base.vcs.vcsbase import VCSMixin
from mozharness.mozilla.l10n.locales import LocalesMixin
from mozharness.mozilla.buildbot import BuildbotMixin
from mozharness.mozilla.purge import PurgeMixin
from mozharness.mozilla.mock import MockMixin
from mozharness.base.script import BaseScript
import mozharness.helpers.html_parse as html_parse

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
                "generate_partials",
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
        self.revision = None
        self.upload_env = None
        self.version = None
        self.upload_urls = {}
        self.locales_property = {}

        if 'mock_target' in self.config:
            self.enable_mock()

    # Helper methods {{{2
    def query_repack_env(self):
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
            repack_env['EN_US_BINARY_URL'] = c['base_en_us_binary_url'] % replace_dict
        if 'MOZ_SIGNING_SERVERS' in os.environ:
            repack_env['MOZ_SIGN_CMD'] = subprocess.list2cmdline(self.query_moz_sign_cmd(formats=None))
        self.repack_env = repack_env
        return self.repack_env

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
        c = self.config
        dirs = self.query_abs_dirs()
        env = self.query_repack_env()
        configure_cmd = ["-f", "client.mk", "configure"]
        export_cmd = ["export", 'MOZ_BUILD_DATE=%s' % str(buildid)]
        make = self.query_exe("make", return_type="list")
        if self.run_command(make + configure_cmd,
                            cwd=dirs['abs_mozilla_dir'],
                            env=env,
                            error_list=MakefileErrorList):
            self.fatal("Configure failed!")
        for make_dir in c.get('make_dirs', []):
            cwd = os.path.join(dirs['abs_objdir'], make_dir)
            make_args = []
            self.run_command(make + make_args,
                             cwd=cwd,
                             env=env,
                             error_list=MakefileErrorList,
                             halt_on_failure=True)
            if buildid:
                self.run_command(make + export_cmd,
                                 cwd=cwd,
                                 env=env,
                                 error_list=MakefileErrorList)

    def setup(self):
        self.enable_mock()
        c = self.config
        dirs = self.query_abs_dirs()
        mozconfig_path = os.path.join(dirs['abs_mozilla_dir'], '.mozconfig')
        self.copyfile(os.path.join(dirs['abs_work_dir'], c['mozconfig']),
                      mozconfig_path)
        hg = self.query_exe("hg")
        make = self.query_exe("make", return_type="list")
        # log the content of mozconfig
        with open(mozconfig_path, 'r') as f:
            for line in f:
                self.info(line.strip())
        env = self.query_repack_env()
        self._setup_configure()
        self.run_command(make + ["wget-en-US"],
                         cwd=dirs['abs_locales_dir'],
                         env=env,
                         error_list=MakefileErrorList,
                         halt_on_failure=True)
        self.run_command(make + ["unpack"],
                         cwd=dirs['abs_locales_dir'],
                         env=env,
                         error_list=MakefileErrorList,
                         halt_on_failure=True)
        revision = self.query_revision()
        if not revision:
            self.fatal("Can't determine revision!")
        # TODO do this through VCSMixin instead of hardcoding hg
        #self.update(dest=dirs["abs_mozilla_dir"], revision=revision)
        self.run_command([hg, "update", "-r", revision],
                         cwd=dirs["abs_mozilla_dir"],
                         env=env,
                         error_list=BaseErrorList,
                         halt_on_failure=True)
        # if checkout updates CLOBBER file with a newer timestamp,
        # next make -f client.mk configure  will delete archives
        # downloaded with make wget_en_US, so just touch CLOBBER file
        clobber_file = os.path.join(dirs['abs_objdir'], 'CLOBBER')
        if os.path.exists(clobber_file):
            self._touch_file(clobber_file)
        # Configure again since the hg update may have invalidated it.
        buildid = self.query_buildid()
        self._setup_configure(buildid=buildid)

    def repack(self):
        # TODO per-locale logs and reporting.
        self.enable_mock()
        #c = self.config
        dirs = self.query_abs_dirs()
        locales = self.query_locales()
        make = self.query_exe("make", return_type="list")
        repack_env = self.query_repack_env()
        #base_package_name = self.query_base_package_name()
        #base_package_dir = os.path.join(dirs['abs_objdir'], 'dist')
        success_count = total_count = 0
        for locale in locales:
            total_count += 1
            result = self.run_compare_locales(locale)
            if result:
                self.add_failure(locale, message="%s failed in compare-locales!" % locale)
                continue
            if self.run_command(make + ["installers-%s" % locale],
                                cwd=os.path.join(dirs['abs_locales_dir']),
                                env=repack_env,
                                error_list=MakefileErrorList,
                                halt_on_failure=False):
                self.add_failure(locale, message="%s failed in make installers-%s!" % (locale, locale))
            else:
                success_count += 1
        self.summarize_success_count(success_count, total_count,
                                     message="Repacked %d of %d binaries successfully.")

    def upload_repacks(self):
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
            aus_base_dir = c['aus_base_dir'] % replace_dict
            aus_abs_dir = os.path.join(dirs['abs_work_dir'], 'update',
                                       aus_base_dir)
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
        c = self.config
        dirs = self.query_abs_dirs()
        update_dir = os.path.join(dirs['abs_work_dir'], 'update')
        if not os.path.exists(update_dir):
            self.error("No such directory %s! Skipping..." % update_dir)
            return
        if self.rsync_upload_directory(update_dir, c['aus_ssh_key'],
                                       c['aus_user'], c['aus_server'],
                                       c['aus_upload_base_dir']):
            self.return_code += 1

    def generate_partials(self):
        self.get_mar_tools()
        self.get_previous_mar()
        self.unpack_previous_mar()
        p_build_id = self.get_buildid_form_ini(self.get_previous_application_ini_file())
        self.info("previous build id %s" % p_build_id)

        dirs = self.query_abs_dirs()
        return os.path.join(dirs['abs_objdir'], 'dist', 'update')

    def local_mar_filename(self):
        dirs = self.query_abs_dirs()
        return os.path.join(dirs['local_mar_dir'], 'previous.mar')

    def query_latest_version(self):
        """ find latest available version from CANDIDATES_URL """
        c = self.config
        url = c.get('candidates_base_url')
        temp_out = tempfile.NamedTemporaryFile(delete=False)
        self.download_file(url, temp_out.name)
        version = html_parse.get_last_version_number(temp_out.name)
        os.remove(temp_out.name)
        return version

    def query_buildnumber(self, url):
        temp_out = tempfile.NamedTemporaryFile(delete=False)
        self.download_file(url, temp_out.name)
        buildnum = html_parse.get_latest_build_number(temp_out.name)
        os.remove(temp_out.name)
        return buildnum

    def previous_mar_url(self):
        c = self.config
        update_env = self.query_env(partial_env=c.get("update_env"))
        #TODO nightly is hardcoded here... fix it!!
        base_url = update_env['EN_US_BINARY_URL']
        platform = update_env['MOZ_PKG_PLATFORM']
        version = self.query_version()
        remote_filename = c["complete_mar"] % {'version': version,
                                               'platform': platform}
        #remote_filename = "".join(("firefox-", version, ".en-US.", platform, ".complete.mar"))
        return "/".join((base_url, remote_filename))

    def get_previous_mar(self):
        dirs = self.query_abs_dirs()
        self.mkdir_p(dirs['local_mar_dir'])
        self.download_file(self.previous_mar_url(),
                           self.local_mar_filename())

    def local_mar_tool_dir(self):
        c = self.config
        dirs = self.query_abs_dirs()
        return os.path.join(dirs['abs_objdir'], c.get("local_mar_tool_dir"))

    def get_mar_tools(self):
        c = self.config
        #update_env = self.query_env(partial_env=c.get("update_env"))
        version = self.query_latest_version()  # self.latest_version() ??
        #partials_url = "/".join((base_url, "{0}-candidates".format(version)))
        partials_url = c["partials_url"] % {'base_url': c.get('candidates_base_url'),
                                            'version': version}
        buildnum = self.query_buildnumber(partials_url)
        # TODO remove macosx64 hardcoded value, get if from config
        # url = "/".join((partials_url, buildnum, 'mar-tools', 'macosx64'))
        url = c["mar_tools_url"] % {'partials_url': partials_url,
                                    'buildnum': buildnum}
        destination_dir = self.local_mar_tool_dir()
        self.mkdir_p(destination_dir)
        for element in ('mar', 'mbsdiff'):
            from_url = "/".join((url, element))
            local_dst = os.path.join(destination_dir, element)
            self.download_file(from_url, file_name=local_dst)
            self.chmod(local_dst, 0755)

    def unpack_previous_mar(self):
        c = self.config
        dirs = self.query_abs_dirs()
        script = os.path.join(dirs['abs_mozilla_dir'],
                              c.get('unpack_script'))
        cmd = ['perl', script, self.local_mar_filename()]
        cwd = self.get_previous_mar_dir()
        if not os.path.exists(cwd):
            self.mkdir_p(cwd)
        env = {}
        env['MAR'] = os.path.join(self.local_mar_tool_dir(), c.get('mar_bin'))
        env['MBSDIFF'] = os.path.join(self.local_mar_tool_dir(), c.get('mbsdiff_bin'))
        self.run_command(cmd,
                         cwd=cwd,
                         env=env,
                         halt_on_failure=True)

    def get_value_from_ini(self, ini_file, section, option):
        """ parses an ini file and returns the value of option from section"""
        from ConfigParser import SafeConfigParser
        parser = SafeConfigParser()
        parser.read(ini_file)
        return parser.get(section, option)

    def get_buildid_form_ini(self, ini_file):
        c = self.config
        return self.get_value_from_ini(ini_file,
                                       c.get('buildid_section'),
                                       c.get('buildid_option'))

    def get_previous_mar_dir(self):
        dirs = self.query_abs_dirs()
        c = self.config
        return os.path.join(dirs['abs_mozilla_dir'],
                            c.get('previous_mar_dir'))

    def get_previous_application_ini_file(self):
        c = self.config
        ini_file = os.path.join(self.get_previous_mar_dir(),
                                c.get('application_ini'))
        self.info("application.ini file: %s" % ini_file)
        return ini_file


# main {{{
if __name__ == '__main__':
    single_locale = DesktopSingleLocale()
    single_locale.run()
