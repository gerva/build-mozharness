BRANCH = "%(branch)s"
MOZILLA_DIR = BRANCH
HG_SHARE_BASE_DIR = "/builds/hg-shared"
EN_US_BINARY_URL = "http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/latest-%(branch)s"
OBJDIR = "obj-l10n"
MOZ_UPDATE_CHANNEL = "nightly"
STAGE_SERVER = "dev-stage01.srv.releng.scl3.mozilla.com"
# STAGE_SERVER = "stage.mozilla.org"
STAGE_USER = "ffxbld"
STAGE_SSH_KEY = "~/.ssh/ffxbld_dsa"
AUS_SERVER = "dev-stage01.srv.releng.scl3.mozilla.com"
# AUS_SERVER = "aus2-staging.mozilla.org"
AUS_USER = "ffxbld"
AUS_SSH_KEY = "~/.ssh/ffxbld_dsa"
AUS_UPLOAD_BASE_DIR = "/opt/aus2/incoming/2/Firefox"
AUS_BASE_DIR = BRANCH + "/%(build_target)s/%(buildid)s/%(locale)s"
CANDIDATES_URL = "http://ftp.mozilla.org/pub/mozilla.org/firefox/%s" % MOZ_UPDATE_CHANNEL
PLATFORM = 'linux64'
config = {
    "enable_partials": True,
    "mozilla_dir": MOZILLA_DIR,
    "mozconfig": "%s/browser/config/mozconfigs/linux64/l10n-mozconfig/%(branch)s",
    "binary_url": EN_US_BINARY_URL,
    "platform": PLATFORM,
    "repos": [{
        "vcs": "hg",
        "repo": "https://hg.mozilla.org/%(branch)s",
        "revision": "default",
        "dest": MOZILLA_DIR,
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
        "MOZ_OBJDIR": OBJDIR,
        "EN_US_BINARY_URL": EN_US_BINARY_URL,
        "LOCALE_MERGEDIR": "%(abs_merge_dir)s/",
        "MOZ_UPDATE_CHANNEL": MOZ_UPDATE_CHANNEL,
        "IS_NIGHTLY": "yes",
    },
    "objdir": OBJDIR,
    "js_src_dir": "js/src",
    "make_dirs": ['config'],
    "vcs_share_base": HG_SHARE_BASE_DIR,

    "upload_env": {
        "UPLOAD_USER": STAGE_USER,
        "UPLOAD_SSH_KEY": STAGE_SSH_KEY,
        "UPLOAD_HOST": STAGE_SERVER,
        "POST_UPLOAD_CMD": "post_upload.py -b %(branch)s-l10n -p firefox -i %(buildid)s  --release-to-latest --release-to-dated",
        "UPLOAD_TO_TEMP": "1"
    },
    # l10n
    "l10n_dir": "l10n",
    "l10n_stage_dir": "dist/firefox/l10n-stage",
    "locales_file": "%s/browser/locales/all-locales" % MOZILLA_DIR,
    "hg_l10n_base": "https://hg.mozilla.org/l10n-central",
    "hg_l10n_tag": "default",
    "merge_locales": True,

    # MAR
    "previous_mar_url": "http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/latest-%(branch)s-l10n",
    "current_mar_url": "http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/latest-%(branch)s",
    "package_base_dir": "dist/l10n-stage",
    "incremental_update_script": "tools/update-packaging/make_incremental_update.sh",
    "update_packaging_dir": "tools/update-packaging",
    "local_mar_tool_dir": "dist/host/bin",
    "mar": "mar",
    "mbsdiff": "mbsdiff",
    "candidates_base_url": CANDIDATES_URL,
    "partials_url": "%(base_url)s/latest-%(branch)s/",
    "mar_tools_url": "http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/latest-%(branch)s/mar-tools/linux64/",
    "current_mar_filename": "firefox-%(version)s.en-US.linux-x86_64.complete.mar",
    "complete_mar": "firefox-%(version)s.en-US.linux-x86_64.complete.mar",
    "localized_mar": "firefox-%(version)s.%(locale)s.linux-x86_64.complete.mar",
    "partial_mar": "firefox-%(version)s.%(locale)s.linux-x86_64.partial.%(from_buildid)s-%(to_buildid)s.mar",
    "installer_file": "firefox-%(version)s.en-US.linux-x86_64.tar.bz2",

    # BALROG
    "balrog_api_root": "https://aus4-admin-dev.allizom.org",
    "balrog_credentials_file": "oauth.txt",
    "balrog_username": "stage-ffxbld",
    'balrog_usernames': {
        'firefox': 'stage-ffxbld',
    },

    # AUS
    "aus_server": AUS_SERVER,
    "aus_user": AUS_USER,
    "aus_ssh_key": AUS_SSH_KEY,
    "aus_upload_base_dir": AUS_UPLOAD_BASE_DIR,
    "aus_base_dir": AUS_BASE_DIR,

    # Mock
    'mock_target': 'mozilla-centos6-x86_64',
    'mock_packages':
    ['autoconf213', 'python', 'zip', 'mozilla-python27-mercurial', 'git', 'ccache',
     'glibc-static', 'libstdc++-static', 'perl-Test-Simple', 'perl-Config-General',
     'gtk2-devel', 'libnotify-devel', 'yasm',
     'alsa-lib-devel', 'libcurl-devel',
     'wireless-tools-devel', 'libX11-devel',
     'libXt-devel', 'mesa-libGL-devel',
     'gnome-vfs2-devel', 'GConf2-devel', 'wget',
     'mpfr',  # required for system compiler
     'xorg-x11-font*',  # fonts required for PGO
     'imake',  # required for makedepend!?!
     'gcc45_0moz3', 'gcc454_0moz1', 'gcc472_0moz1', 'yasm', 'ccache',  # <-- from releng repo
     'gcc473_0moz1', 'valgrind',
     'pulseaudio-libs-devel',
     'gstreamer-devel', 'gstreamer-plugins-base-devel',
     'freetype-2.3.11-6.el6_1.8.x86_64',
     'freetype-devel-2.3.11-6.el6_1.8.x86_64', ],
    'mock_files': [
        ('/home/cltbld/.ssh', '/home/mock_mozilla/.ssh'),
        ('/home/cltbld/.hgrc', '/builds/.hgrc'),
    ],
}