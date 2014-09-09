PLATFORM = 'linux64'
BRANCH = "mozilla-central"
HG_SHARE_BASE_DIR = "/builds/hg-shared"
OBJDIR = "obj-l10n"
MOZILLA_DIR = "%(branch)s"
MOZ_UPDATE_CHANNEL = "nightly"
config = {
    "mozconfig": "%(branch)s/browser/config/mozconfigs/macosx-universal/l10n-mozconfig",
    "platform": PLATFORM,
    "repack_env": {
        "MOZ_OBJDIR": OBJDIR,
        "EN_US_BINARY_URL": "%(en_us_binary_url)s",
        "LOCALE_MERGEDIR": "%(abs_merge_dir)s/",
        "MOZ_UPDATE_CHANNEL": MOZ_UPDATE_CHANNEL,
        "IS_NIGHTLY": "yes",
    },
    "log_name": "single_locale",
    "objdir": OBJDIR,
    "js_src_dir": "js/src",
    "make_dirs": ['config'],
    "vcs_share_base": HG_SHARE_BASE_DIR,

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
    "application_ini": "application.ini",
    "buildid_section": 'App',
    "buildid_option": "BuildID",
    "unpack_script": "tools/update-packaging/unwrap_full_update.pl",
    "incremental_update_script": "tools/update-packaging/make_incremental_update.sh",
    "balrog_release_pusher_script": "scripts/updates/balrog-release-pusher.py",
    "update_packaging_dir": "tools/update-packaging",
    "local_mar_tool_dir": "dist/host/bin",
    "mar": "mar",
    "mbsdiff": "mbsdiff",
    # "partials_url": "%(base_url)s/latest-mozilla-central/",
    "current_mar_filename": "firefox-%(version)s.en-US.linux-x86_64.complete.mar",
    "complete_mar": "firefox-%(version)s.en-US.linux-x86_64.complete.mar",
    "localized_mar": "firefox-%(version)s.%(locale)s.linux-x86_64.complete.mar",
    "partial_mar": "firefox-%(version)s.%(locale)s.linux-x86_64.partial.%(from_buildid)s-%(to_buildid)s.mar",
    "installer_file": "firefox-%(version)s.en-US.linux-x86_64.tar.bz2",

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
        ('/home/cltbld/.boto', '/builds/.boto'),
        ('/builds/gapi.data', '/builds/gapi.data'),
        ('/tools/tooltool.py', '/builds/tooltool.py'),
    ],
}
