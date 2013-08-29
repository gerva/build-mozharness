#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****

import os
import urllib2
import stat

# download and parse html utils
def download_to_file(url, filename, ignoreErrors=[]):
    try:
        response = urllib2.urlopen(url)
        with open(filename, "w") as f:
            f.write(response.read())
    except urllib2.HTTPError as e:
            print 'The server couldn\'t fulfill the request.'
            print url
            print 'Error code: ', e.code
            raise
    except urllib2.URLError as e:
        if e.code in ignoreErrors:
            pass
        else:
            print 'We failed to reach a server.'
            print 'Reason: ', e.reason
            print url
            raise


def parse_html_page(url, left_delimiter, right_delimiter):
        request = urllib2.urlopen(url)
        elements = []
        for line in request.read().split('\n'):
            element = line.partition(left_delimiter)[2]
            element = element.partition('/"')[0]
            element = element.strip()
            elements.append(element)
        return elements


def latest_build_from(url):
    builds = parse_html_page(url, '<td><a href="', '/"')
    builds = filter(lambda b: 'build' in b, builds)
    b = 0
    for build in builds:
        b_temp = int(build.partition('build')[2])
        if b_temp > b:
            b = b_temp
    return "build{0}".format(b)


# files utils
def make_executable(filename):
    st = os.stat(filename)
    os.chmod(filename, st.st_mode | stat.S_IEXEC)

def find_file(root_dir, filename):
    """ find <root_dir> -type f -name <filename>
        returns a single file,
    """
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for f in filenames:
            if f == filename:
                return os.path.join(dirpath, f)

def find_directory(root_dir, dirname):
    """ find <root_dir> -type d -name <dirname>
        returns the first occurence
    """
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for d in dirnames:
            if d == dirname:
                return os.path.join(dirpath, d)

