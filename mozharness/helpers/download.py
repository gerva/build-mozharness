#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****


def _extract_from_html(filename, left_delimiter, right_delimiter, ignoreHTTPErrors=[]):
    """ a very simple html parser. It reads a file and
        parses the page line by line, returning a list of elements
        between left and right delimiters
    """
    elements = []
    with open(filename, 'r') as f:
        for line in f.read().split('\n'):
            element = line.partition(left_delimiter)[2]
            element = element.partition('/"')[0]
            element = element.strip()
            elements.append(element)
    return elements


def get_versions_numbers(filename):
    """ reads filename and returns a list of version availble
        only lines including the word '-candidates' are included in the output.
        All lines including the 'esr' word are excluded
    """
    versions = _extract_from_html(filename, 'href="', '/"')
    versions = filter(lambda v: '-candidates' in v, versions)
    versions = filter(lambda v: 'esr' not in v, versions)
    return [v.partition('-candidates')[0] for v in versions]


def get_last_version_number(filename):
    """ reads filename and returns the latest version available
        version must be in the XX.YYbZZ format
    """
    def to_string(v, padding=5):
        """ tuple to string using padding so it can be sorted (dictionary sort)"""
        return "".join(["{0}".format(str(n).zfill(padding)) for n in v])
    v = (0, 0, 0)
    for version in get_versions_numbers(filename):
        # version = 24.0b5
        # major = 24
        # minor = 0
        # beta = 5
        major, sep, rest = version.partition(".")
        minor, sep, beta = rest.partition("b")
        try:
            v_temp = (int(major), int(minor), int(beta))
            if to_string(v) < to_string(v_temp):
                v = v_temp
        except ValueError:
            # int(...) failed:
            # major, minor and/or beta are not numbers, skip
            pass
    return "{0}.{1}b{2}".format(*v)


def get_latest_build_number(filename):
    """ return latest build number from url or 0
        when no builds are available"""
    builds = _extract_from_html(filename, '<td><a href="', '/"')
    builds = filter(lambda b: 'build' in b, builds)
    b = 0
    for build in builds:
        b_temp = int(build.partition('build')[2])
        if b_temp > b:
            b = b_temp
    return "build{0}".format(b)
