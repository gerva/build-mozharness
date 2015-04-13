"""Disk utility module, no mixins here!

    examples:
    1) get disk size
    from mozharness.base.diskutils import DiskInfo, DiskutilsError
    ...
    try:
        DiskSize().get_size(path='/', unit='Mb')
    except DiskutilsError as e:
        # manage the exception e.g: log.error(e)
        pass
    log.info("%s" % di)


    2) convert disk size:
    from mozharness.base.diskutils import DiskutilsError, convert_to
    ...
    file_size = <function that gets file size in bytes>
    # convert file_size to GB
    try:
        file_size = convert_to(file_size, from_unit='bytes', to_unit='GB')
    except DiskutilsError as e:
        # manage the exception e.g: log.error(e)
        pass

"""
import ctypes
import datetime
import logging
import os
import sys
import time
from fnmatch import fnmatch
from mozharness.base.log import INFO, numeric_log_level
from mozharness.base.script import rmtree

# use mozharness log
log = logging.getLogger(__name__)


class DiskutilsError(Exception):
    """Exception thrown by Diskutils module"""
    pass


def convert_to(size, from_unit, to_unit):
    """Helper method to convert filesystem sizes to kB/ MB/ GB/ TB/
       valid values for source_format and destination format are:
           * bytes
           * kB
           * MB
           * GB
           * TB
        returns: size converted from source_format to destination_format.
    """
    sizes = {'bytes': 1,
             'kB': 1024,
             'MB': 1024 * 1024,
             'GB': 1024 * 1024 * 1024,
             'TB': 1024 * 1024 * 1024 * 1024}
    try:
        df = sizes[to_unit]
        sf = sizes[from_unit]
        return size * sf / df
    except KeyError:
        raise DiskutilsError('conversion error: Invalid source or destination format')
    except TypeError:
        raise DiskutilsError('conversion error: size (%s) is not a number' % size)


class DiskInfo(object):
    """Stores basic information about the disk"""
    def __init__(self):
        self.unit = 'bytes'
        self.free = 0
        self.used = 0
        self.total = 0

    def __str__(self):
        string = ['Disk space info (in %s)' % self.unit]
        string += ['total: %s' % self.total]
        string += ['used: %s' % self.used]
        string += ['free: %s' % self.free]
        return " ".join(string)

    def _to(self, unit):
        from_unit = self.unit
        to_unit = unit
        self.free = convert_to(self.free, from_unit=from_unit, to_unit=to_unit)
        self.used = convert_to(self.used, from_unit=from_unit, to_unit=to_unit)
        self.total = convert_to(self.total, from_unit=from_unit, to_unit=to_unit)
        self.unit = unit


class DiskSize(object):
    """DiskSize object
    """
    @staticmethod
    def _posix_size(path):
        """returns the disk size in bytes
           disk size is relative to path
        """
        # we are on a POSIX system
        st = os.statvfs(path)
        disk_info = DiskInfo()
        disk_info.free = st.f_bavail * st.f_frsize
        disk_info.used = (st.f_blocks - st.f_bfree) * st.f_frsize
        disk_info.total = st.f_blocks * st.f_frsize
        return disk_info

    @staticmethod
    def _windows_size(path):
        """returns size in bytes, works only on windows platforms"""
        # we're on a non POSIX system (windows)
        # DLL call
        disk_info = DiskInfo()
        dummy = ctypes.c_ulonglong()  # needed by the dll call but not used
        total = ctypes.c_ulonglong()  # stores the total space value
        free = ctypes.c_ulonglong()   # stores the free space value
        # depending on path format (unicode or not) and python version (2 or 3)
        # we need to call GetDiskFreeSpaceExW or GetDiskFreeSpaceExA
        called_function = ctypes.windll.kernel32.GetDiskFreeSpaceExA
        if isinstance(path, unicode) or sys.version_info >= (3,):
            called_function = ctypes.windll.kernel32.GetDiskFreeSpaceExW
        # we're ready for the dll call. On error it returns 0
        if called_function(path,
                           ctypes.byref(dummy),
                           ctypes.byref(total),
                           ctypes.byref(free)) != 0:
            # success, we can use the values returned by the dll call
            disk_info.free = free.value
            disk_info.total = total.value
            disk_info.used = total.value - free.value
        return disk_info

    @staticmethod
    def get_size(path, unit, log_level=INFO):
        """Disk info stats:
                total => size of the disk
                used  => space used
                free  => free space
          In case of error raises a DiskutilError Exception
        """
        try:
            # let's try to get the disk size using os module
            disk_info = DiskSize()._posix_size(path)
        except OSError as e:
            # No such file or directory
            raise DiskutilsError(e.message)
        except AttributeError:
            try:
                # os module failed. let's try to get the size using
                # ctypes.windll...
                disk_info = DiskSize()._windows_size(path)
            except AttributeError:
                # No luck! This is not a posix nor window platform
                # raise an exception
                raise DiskutilsError('Unsupported platform')
        disk_info._to(unit)
        lvl = numeric_log_level(log_level)
        log.log(lvl, msg="%s" % disk_info)
        return disk_info


def get_subdirs(base_dir):
    if not os.path.isdir(base_dir):
        yield {'path': None}
    for sub_path in os.listdir(base_dir):
        path = os.path.join(base_dir, sub_path)
        if not os.path.isdir(path):
            continue
        yield {'path': path}


def sub_dirs_mtime(base_dir):
    """
        returns a list of sub directories of base_dir older_than
        Args:
            base_dir (str):
            older_than (time):
        returns:
            list: sub_directories older than older_than

    """
    for sub_dir in get_subdirs(base_dir):
        mtime = None
        path = sub_dir['path']
        if path:
            mtime = os.path.getmtime(path)
            yield {'path': path, 'mtime': mtime}


def _ignore_dir(dirname, ignore_dirs):
    for ignore_d in ignore_dirs:
        if fnmatch(dirname, ignore_d):
            return True
    return False


def remove_subdirs(base_dir, ignore_dirs, requested_free_space=12, unit='GB',
                   older_than=14, dry_run=False):
    # removing older directories
    free_space = DiskSize().get_size(path=base_dir, unit=unit).free
    if free_space > requested_free_space:
        print('Requested space: %s, available space: %s [%s]' % (requested_free_space, free_space, unit))
        return

    # step 1: remove old directories
    for d in get_subdirs_older_than(base_dir, older_than):
        if not _ignore_dir(d, ignore_dirs):
            print('removing %s' % d)
            print("Deleting %s because it's older than %s days" % (d, older_than))
            # rmtree() calls here
        else:
            print('Ignoring %s' % d)

    # step 2: remove other directories
    if free_space > requested_free_space:
        print('Requested space: %s, available space: %s [%s]' % (requested_free_space, free_space, unit))
        return


def get_subdirs_older_than(base_dir, n_days):
    n_days_timestamp = n_days_ago_timestamp(n_days)
    for d in sub_dirs_mtime(base_dir):
        if d['mtime'] < n_days_timestamp:
            yield d['path']


def n_days_ago_timestamp(n_days):
    """

    """
    now = datetime.datetime.now()
    then = now - datetime.timedelta(days=n_days)
    return time.mktime(then.timetuple())


def purge_hg_share(share_dir, requested_free_space, max_age, dry_run=False):
    # Find hg directories
    hg_dirs = []
    for root, dirs, files in os.walk(share_dir):
        for d in dirs[:]:
            path = os.path.join(root, d, '.hg')
            if os.path.exists(path) or os.path.exists(path + clobber_suffix):
                hg_dirs.append(os.path.join(root, d))
                # Remove d from the list so we don't go traversing down into it
                dirs.remove(d)

    # Now we have a list of hg directories, call purge on them
    for hg_dir in hg_dirs:
        remove_subdirs(hg_dir, ignore_dirs=[],
                       requested_free_space=requested_free_space,
                       older_than=max_age, dry_run=dry_run)

    # Clean up empty directories
    for d in hg_dirs:
        if not os.path.exists(os.path.join(d, '.hg')):
            print "Cleaning up", d
            if not dry_run:
                rmtree(d)

