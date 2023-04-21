import zirconium as zr
from autoinject import injector
from old.daemons.metrics import ScriptMetrics
import os
import hashlib
import pathlib
import logging
import datetime
import shutil
import xml.etree.ElementTree as ET


class ErddapDatasetManager:

    config: zr.ApplicationConfig = None
    metrics: ScriptMetrics = None

    HARD_FLAG = 2
    BAD_FILES = 1
    SOFT_FLAG = 0

    @injector.construct
    def __init__(self):
        self.bpd = self.config.as_path(("erddaputil", "big_parent_dir"))
        self._errors = self.metrics.counter("erddaputil_dataset_tools_errors")
        self._warnings = self.metrics.counter("erddaputil_dataset_tools_warnings")
        if (not self.bpd) or not self.bpd.exists():
            self._errors.increment()
            raise ValueError(f"BigParentDirectory not configured properly: {self.bpd}")
        self.datasets_file = self.config.as_path(("erddaputil", "datasets_file"))
        if (not self.datasets_file) or not self.datasets_file.parent.exists():
            self._errors.increment()
            raise ValueError(f"Datasets file not configured properly: {self.datasets_file}")
        self.datasets_d = self.config.as_path(("erddaputil", "datasets_d"))
        self.log = logging.getLogger("erddaputil.datasets")
        self.datasets_template = self.config.as_path(("erddaputil", "datasets_template"))
        self._default_compile_with_errors = self.config.as_bool(("erddaputil", "datasets", "compile_with_errors"), default=False)
        self._backup_directory = self.config.as_path(("erddaputil", "datasets", "backup_directory"))
        self._backup_retention_days = self.config.as_int(("erddaputil", "datasets", "backup_retention_days"), default=30)

    def _raise_error(self, component, error_message, raise_err: bool = True):
        self.metrics.counter(f"erddaputil_dataset_tools_{component}_errors").increment()
        if raise_err:
            raise ValueError(error_message)

    def _warning(self, component, message):
        self.metrics.counter(f"erddaputil_dataset-tools_{component}_warnings").increment()
        self.log.warning(message)

    def reload_dataset(self, dataset_id: str, flag: int = 0):
        self.log.out(f"Reloading dataset {dataset_id}, flag {flag}")
        self.metrics.counter("erddaputil_dataset_tools_reload_attempts", labels={"dataset_id": dataset_id}).increment(1)
        subdir = "flag"
        if flag == ErddapDatasetManager.BAD_FILES:
            subdir = "badFilesFlag"
        elif flag == ErddapDatasetManager.HARD_FLAG:
            subdir = "hardFlag"
        flag_file = self.bpd / subdir / dataset_id
        if not flag_file.parent.exists():
            flag_file.parent.mkdir()
        with open(flag_file, "w") as h:
            h.write("1")

    def reload_all_datasets(self, flag: int = 0):
        datasets_xml = ET.parse(self.datasets_file)
        datasets_root = datasets_xml.getroot()
        for ds in datasets_root.iter("dataset"):
            self.reload_dataset(ds.attrib['datasetID'], flag)

    def set_active_flag(self, dataset_id: str, active_flag: bool):
        if not (self.datasets_d and self.datasets_d.exists()):
            self._errors.increment()
            self._raise_error("set_active", f"Dataset config directory misconfigured: {self.datasets_d}")
        self.log.out(f"Setting active flag on {dataset_id} to {active_flag}")
        for file in os.scandir(self.datasets_d):
            if self._try_setting_active_flag(pathlib.Path(file.path), dataset_id, active_flag):
                self.compile_datasets()
                break
        else:
            self._warnings.increment()
            self._warning("set_active", f"Could not find dataset {dataset_id} in {self.datasets_d}")

    def compile_datasets(self, compile_with_errors: bool = None, reload_all_datasets: bool = False):
        self.metrics.counter("erddaputil_dataset_tools_compile_attempts").increment()
        self.log.out("Recompiling datasets")
        self.log.info("Checking parameters...")
        if compile_with_errors is None:
            compile_with_errors = self._default_compile_with_errors
        if not (self.datasets_template and self.datasets_template.exists()):
            self._raise_error("compile", f"Dataset template file misconfigured: {self.datasets_template}")
        if not (self.datasets_d and self.datasets_d.exists()):
            self._raise_error("compile", f"Dataset config directory misconfigured: {self.datasets_d}")
        if self._backup_directory and not self._backup_directory.exists():
            self._raise_error("compile", f"Backup directory misconfigured: {self._backup_directory}")

        self.log.info("Loading datasets.xml from template file...")
        datasets_xml = ET.parse(self.datasets_template)
        datasets_root = datasets_xml.getroot()
        in_template = {ds.attrib["datasetID"]: [ds, self.datasets_template] for ds in datasets_root.iter("dataset")}
        has_errors = False

        self.log.info("Loading extra config from datasets.d...")
        for file in os.scandir(self.datasets_d):
            try:
                config_xml = ET.parse(file.path)
                config_root = config_xml.getroot()
                ds_id = config_root.attrib["datasetID"]
                if ds_id in in_template:
                    self.log.warning(f"Overwriting definition of {ds_id} defined in {in_template[ds_id][1]}")
                    datasets_root.remove(in_template[ds_id][0])
                datasets_root.append(config_root)
                in_template[ds_id] = [config_root, file.path]
            except Exception as ex:
                self._raise_error("compile", str(ex), False)
                has_errors = True

        if has_errors and not compile_with_errors:
            self._raise_error("compile", f"Errors detected during compilation, aborting")

        original_dataset_hashes = {}
        if self.datasets_file.exists():
            original_xml = ET.parse(self.datasets_file)
            original_root = original_xml.getroot()
            for ds in original_root.iter("dataset"):
                original_dataset_hashes[ds.attrib["datasetID"]] = self._hash_xml_element(ds)
            if self._backup_directory:
                self.log.info("Backing up previous datasets.xml file")
                n = 1
                backup_file = self._backup_directory / f"datasets.{datetime.datetime.now().strftime('%Y%m%d%H%M')}.{n}.xml"
                while backup_file.exists():
                    n += 1
                    backup_file = self._backup_directory / f"datasets.{datetime.datetime.now().strftime('%Y%m%d%H%M')}.{n}.xml"
                shutil.copy2(self.datasets_file, backup_file)
                self.metrics.counter("erddaputil_dataset_tools_compile_backups_taken").increment()
            else:
                self.log.warning(f"Backups not configured, skipping backup process")

        self.log.info("Writing new datasets.xml file...")
        with open(self.datasets_file, "wb") as h:
            # ERDDAP requires these settings
            datasets_xml.write(h, encoding="ISO-8859-1", xml_declaration=True, short_empty_elements=False)
        self.metrics.counter("erddaputil_dataset_tools_compile_successes").increment()

        self.log.info("Scanning for updated datasets to reload...")
        for ds in datasets_root.iter("dataset"):
            updated_hash = self._hash_xml_element(ds)
            ds_id = ds.attrib['datasetID']
            if ds_id not in original_dataset_hashes or original_dataset_hashes[ds_id] != updated_hash:
                self.reload_dataset(ds_id, 2)
            elif reload_all_datasets:
                self.reload_dataset(ds_id, 1)

        self.log.info("Cleaning up backups...")
        gate = (datetime.datetime.now() - datetime.timedelta(days=self._backup_retention_days)).timestamp()
        total_count = 0
        for backup in os.scandir(self._backup_directory):
            if backup.stat().st_mtime < gate:
                pathlib.Path(backup.path).unlink()
                total_count += 1
        self.metrics.counter("erddaputil_dataset_tools_compile_backups_cleaned").increment(total_count)

    def _hash_xml_element(self, element) -> str:
        info = []
        elements = [("/dataset", element)]
        while elements:
            path, e = elements.pop()
            txt = e.text.strip('\r\n\t ')
            if txt:
                info.append(f"{path}[text]=={txt}")
            for aname in e.attrib:
                if aname != "name":
                    info.append(f"{path}[{aname}=={e.attrib[aname]}]")
            for se in e:
                if "name" in se.attrib:
                    elements.append((f"{path}/{se.tag}[name={se.attrib['name']}]", se))
                else:
                    elements.append((f"{path}/{se.tag}", se))
        info.sort()
        h = hashlib.sha1()
        for string in info:
            h.update(string.encode("utf-8"))
        return h.hexdigest()

    def _try_setting_active_flag(self, file_path: pathlib.Path, dataset_id: str, active_flag: bool) -> bool:
        try:
            config_xml = ET.parse(file_path)
            config_root = config_xml.getroot()
            if not dataset_id == config_root.attrib["datasetID"]:
                return False
            config_root.attrib["active"] = "true" if active_flag else "false"
            config_xml.write(file_path)
            return True
        except Exception as ex:
            self._raise_error("set_flag", str(ex), False)
            return False
