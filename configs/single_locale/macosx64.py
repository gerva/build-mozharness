PLATFORM = 'macosx64'
HG_SHARE_BASE_DIR = "/builds/hg-shared"
OBJDIR = "obj-l10n"
MOZILLA_DIR = "%(branch)s",
MOZ_UPDATE_CHANNEL = "nightly"
config = {
    "mozilla_dir": "%(branch)s",
    "mozconfig": "%(branch)s/browser/config/mozconfigs/macosx-universal/l10n-mozconfig",
    "src_xulrunner_mozconfig": "xulrunner/config/mozconfigs/macosx64/xulrunner",
    "binary_url": "%(en_us_binary_url)s",
    "platform": PLATFORM,
    "repos": [{
        "vcs": "hg",
        "repo": "%(branch_repo)s",
        "dest": "%(branch)s",
    }, {
        "vcs": "hg",
        "repo": "https://hg.mozilla.org/build/tools",
        "revision": "default",
        "dest": "tools",
    }, {
        "vcs": "hg",
        "repo": "https://hg.mozilla.org/build/compare-locales",
        "revision": "RELEASE_AUTOMATION"
    }],
    "repack_env": {
        "SHELL": '/bin/bash',
        "MOZ_OBJDIR": OBJDIR,
        "EN_US_BINARY_URL": "%(en_us_binary_url)s",
        "MOZ_UPDATE_CHANNEL": MOZ_UPDATE_CHANNEL,
        "MOZ_SYMBOLS_EXTRA_BUILDID": "macosx64",
        "MOZ_PKG_PLATFORM": "mac",
        "IS_NIGHTLY": "yes",
        "DIST": "%(abs_objdir)s",
        "LOCALE_MERGEDIR": "%(abs_merge_dir)s/",
    },
    "log_name": "single_locale",
    "objdir": OBJDIR,
    "js_src_dir": "js/src",
    "make_dirs": ['config'],
    "vcs_share_base": HG_SHARE_BASE_DIR,

    "upload_env_extra": {
        "MOZ_PKG_PLATFORM": "mac",
    },

    # l10n
    "ignore_locales": ["en-US"],
    "l10n_dir": "l10n",
    "l10n_stage_dir": "dist/firefox/l10n-stage",
    "locales_file": "%(branch)s/browser/locales/all-locales",
    "locales_dir": "browser/locales",
    "hg_l10n_base": "https://hg.mozilla.org/l10n-central",
    "hg_l10n_tag": "default",
    "merge_locales": True,
    "clobber_file": 'CLOBBER',

    # MAR
    "previous_mar_dir": "previous",
    "current_mar_dir": "current",
    "update_mar_dir": "dist/update",  # sure?
    "previous_mar_filename": "previous.mar",
    "current_work_mar_dir": "current.work",
    "package_base_dir": "dist/l10n-stage",
    "application_ini": "Contents/MacOS/application.ini",
    "buildid_section": 'App',
    "buildid_option": "BuildID",
    "unpack_script": "tools/update-packaging/unwrap_full_update.pl",
    "incremental_update_script": "tools/update-packaging/make_incremental_update.sh",
    "balrog_release_pusher_script": "scripts/updates/balrog-release-pusher.py",
    "update_packaging_dir": "tools/update-packaging",
    "local_mar_tool_dir": "dist/host/bin",
    "mar": "mar",
    "mbsdiff": "mbsdiff",
    "current_mar_filename": "firefox-%(version)s.en-US.mac.complete.mar",
    "localized_mar": "firefox-%(version)s.%(locale)s.mac.complete.mar",
    "partial_mar": "firefox-%(version)s.%(locale)s.mac.partial.%(from_buildid)s-%(to_buildid)s.mar",
    'installer_file': "firefox-%(version)s.en-US.mac.dmg",
}
