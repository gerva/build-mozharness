BRANCH = "mozilla-central"
MOZILLA_DIR = BRANCH
HG_SHARE_BASE_DIR = "/builds/hg-shared"
EN_US_BINARY_URL = "http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/latest-mozilla-central"
OBJDIR = "obj-l10n"
MOZ_UPDATE_CHANNEL = "nightly"
STAGE_SERVER = "dev-stage01.srv.releng.scl3.mozilla.com"
#STAGE_SERVER = "stage.mozilla.org"
STAGE_USER = "ffxbld"
STAGE_SSH_KEY = "~/.ssh/ffxbld_dsa"
AUS_SERVER = "dev-stage01.srv.releng.scl3.mozilla.com"
#AUS_SERVER = "aus2-staging.mozilla.org"
AUS_USER = "ffxbld"
AUS_SSH_KEY = "~/.ssh/ffxbld_dsa"
AUS_UPLOAD_BASE_DIR = "/opt/aus2/incoming/2/Firefox"
AUS_BASE_DIR = BRANCH + "/%(build_target)s/%(buildid)s/%(locale)s"
CANDIDATES_URL = "http://ftp.mozilla.org/pub/mozilla.org/firefox/%s" % MOZ_UPDATE_CHANNEL
config = {
    'balrog_api_root': 'https://aus4-admin-dev.allizom.org',
    "mozilla_dir": MOZILLA_DIR,
    "snippet_base_url": "http://example.com",
    "mozconfig": "%s/browser/config/mozconfigs/linux64/l10n-mozconfig" % MOZILLA_DIR,
    "binary_url": EN_US_BINARY_URL,
    "repos": [{
        "vcs": "hg",
        "repo": "https://hg.mozilla.org/mozilla-central",
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
        "DIST": "%(abs_objdir)s",
        "LOCALE_MERGEDIR": "%(abs_merge_dir)s/",
    },
    "log_name": "single_locale",
    "objdir": OBJDIR,
    "js_src_dir": "js/src",
    "make_dirs": ['config'],
    "vcs_share_base": HG_SHARE_BASE_DIR,

    "upload_env": {
        "UPLOAD_USER": STAGE_USER,
        "UPLOAD_SSH_KEY": STAGE_SSH_KEY,
        "UPLOAD_HOST": STAGE_SERVER,
        #"POST_UPLOAD_CMD": "post_upload.py -b mozilla-central-android-l10n -p mobile -i %(buildid)s --release-to-latest --release-to-dated",
        "POST_UPLOAD_CMD": "post_upload.py -b mozilla-central-l10n -p firefox -i %(buildid)s  --release-to-latest --release-to-dated",
        "UPLOAD_TO_TEMP": "1"
    },
    #l10n
    "ignore_locales": ["en-US"],
    "l10n_dir": "l10n",
    "l10n_stage_dir": "dist/firefox/l10n-stage",
    "locales_file": "%s/browser/locales/all-locales" % MOZILLA_DIR,
    "locales_dir": "browser/locales",
    "hg_l10n_base": "https://hg.mozilla.org/l10n-central",
    "hg_l10n_tag": "default",
    "merge_locales": True,
    "clobber_file": 'CLOBBER',

    #MAR
    'previous_mar_url': 'http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/latest-mozilla-central-l10n',
    'current_mar_url': 'http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/latest-mozilla-central',
    "previous_mar_dir": "previous",
    "current_mar_dir": "current",
    "update_mar_dir": "dist/update",  # sure?
    "previous_mar_filename": "previous.mar",
    "current_work_mar_dir": "current.work",
    "package_base_dir": "dist/l10n-stage",
    "application_ini": "application.ini",
    "buildid_section": 'App',
    "buildid_option": "BuildID",
    "unpack_script": "tools/update-packaging/unwrap_full_update.pl",
    "incremental_update_script": "tools/update-packaging/make_incremental_update.sh",
    "update_packaging_dir": "tools/update-packaging",
    "local_mar_tool_dir": "dist/host/bin",
    "mar": "mar",
    "mbsdiff": "mbsdiff",
    "candidates_base_url": CANDIDATES_URL,
    "partials_url": "%(base_url)s/latest-mozilla-central/",
    "mar_tools_url": "http://ftp.mozilla.org/pub/mozilla.org/firefox/nightly/latest-mozilla-central/mar-tools/linux/",
    "complete_mar": "firefox-%(version)s.en-US.linux-i686.complete.mar",
    "localized_mar": "firefox-%(version)s.%(locale)s.linux-i686.complete.mar",
    "partial_mar": "firefox-%(version)s.%(locale)s.partial.%(from_buildid)s-%(to_buildid)s.mar",
    'installer_file': "firefox-%(version)s.en-US.linux-i686.tar.bz2",

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
         'glibc-static.i686', 'libstdc++-static.i686', 'perl-Test-Simple', 'perl-Config-General',
         'gtk2-devel.i686', 'libnotify-devel.i686', 'yasm',
         'alsa-lib-devel.i686', 'libcurl-devel.i686',
         'wireless-tools-devel.i686', 'libX11-devel.i686',
         'libXt-devel.i686', 'mesa-libGL-devel.i686',
         'gnome-vfs2-devel.i686', 'GConf2-devel.i686', 'wget',
         'mpfr',  # required for system compiler
         'xorg-x11-font*',  # fonts required for PGO
         'imake',  # required for makedepend!?!
         'gcc45_0moz3', 'gcc454_0moz1', 'gcc472_0moz1', 'gcc473_0moz1', 'yasm', 'ccache',  # <-- from releng repo
         'valgrind',
         'pulseaudio-libs-devel.i686',
         'gstreamer-devel.i686', 'gstreamer-plugins-base-devel.i686',
         # Packages already installed in the mock environment, as x86_64
         # packages.
         'glibc-devel.i686', 'libgcc.i686', 'libstdc++-devel.i686',
         # yum likes to install .x86_64 -devel packages that satisfy .i686
         # -devel packages dependencies. So manually install the dependencies
         # of the above packages.
         'ORBit2-devel.i686', 'atk-devel.i686', 'cairo-devel.i686',
         'check-devel.i686', 'dbus-devel.i686', 'dbus-glib-devel.i686',
         'fontconfig-devel.i686', 'glib2-devel.i686',
         'hal-devel.i686', 'libICE-devel.i686', 'libIDL-devel.i686',
         'libSM-devel.i686', 'libXau-devel.i686', 'libXcomposite-devel.i686',
         'libXcursor-devel.i686', 'libXdamage-devel.i686', 'libXdmcp-devel.i686',
         'libXext-devel.i686', 'libXfixes-devel.i686', 'libXft-devel.i686',
         'libXi-devel.i686', 'libXinerama-devel.i686', 'libXrandr-devel.i686',
         'libXrender-devel.i686', 'libXxf86vm-devel.i686', 'libdrm-devel.i686',
         'libidn-devel.i686', 'libpng-devel.i686', 'libxcb-devel.i686',
         'libxml2-devel.i686', 'pango-devel.i686', 'perl-devel.i686',
         'pixman-devel.i686', 'zlib-devel.i686',
         # Freetype packages need to be installed be version, because a newer
         # version is available, but we don't want it for Firefox builds.
         'freetype-2.3.11-6.el6_1.8.i686', 'freetype-devel-2.3.11-6.el6_1.8.i686',
         'freetype-2.3.11-6.el6_1.8.x86_64',
         ],
         'mock_files': [
                ('/home/cltbld/.ssh', '/home/mock_mozilla/.ssh'),
                ('/home/cltbld/.hgrc', '/builds/.hgrc'),
                ('/home/cltbld/.boto', '/builds/.boto'),
                ('/builds/gapi.data', '/builds/gapi.data'),
                ('/tools/tooltool.py', '/builds/tooltool.py'),
         ],
}
