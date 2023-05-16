from zirconium import test_with_config
from autoinject import injector
from erddaputil.erddap.datasets import ErddapDatasetManager
import unittest
import pathlib
import os
import time
import shutil


TEST_DATA_DIR = pathlib.Path(__file__).parent / "test_data"


class ErddapUtilTestCase(unittest.TestCase):

    def setUp(self):
        to_copy = [
            "datasets.d/dataset_a.xml",
            "datasets.d/dataset_b.xml",
            "datasets.template.xml",
            "datasets.xml",
            "bpd/.email_block_list.txt",
            "bpd/.ip_block_list.txt",
            "bpd/.unlimited_allow_list.txt"
        ]
        for f in to_copy:
            shutil.copy2(
                TEST_DATA_DIR / "originals" / f,
                TEST_DATA_DIR / "good_example" / f
            )
        cleanup = [
            TEST_DATA_DIR / "good_example" / "bpd" / "flag",
            TEST_DATA_DIR / "good_example" / "bpd" / "badFilesFlag",
            TEST_DATA_DIR / "good_example" / "bpd" / "hardFlag",
        ]
        for d in cleanup:
            if d.exists():
                for f in os.scandir(d):
                    os.unlink(f.path)
                os.rmdir(d)

    def assertInFile(self, file_path, content):
        with open(file_path, "r") as h:
            if content not in h.read():
                raise AssertionError(f"Content [{content}] not found in {file_path}")

    def assertFileHasLine(self, file_path, line):
        with open(file_path, "r") as h:
            if not any(l.strip() == line for l in h):
                raise AssertionError(f"Line [{line}] not found in {file_path} when expected")

    def assertNotFileHasLine(self, file_path, line):
        with open(file_path, "r") as h:
            if any(l.strip() == line for l in h):
                raise AssertionError(f"Line [{line}] found in {file_path} when unexpected")

    def assertRaises(self, exc: type, cb: callable, *args, **kwargs):
        try:
            super().assertRaises(exc, cb, *args, **kwargs)
        except AssertionError:
            params = [str(x) for x in args]
            params.extend(f"{k}={str(kwargs[k])}" for k in kwargs)
            raise AssertionError(f"{exc.__name__} not raised by {cb.__name__}({','.join(params)})")


class TestConfigChecks(ErddapUtilTestCase):

    @injector.test_case()
    def test_defaults(self):
        edm = ErddapDatasetManager()
        self.assertRaises(ValueError, edm.check_can_compile)
        self.assertRaises(ValueError, edm.check_datasets_exist)
        self.assertRaises(ValueError, edm.check_can_reload)
        self.assertRaises(ValueError, edm.check_can_http)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    @test_with_config(("erddaputil", "erddap", "base_url"), "http://localhost:9100/erddap")
    def test_good(self):
        edm = ErddapDatasetManager()
        self.assertTrue(edm.check_can_compile())
        self.assertTrue(edm.check_datasets_exist())
        self.assertTrue(edm.check_can_reload())
        self.assertTrue(edm.check_can_http())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "no" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    @test_with_config(("erddaputil", "erddap", "base_url"), "http://localhost:9100/erddap")
    def test_bad_datasets_template(self):
        edm = ErddapDatasetManager()
        self.assertRaises(ValueError, edm.check_can_compile)
        self.assertTrue(edm.check_datasets_exist())
        self.assertTrue(edm.check_can_reload())
        self.assertTrue(edm.check_can_http())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "no" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    @test_with_config(("erddaputil", "erddap", "base_url"), "http://localhost:9100/erddap")
    def test_bad_datasets_d(self):
        edm = ErddapDatasetManager()
        self.assertRaises(ValueError, edm.check_can_compile)
        self.assertTrue(edm.check_datasets_exist())
        self.assertTrue(edm.check_can_reload())
        self.assertTrue(edm.check_can_http())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "no" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    @test_with_config(("erddaputil", "erddap", "base_url"), "http://localhost:9100/erddap")
    def test_bad_datasets_xml(self):
        edm = ErddapDatasetManager()
        self.assertRaises(ValueError, edm.check_can_compile)
        self.assertRaises(ValueError, edm.check_datasets_exist)
        self.assertTrue(edm.check_can_reload())
        self.assertTrue(edm.check_can_http())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.fresh.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    @test_with_config(("erddaputil", "erddap", "base_url"), "http://localhost:9100/erddap")
    def test_fresh_datasets_xml(self):
        edm = ErddapDatasetManager()
        self.assertTrue(edm.check_can_compile())
        self.assertRaises(ValueError, edm.check_datasets_exist)
        self.assertTrue(edm.check_can_reload())
        self.assertTrue(edm.check_can_http())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "no" / "bpd")
    @test_with_config(("erddaputil", "erddap", "base_url"), "http://localhost:9100/erddap")
    def test_bad_bpd(self):
        edm = ErddapDatasetManager()
        self.assertRaises(ValueError, edm.check_can_compile)
        self.assertTrue(edm.check_datasets_exist())
        self.assertRaises(ValueError, edm.check_can_reload)
        self.assertTrue(edm.check_can_http())


class TestReloadDataset(ErddapUtilTestCase):

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_reload_flag_0(self):
        expected_file = TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "foobar0"
        edm = ErddapDatasetManager()
        self.assertFalse(expected_file.exists())
        edm.reload_dataset("foobar0", 0, True)
        self.assertTrue(expected_file.exists())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_reload_multiple(self):
        expected_files = [
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "foo",
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "bar",
        ]
        edm = ErddapDatasetManager()
        self.assertFalse(expected_files[0].exists())
        self.assertFalse(expected_files[1].exists())
        edm.reload_dataset("foo", 0, True)
        self.assertTrue(expected_files[0].exists())
        self.assertFalse(expected_files[1].exists())
        # Try doing the same one to make sure this doesn't error
        edm.reload_dataset("foo", 0, True)
        self.assertTrue(expected_files[0].exists())
        self.assertFalse(expected_files[1].exists())
        edm.reload_dataset("bar", 0, True)
        self.assertTrue(expected_files[0].exists())
        self.assertTrue(expected_files[1].exists())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_reload_multiple_commas(self):
        expected_files = [
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "foo2",
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "bar2",
        ]
        edm = ErddapDatasetManager()
        self.assertFalse(expected_files[0].exists())
        self.assertFalse(expected_files[1].exists())
        edm.reload_dataset("foo2,bar2,,foo2", 0, True)
        self.assertTrue(expected_files[0].exists())
        self.assertTrue(expected_files[1].exists())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_reload_flag_1(self):
        expected_file = TEST_DATA_DIR / "good_example" / "bpd" / "badFilesFlag" / "foobar1"
        edm = ErddapDatasetManager()
        self.assertFalse(expected_file.exists())
        edm.reload_dataset("foobar1", 1, True)
        self.assertTrue(expected_file.exists())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_reload_flag_upgrade(self):
        not_expected_file = TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "foobarup"
        expected_file = TEST_DATA_DIR / "good_example" / "bpd" / "badFilesFlag" / "foobarup"
        edm = ErddapDatasetManager()
        self.assertFalse(not_expected_file.exists())
        self.assertFalse(expected_file.exists())
        edm.reload_dataset("foobarup", 0, False)
        edm.reload_dataset("foobarup", 1, False)
        edm.flush(True)
        self.assertFalse(not_expected_file.exists())
        self.assertTrue(expected_file.exists())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_reload_flag_2(self):
        expected_file = TEST_DATA_DIR / "good_example" / "bpd" / "hardFlag" / "foobar2"
        edm = ErddapDatasetManager()
        self.assertFalse(expected_file.exists())
        edm.reload_dataset("foobar2", 2, True)
        self.assertTrue(expected_file.exists())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_reload_flag_bad(self):
        edm = ErddapDatasetManager()
        self.assertRaises(ValueError, edm.reload_dataset, "foobar3", 3, True)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    @test_with_config(("erddaputil", "dataset_manager", "max_pending"), 3)
    def test_reload_max_pending(self):
        expected_files = [
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "max_pending0",
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "max_pending1",
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "max_pending2",
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "max_pending3"
        ]
        edm = ErddapDatasetManager()
        self.assertFalse(expected_files[0].exists())
        self.assertFalse(expected_files[1].exists())
        self.assertFalse(expected_files[2].exists())
        self.assertFalse(expected_files[3].exists())
        edm.reload_dataset("max_pending0")
        edm.reload_dataset("max_pending1")
        edm.reload_dataset("max_pending2")
        self.assertFalse(expected_files[0].exists())
        self.assertFalse(expected_files[1].exists())
        self.assertFalse(expected_files[2].exists())
        self.assertFalse(expected_files[3].exists())
        edm.reload_dataset("max_pending3")
        self.assertTrue(expected_files[0].exists())
        self.assertFalse(expected_files[1].exists())
        self.assertFalse(expected_files[2].exists())
        self.assertFalse(expected_files[3].exists())
        edm.flush(True)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    @test_with_config(("erddaputil", "dataset_manager", "max_pending"), 99)
    @test_with_config(("erddaputil", "dataset_manager", "max_delay_seconds"), 2)
    def test_reload_max_time(self):
        expected_files = [
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "max_time0",
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "max_time1",
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "max_time2",
        ]
        edm = ErddapDatasetManager()
        self.assertFalse(expected_files[0].exists())
        self.assertFalse(expected_files[1].exists())
        self.assertFalse(expected_files[2].exists())
        edm.reload_dataset("max_time0")
        edm.reload_dataset("max_time1")
        self.assertFalse(expected_files[0].exists())
        self.assertFalse(expected_files[1].exists())
        self.assertFalse(expected_files[2].exists())
        time.sleep(2.1)
        edm.reload_dataset("max_time2")
        self.assertTrue(expected_files[0].exists())
        self.assertTrue(expected_files[1].exists())
        self.assertFalse(expected_files[2].exists())
        edm.flush(True)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_reload_all(self):
        test_files = [
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "existing_a",
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "existing_b",
            TEST_DATA_DIR / "good_example" / "bpd" / "flag" / "existing_c"
        ]
        edm = ErddapDatasetManager()
        self.assertFalse(test_files[0].exists())
        self.assertFalse(test_files[1].exists())
        self.assertFalse(test_files[2].exists())
        edm.reload_all_datasets(0, True)
        self.assertTrue(test_files[0].exists())
        self.assertTrue(test_files[1].exists())
        self.assertFalse(test_files[2].exists())


class TestSetActiveFlag(ErddapUtilTestCase):

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_set_active_false(self):
        ds_file = TEST_DATA_DIR / "good_example" / "datasets.d" / "dataset_a.xml"
        self.assertInFile(ds_file, 'active="true"')
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        edm.set_active_flag("dataset_a", False)
        self.assertInFile(ds_file, 'active="false"')
        self.assertIsNotNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_set_active_true(self):
        ds_file = TEST_DATA_DIR / "good_example" / "datasets.d" / "dataset_b.xml"
        self.assertInFile(ds_file, 'active="false"')
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        edm.set_active_flag("dataset_b", True)
        self.assertInFile(ds_file, 'active="true"')
        self.assertIsNotNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_reset_active_true(self):
        ds_file = TEST_DATA_DIR / "good_example" / "datasets.d" / "dataset_a.xml"
        self.assertInFile(ds_file, 'active="true"')
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        edm.set_active_flag("dataset_a", True)
        self.assertInFile(ds_file, 'active="true"')
        self.assertIsNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_reset_active_false(self):
        ds_file = TEST_DATA_DIR / "good_example" / "datasets.d" / "dataset_b.xml"
        self.assertInFile(ds_file, 'active="false"')
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        edm.set_active_flag("dataset_b", False)
        self.assertInFile(ds_file, 'active="false"')
        self.assertIsNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_dataset_not_exist(self):
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertRaises(ValueError, edm.set_active_flag, "dataset_c", False)
        self.assertIsNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_dataset_is_invalid(self):
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertRaises(ValueError, edm.set_active_flag, "invalid_d", False)
        self.assertIsNone(edm._compilation_requested)


class TestBlockAllowLists(ErddapUtilTestCase):

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_block_ip(self):
        ip_block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".ip_block_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertNotFileHasLine(ip_block_file, "10.0.0.0")
        edm.update_ip_block_list("10.0.0.0", True)
        self.assertFileHasLine(ip_block_file, "10.0.0.0")
        self.assertIsNotNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_block_already_blocked_ip(self):
        ip_block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".ip_block_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertFileHasLine(ip_block_file, "10.0.0.1")
        edm.update_ip_block_list("10.0.0.1", True)
        self.assertFileHasLine(ip_block_file, "10.0.0.1")
        self.assertIsNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_ip_validation(self):
        ip_block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".ip_block_list.txt"
        edm = ErddapDatasetManager()
        valid_tests = [
            # Raw IP
            "10.0.0.0",
            # ERDDAP Ranges
            "10.0.0.*",
            "10.0.*.*",
            # Subnets
            "10.0.0.0/16",
            "10.0.0.0/22",
            "10.0.0.0/255.0.0.0",
        ]
        for valid in valid_tests:
            self.assertNotFileHasLine(ip_block_file, valid)
            edm.update_ip_block_list(valid, True)
            self.assertFileHasLine(ip_block_file, valid)
        invalid_tests = [
            # Not an IP
            "hello_World",
            # Invalid ERDDAP ranges
            "10.*.*.*",
            "*.*.*.*",
            "10.0.*.0",
            # Invalid subnets
            "10.0.0.0/64",
            # Invalid but IP-like
            "300.100.0.2",
            "10.0.0.0/300.0.0.0",
            "a.b.c.d",
            "a.0.0.0",
            "0.a.0.0",
            "0.0.a.0",
            "0.0.0.a",
            "300.0.*.*",
            "0.300.*.*",
            "0.0.300.*",
            "0.0.*",
            "0.0.0.*.0",
            "hello_World*"
            "-1.0.0.0",
            "0.-1.0.0",
            "0.0.-1.0",
            "0.0.0.-1",
        ]
        for invalid in invalid_tests:
            self.assertNotFileHasLine(ip_block_file, invalid)
            self.assertRaises(ValueError, edm.update_ip_block_list, invalid, True)
            self.assertNotFileHasLine(ip_block_file, invalid)
