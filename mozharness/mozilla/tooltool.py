"""module for tooltool operations"""
import os

from mozharness.base.errors import PythonErrorList
from mozharness.base.log import ERROR, FATAL
from mozharness.mozilla.proxxy import ProxxyMixin

TooltoolErrorList = PythonErrorList + [{
    'substr': 'ERROR - ', 'level': ERROR
}]


class TooltoolMixin(ProxxyMixin):
    """Mixin class for handling tooltool manifests.
    Requires self.config['tooltool_servers'] to be a list of base urls
    """
    def tooltool_fetch(self, manifest, bootstrap_cmd=None,
                       output_dir=None, privileged=False):
        """docstring for tooltool_fetch"""
        tooltool = self.query_exe('tooltool.py', return_type='list')
        cmd = tooltool
        # get the tooltools servers from configuration
        default_urls = set([s for s in self.config['tooltool_servers']])
        # to take full advantage of proxies, we need to calculate the proxied
        # urls and use this list to create the --url options.
        # proxied urls must be at the beginning of the --url options
        # default_urls must go at the end of the --url options

        # find the proxyied url, if any
        proxxy_urls = []
        for url in default_urls:
            proxxy_urls.extend(self.query_proxy_urls(url))

        # remove default_urls from the list of proxied urls
        # note: query_proxy_url returns a list and "url" is always in it
        proxxy_urls = set(proxxy_urls) - default_urls

        # extend the --url options
        # adding the proxied urls in first place
        for proxyied_url in proxxy_urls:
            cmd.extend(['--url', proxyied_url])
        # ... followed by urls from configuration
        for url in default_urls:
            cmd.extend(['--url', url])

        cmd.extend(['fetch', '-m', manifest, '-o'])
        self.retry(
            self.run_command,
            args=(cmd, ),
            kwargs={'cwd': output_dir,
                    'error_list': TooltoolErrorList,
                    'privileged': privileged,
                    },
            good_statuses=(0, ),
            error_message="Tooltool %s fetch failed!" % manifest,
            error_level=FATAL,
        )
        if bootstrap_cmd is not None:
            error_message = "Tooltool bootstrap %s failed!" % str(bootstrap_cmd)
            self.retry(
                self.run_command,
                args=(bootstrap_cmd, ),
                kwargs={'cwd': output_dir,
                        'error_list': TooltoolErrorList,
                        'privileged': privileged,
                        },
                good_statuses=(0, ),
                error_message=error_message,
                error_level=FATAL,
            )

    def create_tooltool_manifest(self, contents, path=None):
        """ Currently just creates a manifest, given the contents.
        We may want a template and individual values in the future?
        """
        if path is None:
            dirs = self.query_abs_dirs()
            path = os.path.join(dirs['abs_work_dir'], 'tooltool.tt')
        self.write_to_file(path, contents, error_level=FATAL)
        return path
