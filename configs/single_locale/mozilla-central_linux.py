BRANCH = "mozilla-central"
MOZILLA_DIR = BRANCH
HG_SHARE_BASE_DIR = "/builds/hg-shared"
EN_US_BINARY_URL = "http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/latest-mozilla-central"
OBJDIR = "obj-l10n"
MOZ_UPDATE_CHANNEL = "nightly"
STAGE_SERVER = "dev-stage01.build.sjc1.mozilla.com"
#STAGE_SERVER = "stage.mozilla.org"
STAGE_USER = "ffxbld"
STAGE_SSH_KEY = "~/.ssh/ffxbld_dsa"
AUS_SERVER = "dev-stage01.build.sjc1.mozilla.com"
#AUS_SERVER = "aus2-staging.mozilla.org"
AUS_USER = "ffxbld"
AUS_SSH_KEY = "~/.ssh/ffxbld_dsa"
AUS_UPLOAD_BASE_DIR = "/opt/aus2/incoming/2/Firefox"
AUS_BASE_DIR = BRANCH + "/%(build_target)s/%(buildid)s/%(locale)s"


config = {
    "mozilla_dir": MOZILLA_DIR,
    "app_name": "browser",
    "brand_name": "Minefield",
    "snippet_base_url": "http://example.com",
    "mozconfig": "%s/browser/config/mozconfigs/linux32/l10n-mozconfig" % MOZILLA_DIR,
    "repos": [{
        "vcs": "hgtool",
        "repo": "http://hg.mozilla.org/mozilla-central",
        "revision": "default",
        "dest": MOZILLA_DIR,
    }, {
        "vcs": "hgtool",
        "repo": "http://hg.mozilla.org/build/buildbot-configs",
        "revision": "default",
        "dest": "buildbot-configs"
    }, {
        "vcs": "hgtool",
        "repo": "http://hg.mozilla.org/build/compare-locales",
        "revision": "RELEASE_AUTOMATION"
    }, {
        "vcs": "hgtool",
        "repo": "http://hg.mozilla.org/build/tools",
        "revision": "default",
        "dest": "tools"
    }],
    "repack_env": {
        "MOZ_OBJDIR": OBJDIR,
        "EN_US_BINARY_URL": EN_US_BINARY_URL,
        "LOCALE_MERGEDIR": "%(abs_merge_dir)s/",
        "MOZ_UPDATE_CHANNEL": MOZ_UPDATE_CHANNEL
    },
    "log_name": "single_locale",
    "objdir": OBJDIR,
    "make_dirs": ['config'],
    "vcs_share_base": HG_SHARE_BASE_DIR,

    "upload_env": {
        "UPLOAD_USER": STAGE_USER,
        "UPLOAD_SSH_KEY": STAGE_SSH_KEY,
        "UPLOAD_HOST": STAGE_SERVER,
        #"POST_UPLOAD_CMD": "post_upload.py -b mozilla-central-android-l10n -p mobile -i %(buildid)s --release-to-latest --release-to-dated",
        "POST_UPLOAD_CMD": "post_upload.py -b mozilla-central-l10n -p firefox -i %(buildid)s --release-to-latest --release-to-dated",
        "UPLOAD_TO_TEMP": "1"
    },
    #l10n
    "ignore_locales": ["en-US"],
    "l10n_dir": "l10n",
    "locales_file": "%s/browser/locales/all-locales" % MOZILLA_DIR,
    "locales_dir": "browser/locales",
    "hg_l10n_base": "http://hg.mozilla.org/l10n-central",
    "hg_l10n_tag": "default",
    "merge_locales": True,

    # AUS
    "build_target": "Linux_x86-gcc3",
    "aus_server": AUS_SERVER,
    "aus_user": AUS_USER,
    "aus_ssh_key": AUS_SSH_KEY,
    "aus_upload_base_dir": AUS_UPLOAD_BASE_DIR,
    "aus_base_dir": AUS_BASE_DIR,

    # Mock
    'mock_target': 'mozilla-centos6-i386',
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
     'gcc45_0moz3', 'gcc454_0moz1', 'gcc472_0moz1', 'gcc473_0moz1', 'yasm', 'ccache',  # <-- from releng repo
     'valgrind',
     'pulseaudio-libs-devel',
     'gstreamer-devel', 'gstreamer-plugins-base-devel',
     'freetype-2.3.11-6.el6_1.8.x86_64',
     'freetype-devel-2.3.11-6.el6_1.8.x86_64', ],
    'mock_copyin_files': [
        ('/home/cltbld/.ssh', '/home/mock_mozilla/.ssh'),
        ('/home/cltbld/.hgrc', '/builds/.hgrc'),
    ],
}