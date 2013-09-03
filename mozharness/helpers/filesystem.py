# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****

import os


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
