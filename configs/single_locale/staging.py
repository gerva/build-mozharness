UPLOAD_SERVER = "dev-stage01.srv.releng.scl3.mozilla.com"
UPLOAD_USER = "ffxbld"
UPLOAD_SSH_KEY = "~/.ssh/ffxbld_dsa"
AUS_USER = "ffxbld"
AUS_SSH_KEY = "~/.ssh/ffxbld_dsa"
AUS_UPLOAD_BASE_DIR = "/opt/aus2/incoming/2/Firefox"
AUS_BASE_DIR = "%(branch)s/%(update_platform)s/%(buildid)s/%(locale)s"
AUS_SERVER = "blah"

config = {
    "upload_env": {
        "UPLOAD_USER": UPLOAD_USER,
        "UPLOAD_SSH_KEY": UPLOAD_SSH_KEY,
        "UPLOAD_HOST": UPLOAD_SERVER,
        "POST_UPLOAD_CMD": "post_upload.py -b %(branch)s -p firefox -i %(buildid)s  --release-to-latest --release-to-dated",
        "UPLOAD_TO_TEMP": "1"
    },
    # AUS
    "aus_server": AUS_SERVER,
    "aus_user": AUS_USER,
    "aus_ssh_key": AUS_SSH_KEY,
    "aus_upload_base_dir": AUS_UPLOAD_BASE_DIR,
    "aus_base_dir": AUS_BASE_DIR,
}
