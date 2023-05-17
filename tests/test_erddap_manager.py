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
            TEST_DATA_DIR / "good_example" / "bpd" / "decompressed" / "_a" / "existing_a",
            TEST_DATA_DIR / "good_example" / "bpd" / "decompressed" / "_b" / "existing_b",
            TEST_DATA_DIR / "good_example" / "bpd" / "decompressed" / "_c" / "existing_c",
        ]
        for d in cleanup:
            if d.exists():
                for f in os.scandir(d):
                    os.unlink(f.path)
                os.rmdir(d)

    def make_dir_recursive(self, dir_path: pathlib.Path):
        if not dir_path.exists():
            self.make_dir_recursive(dir_path.parent)
            dir_path.mkdir()

    def assertInXMLTag(self, content, tag_name, inner_content):
        with_braces = f"<{tag_name}>"
        if with_braces not in content:
            raise AssertionError(f"Tag {tag_name} missing")
        start = content.find(with_braces)
        end = content.find("</", start + 1)
        if inner_content not in content[start+len(with_braces):end]:
            raise AssertionError(f"Tag {tag_name} missing content {inner_content}")

    def assertNotInXMLTag(self, content, tag_name, inner_content):
        with_braces = f"<{tag_name}>"
        if with_braces not in content:
            raise AssertionError(f"Tag {tag_name} missing")
        start = content.find(with_braces)
        end = content.find("</", start + 1)
        if inner_content in content[start+len(with_braces):end]:
            raise AssertionError(f"Tag {tag_name} has unexpected content {inner_content}")

    def assertInFile(self, file_path, content):
        with open(file_path, "r") as h:
            if content not in h.read():
                raise AssertionError(f"Content [{content}] not found in {file_path} as expected")

    def assertNotInFile(self, file_path, content):
        with open(file_path, "r") as h:
            if content in h.read():
                raise AssertionError(f"Content [{content}] unexpectedly found in {file_path}")

    def assertFileHasLine(self, file_path, line):
        with open(file_path, "r") as h:
            if not any(l.strip("\r\n") == line for l in h):
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

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    def test_list_datasets(self):
        edm = ErddapDatasetManager()
        ds_list = edm.list_datasets()
        self.assertIn("existing_a", ds_list)
        self.assertIn("existing_b", ds_list)
        self.assertIn("existing_c", ds_list)


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
    def test_unblock_ip(self):
        ip_block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".ip_block_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertFileHasLine(ip_block_file, "10.0.0.2")
        edm.update_ip_block_list("10.0.0.2", False)
        self.assertNotFileHasLine(ip_block_file, "10.0.0.2")
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
        self.assertFileHasLine(ip_block_file, "10.0.0.2")
        edm.update_ip_block_list("10.0.0.2", True)
        self.assertFileHasLine(ip_block_file, "10.0.0.2")
        self.assertIsNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_unblock_already_unblocked_ip(self):
        ip_block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".ip_block_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertNotFileHasLine(ip_block_file, "10.0.0.0")
        edm.update_ip_block_list("10.0.0.0", False)
        self.assertNotFileHasLine(ip_block_file, "10.0.0.0")
        self.assertIsNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_allow_unlimited_ip(self):
        unlimited_allow_file = TEST_DATA_DIR / "good_example" / "bpd" / ".unlimited_allow_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertNotFileHasLine(unlimited_allow_file, "10.0.0.0")
        edm.update_allow_unlimited_list("10.0.0.0", True)
        self.assertFileHasLine(unlimited_allow_file, "10.0.0.0")
        self.assertIsNotNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_unallow_unlimited_ip(self):
        unlimited_allow_file = TEST_DATA_DIR / "good_example" / "bpd" / ".unlimited_allow_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertFileHasLine(unlimited_allow_file, "10.0.0.1")
        edm.update_allow_unlimited_list("10.0.0.1", False)
        self.assertNotFileHasLine(unlimited_allow_file, "10.0.0.1")
        self.assertIsNotNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_allow_unlimited_already_allowed_ip(self):
        unlimited_allow_file = TEST_DATA_DIR / "good_example" / "bpd" / ".unlimited_allow_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertFileHasLine(unlimited_allow_file, "10.0.0.1")
        edm.update_allow_unlimited_list("10.0.0.1", True)
        self.assertFileHasLine(unlimited_allow_file, "10.0.0.1")
        self.assertIsNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_unallow_unlimited_already_unallowed_ip(self):
        unlimited_allow_file = TEST_DATA_DIR / "good_example" / "bpd" / ".unlimited_allow_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertNotFileHasLine(unlimited_allow_file, "10.0.0.0")
        edm.update_allow_unlimited_list("10.0.0.0", False)
        self.assertNotFileHasLine(unlimited_allow_file, "10.0.0.0")
        self.assertIsNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_block_multiple(self):
        block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".email_block_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertNotFileHasLine(block_file, "me3@example.com")
        self.assertNotFileHasLine(block_file, "me4@example.com")
        edm.update_email_block_list("me3@example.com,me4@example.com", True)
        self.assertFileHasLine(block_file, "me3@example.com")
        self.assertFileHasLine(block_file, "me4@example.com")
        self.assertIsNotNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"),
                      TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_block_multiple_iter(self):
        block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".email_block_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertNotFileHasLine(block_file, "me3@example.com")
        self.assertNotFileHasLine(block_file, "me4@example.com")
        edm.update_email_block_list(["me3@example.com", "me4@example.com"], True)
        self.assertFileHasLine(block_file, "me3@example.com")
        self.assertFileHasLine(block_file, "me4@example.com")
        self.assertIsNotNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_block_email(self):
        block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".email_block_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertNotFileHasLine(block_file, "me@example.com")
        edm.update_email_block_list("me@example.com", True)
        self.assertFileHasLine(block_file, "me@example.com")
        self.assertIsNotNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_unblock_email(self):
        block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".email_block_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertFileHasLine(block_file, "me2@example.com")
        edm.update_email_block_list("me2@example.com", False)
        self.assertNotFileHasLine(block_file, "me2@example.com")
        self.assertIsNotNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_block_already_blocked_email(self):
        block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".email_block_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertFileHasLine(block_file, "me2@example.com")
        edm.update_email_block_list("me2@example.com", True)
        self.assertFileHasLine(block_file, "me2@example.com")
        self.assertIsNone(edm._compilation_requested)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_unblock_already_unblocked_email(self):
        block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".email_block_list.txt"
        edm = ErddapDatasetManager()
        self.assertIsNone(edm._compilation_requested)
        self.assertNotFileHasLine(block_file, "me@example.com")
        edm.update_email_block_list("me@example.com", False)
        self.assertNotFileHasLine(block_file, "me@example.com")
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
            "hello_World*",
            "-1.0.0.0",
            "0.-1.0.0",
            "0.0.-1.0",
            "0.0.0.-1",
        ]
        for invalid in invalid_tests:
            self.assertNotFileHasLine(ip_block_file, invalid)
            self.assertRaises(ValueError, edm.update_ip_block_list, invalid, True)
            self.assertNotFileHasLine(ip_block_file, invalid)

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_email_validation(self):
        email_block_file = TEST_DATA_DIR / "good_example" / "bpd" / ".email_block_list.txt"
        edm = ErddapDatasetManager()
        valid_tests = [
            "me@example.com",
            "example@email.com",
            "example.first.middle.lastname@email.com",
            "example@subdomain.email.com",
            "example+firstname+lastname@email.com",
            "example@234.234.234.234",
            "example@[234.234.234.234]",
            "\"example\"@email.com",
            "0987654321@example.com",
            "example@email-one.com",
            "_______@email.com",
            "example@email.name",
            "example@email.museum",
            "example@email.co.jp",
            "example.firstname-lastname@email.com",
            r"extremely.\"odd\\unusual\"@example.com",
            "extremely.unusual.\"@\".unusual.com@example.com",
            # NB: ERDDAP doesn't let you use commas, so I've removed a comma from this example
            r"very.\"():;<>[]\".VERY.\"very@\\ \"very.unusual@strange.email.example.com",
        ]
        for valid in valid_tests:
            self.assertNotFileHasLine(email_block_file, valid.lower())
            edm.update_email_block_list(valid, True)
            self.assertFileHasLine(email_block_file, valid.lower())
        invalid_tests = [
            "no_at_example.com",
            "no,commas@example.com",
            "bad_domain@example",
            "plaintextaddress",
            "@#@@##@%^%#$@#$@#.com",
            "@email.com",
            #"John Doe <example@email.com>",
            "example.email.com",
            #"example@example@email.com",
            #".example@email.com",
            #"example.@email.com",
            #"example...example@email.com",
            "おえあいう@example.com",
            #"example@email.com (John Doe)",
            "example@email",
            #"example@-email.com",
            #"example@email.web",
            #"example@111.222.333.44444",
            #"example@email...com",
            #"CAT...123@email.com",
            r"”(),:;<>[\]@email.com",
            #"obviously\"not\"correct@email.com",
            #r"example\ is\"especially\"not\allowed@email.com"
        ]
        for invalid in invalid_tests:
            self.assertNotFileHasLine(email_block_file, invalid.lower())
            self.assertRaises(ValueError, edm.update_email_block_list, invalid, True)
            self.assertNotFileHasLine(email_block_file, invalid.lower())


class TestCacheClear(ErddapUtilTestCase):

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_remove_one(self):
        test_file = TEST_DATA_DIR / "good_example" / "bpd" / "decompressed" / "_a" / "existing_a" / "existing_a.nc"
        self.make_dir_recursive(test_file.parent)
        with open(test_file, "w") as h:
            h.write("1")
        self.assertTrue(test_file.exists())
        edm = ErddapDatasetManager()
        edm.clear_erddap_cache("existing_a")
        self.assertFalse(test_file.exists())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_remove_two(self):
        test_file1 = TEST_DATA_DIR / "good_example" / "bpd" / "decompressed" / "_a" / "existing_a" / "existing_a.nc"
        test_file2 = TEST_DATA_DIR / "good_example" / "bpd" / "decompressed" / "_b" / "existing_b" / "existing_b.nc"
        test_file3 = TEST_DATA_DIR / "good_example" / "bpd" / "decompressed" / "_c" / "existing_c" / "existing_c.nc"
        self.make_dir_recursive(test_file1.parent)
        self.make_dir_recursive(test_file2.parent)
        self.make_dir_recursive(test_file3.parent)
        with open(test_file1, "w") as h:
            h.write("1")
        with open(test_file2, "w") as h:
            h.write("2")
        with open(test_file3, "w") as h:
            h.write("3")
        self.assertTrue(test_file1.exists())
        self.assertTrue(test_file2.exists())
        self.assertTrue(test_file3.exists())
        edm = ErddapDatasetManager()
        edm.clear_erddap_cache("existing_a,existing_b")
        self.assertFalse(test_file1.exists())
        self.assertFalse(test_file2.exists())
        self.assertTrue(test_file3.exists())

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_remove_all(self):
        test_file1 = TEST_DATA_DIR / "good_example" / "bpd" / "decompressed" / "_a" / "existing_a" / "existing_a.nc"
        test_file2 = TEST_DATA_DIR / "good_example" / "bpd" / "decompressed" / "_b" / "existing_b" / "existing_b.nc"
        test_file3 = TEST_DATA_DIR / "good_example" / "bpd" / "decompressed" / "_c" / "existing_c" / "existing_c.nc"
        self.make_dir_recursive(test_file1.parent)
        self.make_dir_recursive(test_file2.parent)
        self.make_dir_recursive(test_file3.parent)
        with open(test_file1, "w") as h:
            h.write("1")
        with open(test_file2, "w") as h:
            h.write("2")
        with open(test_file3, "w") as h:
            h.write("3")
        self.assertTrue(test_file1.exists())
        self.assertTrue(test_file2.exists())
        self.assertTrue(test_file3.exists())
        edm = ErddapDatasetManager()
        edm.clear_erddap_cache()
        self.assertFalse(test_file1.exists())
        self.assertFalse(test_file2.exists())
        self.assertFalse(test_file3.exists())


class TestCompileDatasets(ErddapUtilTestCase):

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_skip_errors(self):
        datasets_file = TEST_DATA_DIR / "good_example" / "datasets.xml"
        edm = ErddapDatasetManager()
        with self.assertLogs("erddaputil.datasets", "ERROR"):
            edm.compile_datasets(True, False, True)
        self.assertInFile(datasets_file, 'datasetID="existing_a"')
        self.assertInFile(datasets_file, 'datasetID="existing_b"')
        self.assertInFile(datasets_file, 'datasetID="existing_c"')
        self.assertInFile(datasets_file, 'datasetID="dataset_a"')
        self.assertInFile(datasets_file, 'datasetID="dataset_b"')

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_no_skip_errors(self):
        datasets_file = TEST_DATA_DIR / "good_example" / "datasets.xml"
        edm = ErddapDatasetManager()
        with self.assertLogs("erddaputil.datasets", "ERROR"):
            edm.compile_datasets(False, False, True)
        self.assertInFile(datasets_file, 'datasetID="existing_a"')
        self.assertInFile(datasets_file, 'datasetID="existing_b"')
        self.assertInFile(datasets_file, 'datasetID="existing_c"')
        self.assertNotInFile(datasets_file, 'datasetID="dataset_a"')
        self.assertNotInFile(datasets_file, 'datasetID="dataset_b"')

    @injector.test_case()
    @test_with_config(("erddaputil", "erddap", "datasets_xml_template"), TEST_DATA_DIR / "good_example" / "datasets.template.xml")
    @test_with_config(("erddaputil", "erddap", "datasets_d"), TEST_DATA_DIR / "good_example" / "datasets.d")
    @test_with_config(("erddaputil", "erddap", "datasets_xml"), TEST_DATA_DIR / "good_example" / "datasets.xml")
    @test_with_config(("erddaputil", "erddap", "big_parent_directory"), TEST_DATA_DIR / "good_example" / "bpd")
    def test_datasets_content(self):
        datasets_file = TEST_DATA_DIR / "good_example" / "datasets.xml"
        edm = ErddapDatasetManager()
        edm.compile_datasets(True, False, True)
        with open(datasets_file, "r") as h:
            content = h.read()
            self.assertNotIn("é", content)
            self.assertIn("&#233;", content)
            self.assertInXMLTag(content, "ipAddressUnlimited", "12.0.0.0")
            self.assertInXMLTag(content, "ipAddressUnlimited", "10.0.0.1")
            self.assertInXMLTag(content, "requestBlacklist", "11.0.0.0")
            self.assertInXMLTag(content, "requestBlacklist", "10.0.0.2")
            self.assertInXMLTag(content, "subscriptionEmailBlacklist", "blocked@example.com")
            self.assertInXMLTag(content, "subscriptionEmailBlacklist", "me2@example.com")
