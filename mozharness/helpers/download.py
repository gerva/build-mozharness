#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****

import urllib2


#TODO add a logger, remove prints
# download and parse html utilities
def read_from_url(url, ignoreHTTPErrors=[]):
    """ downloads from url to filename ignoring http errors
        from the ingoreErrors list"""
    try:
        return urllib2.urlopen(url)
    except urllib2.HTTPError as e:
            print 'The server couldn\'t fulfill the request.'
            print url
            print 'Error code: ', e.code
            raise
    except urllib2.URLError as e:
        if e.code in ignoreHTTPErrors:
            pass
        else:
            print 'We failed to reach a server.'
            print 'Reason: ', e.reason
            print url
            raise


def parse_html(url, left_delimiter, right_delimiter, ignoreHTTPErrors=[]):
    """ a very simple html parser. It reads from url and
        parses the page line by line, returning a list of elements
        between left and right delimiters
    """
    remote_page = read_from_url(url, ignoreHTTPErrors)
    elements = []
    for line in remote_page.read().split('\n'):
        element = line.partition(left_delimiter)[2]
        element = element.partition('/"')[0]
        element = element.strip()
        elements.append(element)
    return elements


def to_file(url, filename, ignoreHTTPErrors=[]):
    remote_file = read_from_url(url, ignoreHTTPErrors)
    with open(filename, "w") as f:
        f.write(remote_file.read())


def get_latest_build_number(url):
    """ return latest build number from url or 0
        when no builds are available"""
    builds = parse_html(url, '<td><a href="', '/"')
    builds = filter(lambda b: 'build' in b, builds)
    b = 0
    for build in builds:
        b_temp = int(build.partition('build')[2])
        if b_temp > b:
            b = b_temp
    return "build{0}".format(b)
