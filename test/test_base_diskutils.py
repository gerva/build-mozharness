import datetime
import mock
import os
import unittest
import time
from mozharness.base.diskutils import convert_to, DiskutilsError, DiskSize, DiskInfo
from mozharness.base.diskutils import get_subdirs, find_dirs, enough_space, get_hg_subdirs, _ignore_dir, n_days_ago_timestamp, _dir_is_older_than, purge, get_subdirs_older_than, purge_hg_share


def mocked_now():
    return datetime.datetime(2015, 1, 10)


class TestDiskutils(unittest.TestCase):
    def test_convert_to(self):
        # 0 is 0 regardless from_unit/to_unit
        self.assertTrue(convert_to(size=0, from_unit='GB', to_unit='MB') == 0)
        size = 524288  # 512 * 1024
        # converting from/to same unit
        self.assertTrue(convert_to(size=size, from_unit='MB', to_unit='MB') == size)

        self.assertTrue(convert_to(size=size, from_unit='MB', to_unit='GB') == 512)

        self.assertRaises(DiskutilsError,
                          lambda: convert_to(size='a string', from_unit='MB', to_unit='MB'))
        self.assertRaises(DiskutilsError,
                          lambda: convert_to(size=0, from_unit='foo', to_unit='MB'))
        self.assertRaises(DiskutilsError,
                          lambda: convert_to(size=0, from_unit='MB', to_unit='foo'))


class TestDiskInfo(unittest.TestCase):

    def testDiskinfo_to(self):
        di = DiskInfo()
        self.assertTrue(di.unit == 'bytes')
        self.assertTrue(di.free == 0)
        self.assertTrue(di.used == 0)
        self.assertTrue(di.total == 0)
        # convert to GB
        di._to('GB')
        self.assertTrue(di.unit == 'GB')
        self.assertTrue(di.free == 0)
        self.assertTrue(di.used == 0)
        self.assertTrue(di.total == 0)

        str_ = "{0}".format(di)
        self.assertTrue(str_ == 'Disk space info (in GB) total: 0 used: 0 free: 0')


class MockStatvfs(object):
    def __init__(self):
        self.f_bsize = 0
        self.f_frsize = 0
        self.f_blocks = 0
        self.f_bfree = 0
        self.f_bavail = 0
        self.f_files = 0
        self.f_ffree = 0
        self.f_favail = 0
        self.f_flag = 0
        self.f_namemax = 0


class TestDiskSpace(unittest.TestCase):

    @mock.patch('mozharness.base.diskutils.DiskSize._posix_size')
    def testDiskSpace_wrong_path(self, mock_os):
        mock_os.side_effect = OSError('')
        self.assertRaises(DiskutilsError,
                          lambda: DiskSize().get_size(path='/', unit='GB'))

    @mock.patch('mozharness.base.diskutils.os')
    def testDiskSpacePosix(self, mock_os):
        ds = MockStatvfs()
        mock_os.statvfs.return_value = ds
        di = DiskSize()._posix_size('/')
        self.assertTrue(di.unit == 'bytes')
        self.assertTrue(di.free == 0)
        self.assertTrue(di.used == 0)
        self.assertTrue(di.total == 0)

    @mock.patch('mozharness.base.diskutils.ctypes')
    def testDiskSpaceWindows(self, mock_ctypes):
        mock_ctypes.windll.kernel32.GetDiskFreeSpaceExA.return_value = 0
        mock_ctypes.windll.kernel32.GetDiskFreeSpaceExW.return_value = 0
        di = DiskSize()._windows_size('/c/')
        self.assertTrue(di.unit == 'bytes')
        self.assertTrue(di.free == 0)
        self.assertTrue(di.used == 0)
        self.assertTrue(di.total == 0)

    @mock.patch('mozharness.base.diskutils.os')
    @mock.patch('mozharness.base.diskutils.ctypes')
    def testUnspportedPlafrom(self, mock_ctypes, mock_os):
        mock_os.statvfs.side_effect = AttributeError('')
        self.assertRaises(AttributeError, lambda: DiskSize()._posix_size('/'))
        mock_ctypes.windll.kernel32.GetDiskFreeSpaceExW.side_effect = AttributeError('')
        mock_ctypes.windll.kernel32.GetDiskFreeSpaceExA.side_effect = AttributeError('')
        self.assertRaises(AttributeError, lambda: DiskSize()._windows_size('/'))
        self.assertRaises(DiskutilsError, lambda: DiskSize().get_size(path='/', unit='GB'))


class TestDirectoriesUtil(unittest.TestCase):
    @mock.patch('mozharness.base.diskutils.os')
    def test_get_subdirs_basedir_not_a_dir(self, mock_os):
        """test get_subdirs, base_dir is not a directory"""
        mock_os.path.isdir.return_value = False
        results = list(get_subdirs('/'))
        self.assertEqual(results, [None])

    @mock.patch('mozharness.base.diskutils.os.path.isdir')
    @mock.patch('mozharness.base.diskutils.os.listdir')
    def test_get_subdirs(self, mock_listdir, mock_isdir):
        """test get_subdirs"""
        root_dir = '/'
        sub_dirs = ['test_1', 'test_2']
        mock_isdir.return_value = True
        mock_listdir.return_value = sub_dirs
        expected_results = [os.path.join(root_dir, element) for element in sub_dirs]
        results = list(get_subdirs(root_dir))
        self.assertEqual(results, expected_results)

    def test_find_dirs_wrong_depth(self):
        """tests find dir with 0 and -1 depth"""
        for depth in (0, -1):
            for directory in find_dirs('/', depth=0):
                self.assertEqual(directory, None)

    @mock.patch('mozharness.base.diskutils.get_subdirs')
    def test_find_dirs_directory_has_no_subdirs(self, mock_get_subdirs):
        """test find_dirs in a directory without subdirs"""
        mock_get_subdirs.return_value = []
        root_dir = 'test dir'
        for directory in find_dirs(root_dir, depth=1):
            self.assertEqual(directory, root_dir)

    @mock.patch('mozharness.base.diskutils.get_subdirs')
    def test_find_dirs_recusrion_ends(self, mock_get_subdirs):
        """check that we never reach a recursion error"""
        sub_dirs = ['test1', 'test2']
        # every subdir has 2 subdirs and this may generate an infinite loop
        # is recursion does not terminated
        mock_get_subdirs.return_value = sub_dirs
        root_dir = 'test dir'
        try:
            for directory in find_dirs(root_dir, depth=10):
                pass
        except RuntimeError:
            # recursion error
            raise AssertionError('recursion error')

    @mock.patch('mozharness.base.diskutils.DiskSize.get_size')
    def test_enough_space(self, mock_get_size):
        """test enough_space"""
        disk_info = DiskInfo()
        disk_info.free = 10
        mock_get_size.return_value = disk_info
        self.assertTrue(enough_space('/', requested_free_space=1, unit='GB'))
        self.assertFalse(enough_space('/', requested_free_space=100, unit='GB'))

    @mock.patch('mozharness.base.diskutils.find_dirs')
    def test_get_hg_subdirs(self, mock_find_dirs):
        """test get_hg_subdirs"""
        dirs = ['/tmp',
                '/tmp/hg_checkout',
                '/tmp/hg_checkout/.hg',
                '/tmp/hg_checkout/other_dir',
                '/tmp/not_an_hg_dir/']
        mock_find_dirs.return_value = dirs
        results = list(get_hg_subdirs('/tmp'))
        self.assertTrue(len(results) == 1)
        self.assertTrue('/tmp/hg_checkout' in results)

    def test_ignore_dir(self):
        """_ignore_dir test"""
        self.assertFalse(_ignore_dir(dirname='/', ignore_dirs=[]))
        self.assertTrue(_ignore_dir(dirname='/', ignore_dirs=['/']))
        self.assertTrue(_ignore_dir(dirname='/tmp/tmp_test',
                                    ignore_dirs=['*test']))

    def test_n_days_ago_timestamp(self):
        """test n_days_ago_timestamp conversion"""
        # this test is not complete
        result = n_days_ago_timestamp(n_days=5)
        self.assertTrue(result < time.time())

    @mock.patch('mozharness.base.diskutils.get_subdirs')
    @mock.patch('mozharness.base.diskutils._dir_is_older_than')
    def test_get_subdirs_older_than(self, mock_older, mock_subdirs):
        """test get_subdirs_older_than"""
        mock_older.return_value = True
        root_dir = '/'
        sub_dirs = [os.path.join(root_dir, d) for d in ('test1', 'test2')]
        mock_subdirs.return_value = sub_dirs
        results = list(get_subdirs_older_than(root_dir, n_days=0))
        self.assertEqual(results, sub_dirs)

    @mock.patch('mozharness.base.diskutils.os.path')
    def test_dir_is_older_than(self, mock_path):
        """test directory is older than n days"""
        mock_path.getmtime.return_value = 1
        self.assertTrue(_dir_is_older_than('/', n_days=1))
        mock_path.getmtime.return_value = time.time()
        self.assertFalse(_dir_is_older_than('/', n_days=20))
        self.assertRaises(DiskutilsError, lambda:  _dir_is_older_than(None, 1))
        mock_path.isdir.return_value = False
        self.assertRaises(DiskutilsError, lambda: _dir_is_older_than('/', 1))

    @mock.patch('mozharness.base.diskutils.enough_space')
    @mock.patch('mozharness.base.diskutils.rmtree')
    def test_purge_enough_disk_space(self, mock_rmtree, mock_space):
        """test purge with a lot of disk space (nothing to do)"""
        mock_space.return_value = True
        mock_rmtree.return_value = True
        self.assertIsNone(purge(base_dir='a non existing path',
                                ignore_dirs=[],
                                requested_free_space=0,
                                unit='GB',
                                older_than=14,
                                dry_run=True))

    @mock.patch('mozharness.base.diskutils.enough_space')
    @mock.patch('mozharness.base.diskutils.os')
    @mock.patch('mozharness.base.diskutils.get_subdirs_older_than')
    @mock.patch('mozharness.base.diskutils.rmtree')
    def test_purge_not_enough_disk_space(self, mock_rmtree, mock_subdirs,
                                         mock_os, mock_space):
        """test purge with low disk space (it triggers rmtree)"""
        mock_rmtree.return_value = True
        mock_space.return_value = False
        mock_os.isdir.return_value = True
        mock_subdirs.return_value = ['test1', 'test2']
        self.assertIsNone(purge(base_dir='a non existing path',
                                ignore_dirs=['test2'],
                                requested_free_space=0,
                                unit='GB',
                                older_than=14,
                                dry_run=True))

    @mock.patch('mozharness.base.diskutils._dir_is_older_than')
    @mock.patch('mozharness.base.diskutils.enough_space')
    @mock.patch('mozharness.base.diskutils.rmtree')
    @mock.patch('mozharness.base.diskutils.get_hg_subdirs')
    def test_purge_hg_share(self, mock_hg_dirs, mock_rmtree,
                            mock_space, mock_older):
        """test purge_hg_share"""
        mock_space.return_value = True
        mock_rmtree.return_value = True
        self.assertIsNone(purge_hg_share(share_dir='a dir',
                                         requested_free_space=10,
                                         unit='GB',
                                         older_than=14))

        mock_space.return_value = False
        mock_older.return_value = True
        mock_hg_dirs.return_value = ['/tmp/hg_1', '/tmp/hg_2']
        self.assertIsNone(purge_hg_share(share_dir='a dir',
                                         requested_free_space=10,
                                         unit='GB',
                                         older_than=14))

if __name__ == '__main__':
    unittest.main()
