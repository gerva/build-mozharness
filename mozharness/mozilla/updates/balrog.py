from itertools import chain
import os

from mozharness.base.log import INFO


# BalrogMixin {{{1
class BalrogMixin(object):
    def submit_balrog_updates(self, marfile, hash_type, appName, appVersion,
                              platform, branch, buildid, complete_mar_url,
                              release_type="nightly", ):
        config = self.config
        balrog_props = {}
        balrog_props['hashType'] = hash_type
        balrog_props['appName'] = appName
        balrog_props['appVersion'] = appVersion
        balrog_props['platform'] = platform
        balrog_props['buildid'] = buildid
        balrog_props['branch'] = branch
        balrog_props['completeMarSize'] = self.query_filesize(marfile)
        balrog_props['completeMarHash'] = self.query_sha512sum(marfile)
        balrog_props['completeMarUrl'] = complete_mar_url

        dirs = self.query_abs_dirs()
        product = config["product"]
        props_path = os.path.join(dirs["base_work_dir"], "balrog_props.json")
        credentials_file = os.path.join(
            dirs["base_work_dir"], config["balrog_credentials_file"]
        )
        submitter_script = os.path.join(
            dirs["abs_tools_dir"], "scripts", "updates", "balrog-submitter.py"
        )
        balrog_props = dict(properties=dict(chain(
            balrog_props.items(),)))
        self.dump_config(props_path, balrog_props)
        cmd = [
            self.query_exe("python"),
            submitter_script,
            "--build-properties", props_path,
            "--api-root", config["balrog_api_root"],
            "--username", config["balrog_usernames"][product],
            "-t", release_type,
            "--credentials-file", credentials_file,
        ]
        if self._log_level_at_least(INFO):
            cmd.append("--verbose")

        self.info("Calling Balrog submission script")
        self.retry(
            self.run_command, args=(cmd,),
            kwargs={
                "halt_on_failure": False,
                "fatal_exit_code": 3,
            },
        )
