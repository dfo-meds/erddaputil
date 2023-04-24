"""Manage datasets"""
from autoinject import injector
import zirconium as zr
import logging
import time
import xml.etree.ElementTree as ET
from erddaputil.main.metrics import ScriptMetrics
import os
import datetime
import shutil
import hashlib
import pathlib
import ipaddress
import socket


@injector.injectable_global
class ErddapDatasetManager:
    """Manages datasets on behalf of ERDDAP"""

    config: zr.ApplicationConfig = None
    metrics: ScriptMetrics = None

    HARD_FLAG = 2
    BAD_FLAG = 1
    SOFT_FLAG = 0

    @injector.construct
    def __init__(self):
        super().__init__()
        self.log = logging.getLogger("erddaputil.datasets")
        self.bpd = self.config.as_path(("erddaputil", "erddap", "big_parent_directory"))
        self.datasets_template_file = self.config.as_path(("erddaputil", "erddap", 'datasets_xml_template'), default=None)
        if self.datasets_template_file is None:
            self.datasets_template_file = pathlib.Path(__file__).absolute().parent / "datasets.template.xml"
        self.datasets_directory = self.config.as_path(("erddaputil", "erddap", "datasets_d"), default=None)
        self.datasets_file = self.config.as_path(("erddaputil", "erddap", "datasets_xml"), default=None)
        self.backup_directory = self.config.as_path(("erddaputil", "backups"), default=None)
        self._max_pending_reloads = self.config.as_int(("erddaputil", "dataset_manager", "max_pending"), default=2)
        self._max_reload_delay = self.config.as_int(("erddaputil", "dataset_manager", "max_delay_seconds"), default=10)
        self._max_recompilation_delay = self.config.as_int(("erddaputil", "dataset_manager", "max_recompile_delay"), default=15)
        self._skip_errored_datasets = self.config.as_bool(("erddaputil", "dataset_manager", "skip_misconfigured_datasets"), default=True)
        self._email_block_list = self.config.as_path(("erddaputil", "erddap", "subscription_block_list"), default=None)
        self._backup_retention_days = self.config.as_int(("erddaputil", "dataset_manager", "backup_retention_days"), default=30)
        self._ip_block_list = self.config.as_path(("erddaputil", "erddap", "ip_block_list"), default=None)
        self._unlimited_allow_list = self.config.as_path(("erddaputil", "erddap", "unlimited_allow_list"), default=None)
        self.hostname = self.config.as_str(("erddaputil", "ampq", "hostname"), default=None)
        if self.hostname is None:
            self.hostname = socket.gethostname()
        self.cluster_name = self.config.as_str(("erddaputil", "ampq", "cluster_name"), default="default")
        if self.bpd:
            if self._email_block_list is None:
                self._email_block_list = self.bpd / ".email_block_list.txt"
            if self._ip_block_list is None:
                self._ip_block_list = self.bpd / ".ip_block_list.txt"
            if self._unlimited_allow_list is None:
                self._unlimited_allow_list = self.bpd / ".unlimited_allow_list.txt"
        self._datasets_to_reload = {}
        self._compilation_requested = None

    def can_recompile(self):
        if not (self.datasets_template_file and self.datasets_template_file.exists()):
            return False
        if not (self.datasets_directory and self.datasets_directory.exists()):
            return False
        if not (self.datasets_file and self.datasets_file.parent.exists()):
            return False
        return True

    def can_reload(self):
        if not (self.bpd and self.bpd.exists()):
            return False
        return True

    def reload_dataset(self, dataset_id: str, flag: int = 0, flush: bool = False):
        """Queue a dataset for reloading."""
        if not self.can_reload():
            raise ValueError("Configuration not sufficient to reload")
        self.log.info(f"Reload[{flag}] of {dataset_id} requested")
        if dataset_id not in self._datasets_to_reload and len(self._datasets_to_reload) >= self._max_pending_reloads:
            self._flush_datasets(True)
        self._queue_dataset_reload(dataset_id, flag)
        self._flush_datasets(flush)

    def _queue_dataset_reload(self, dataset_id: str, flag: int):
        self.metrics.counter("erddaputil_dataset_reloads", {
            "stage": "queued",
            "flag": str(flag),
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).increment()
        if dataset_id not in self._datasets_to_reload:
            self._datasets_to_reload[dataset_id] = [flag, time.monotonic()]
        else:
            if flag > self._datasets_to_reload[dataset_id][0]:
                self._datasets_to_reload[dataset_id][0] = flag
            self._datasets_to_reload[dataset_id][1] = time.monotonic()

    def _reload_dataset(self, dataset_id, flag):
        """Actually reload a dataset"""
        self.log.info(f"Reload[{flag}] of {dataset_id} proceeding")
        subdir = "flag"
        if flag == ErddapDatasetManager.BAD_FLAG:
            subdir = "badFilesFlag"
        elif flag == ErddapDatasetManager.HARD_FLAG:
            subdir = "hardFlag"
        flag_file = self.bpd / subdir / dataset_id
        if not flag_file.parent.exists():
            flag_file.parent.mkdir()
        with open(flag_file, "w") as h:
            h.write("1")
        self.metrics.counter("erddaputil_dataset_reloads", {
            "stage": "complete",
            "flag": str(flag),
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).increment()

    def set_active_flag(self, dataset_id: str, active_flag: bool, flush: bool = False):
        if not self.can_recompile():
            raise ValueError("Configuration not sufficient to recompile")
        self.log.info(f"Setting active flag on {dataset_id} to {active_flag}")
        self.metrics.counter("erddaputil_dataset_activations", {
            "mode": str(active_flag),
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).increment()

        for file in os.scandir(self.datasets_directory):
            if self._try_setting_active_flag(pathlib.Path(file.path), dataset_id, active_flag):
                self._queue_dataset_reload(dataset_id, 0)
                self.compile_datasets(False, False, flush)
                break
        else:
            raise ValueError(f"Could not find dataset {dataset_id}")

    def block_email(self, email_address: str, flush: bool = False):
        if not (self._email_block_list and self._email_block_list.parent.exists()):
            raise ValueError("Email block list not configured")
        if not self.can_recompile():
            raise ValueError("Configuration not sufficient to recompile")
        if email_address.count("@") != 1:
            raise ValueError("Invalid email address")
        if email_address[0] == "@":
            raise ValueError("Invalid email address")
        if "." not in email_address[email_address.find("@"):]:
            raise ValueError("Invalid email address")
        if "," in email_address:
            raise ValueError("ERDDAP does not allow commas in email addresses")
        self.metrics.counter("erddaputil_emails_blocked", {
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).increment()
        self._append_entry_to_file(self._email_block_list, email_address)
        self.compile_datasets(False, False, flush)

    def _validate_ip_address(self, ip_address: str):
        if '*' in ip_address:
            # ERDDAP allows the usage of '*' as a placeholder for the fourth (or third and fourth)
            # element of an IPv4 address
            # We check this here since this is a non-standard way of specifying a range of IP addresses
            if '.' not in ip_address:
                raise ValueError(f"Invalid IP address: {ip_address}")
            pieces = ip_address.split('.')
            if len(pieces) != 4:
                raise ValueError(f"Invalid IP address: {ip_address}")
            if not (pieces[0].isdigit() and pieces[1].isdigit()):
                raise ValueError(f"Invalid IP address: {ip_address}")
            if pieces[2] == '*' and not pieces[3] == '*':
                raise ValueError(f"Invalid IP address: {ip_address}")
            if pieces[2] != '*' and not pieces[2].isdigit():
                raise ValueError(f"Invalid IP address: {ip_address}")
            if pieces[3] != '*' and not pieces[3].isdigit():
                raise ValueError(f"Invalid IP address: {ip_address}")
        else:
            # Test the IP address to make sure it is a valid IP address
            # raises ValueError if the address is invalid
            ipaddress.ip_address(ip_address)

    def block_ip(self, ip_address: str, flush: bool = False):
        if not (self._ip_block_list and self._ip_block_list.parent.exists()):
            raise ValueError("IP block list not configured")
        if not self.can_recompile():
            raise ValueError("Configuration not sufficient to recompile")
        self._validate_ip_address(ip_address)
        self.metrics.counter("erddaputil_ips_blocked", {
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).increment()
        self._append_entry_to_file(self._ip_block_list, ip_address)
        self.compile_datasets(False, False, flush)

    def allow_unlimited(self, ip_address: str, flush: bool = False):
        if not (self._unlimited_allow_list and self._unlimited_allow_list.parent.exists()):
            raise ValueError("Unlimited allow list not configured")
        if not self.can_recompile():
            raise ValueError("Configuration not sufficient to recompile")
        self._validate_ip_address(ip_address)
        self.metrics.counter("erddaputil_emails_blocked", {
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).increment()
        self._append_entry_to_file(self._unlimited_allow_list, ip_address)
        self.compile_datasets(False, False, flush)

    def _append_entry_to_file(self, file, new_entry):
        file_list = set()
        if file.exists():
            with open(file, "r") as h:
                file_list = set(x.strip("\r\n\t ").lower() for x in h.readlines())
        file_list.add(new_entry.lower())
        with open(file, "w") as h:
            for entry in file_list:
                h.write(entry + "\n")

    def reload_all_datasets(self, flag: int = 0, flush: bool = False):
        if not (self.datasets_file and self.datasets_file.parent.exists()):
            raise ValueError("Datasets file is not set")
        if not self.can_reload():
            raise ValueError("Configuration not sufficient to reload")
        config_xml = ET.parse(self.datasets_file)
        config_root = config_xml.getroot()
        for ds in config_root.iter("dataset"):
            self._queue_dataset_reload(ds.attrib["datasetID"], flag)
        self._flush_datasets(flush)

    def compile_datasets(self, skip_errored_datasets: bool = None, reload_all_datasets: bool = False, immediate: bool = False):
        self.log.info(f"Recompilation of datasets requested")
        if not self.can_recompile():
            raise ValueError("Configuration not sufficient to recompile")
        self._queue_recompilation(skip_errored_datasets, reload_all_datasets)
        self._flush_recompilation(immediate)

    def _queue_recompilation(self, skip_errored_datasets: bool, reload_all_datasets: bool):
        self.metrics.counter("erddaputil_dataset_recompilation", {
            "stage": "queued",
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).increment()
        if skip_errored_datasets is None:
            skip_errored_datasets = self._skip_errored_datasets
        if self._compilation_requested is None:
            self._compilation_requested = [skip_errored_datasets, reload_all_datasets, time.monotonic()]
        else:
            if skip_errored_datasets is False and self._compilation_requested[0]:
                self._compilation_requested[0] = False
            if reload_all_datasets is True and not self._compilation_requested[1]:
                self._compilation_requested[1] = True
            self._compilation_requested[2] = time.monotonic()

    def _expand_ip_addresses(self, ip_list, allow_ranges: bool = False):
        for ip in ip_list:
            if "/" in ip:
                # Handle a subnet range, which ERDDAP won't do
                if "." in ip:
                    for subnet_ip in ipaddress.IPv4Network(ip):
                        yield str(subnet_ip)
                elif ":" in ip:
                    for subnet_ip in ipaddress.IPv6Network(ip):
                        yield str(subnet_ip)
                else:
                    self.log.warning(f"Invalid subnet identified: {ip}")
                    continue
            elif "*" in ip and not allow_ranges:
                # Expand ERDDAP's asterisk ranges for unlimitedIP if it was used (probably not a good practice)
                pieces = ip.split(".")
                if pieces[0] == "*" or pieces[1] == "*" or (pieces[3] == "*" and not pieces[2] == "*"):
                    self.log.warning(f"Bad format for ERDDAP range: {ip}")
                    continue
                elif pieces[2] != "*" and pieces[3] == "*":
                    for i in range(0, 256):
                        yield f"{pieces[0]}.{pieces[1]}.{pieces[2]}.{i}"
                elif pieces[2] == "*" and pieces[3] == "*":
                    for i in range(0, 256):
                        for j in range(0, 256):
                            yield f"{pieces[0]}.{pieces[1]}.{i}.{j}"
            else:
                yield ip

    def _compile_block_allow_lists(self, datasets_root):
        ip_blocks = set()
        ip_element = None
        email_blocks = set()
        email_element = None
        unlimited_allow = set()
        unlimited_element = None

        for a1 in datasets_root.iter("ipAddressUnlimited"):
            unlimited_allow.update(x.strip("\r\n\t ").lower() for x in a1.text.split(","))
            unlimited_element = a1
        for a2 in datasets_root.iter("subscriptionEmailBlacklist"):
            email_blocks.update(x.strip("\r\n\t ").lower() for x in a2.text.split(","))
            email_element = a2
        for a3 in datasets_root.iter("requestBlacklist"):
            ip_blocks.update(x.strip("\r\n\t ").lower() for x in a3.text.split(","))
            ip_element = a3
        if self._ip_block_list.exists():
            with open(self._ip_block_list, "r") as h:
                ip_blocks.update(x.strip("\r\n\t ").lower() for x in h.readlines())
        if self._email_block_list.exists():
            with open(self._email_block_list, "r") as h:
                email_blocks.update(x.strip("\r\n\t ").lower() for x in h.readlines())
        if self._unlimited_allow_list.exists():
            with open(self._unlimited_allow_list, "r") as h:
                unlimited_allow.update(x.strip("\r\n\t ").lower() for x in h.readlines())

        if unlimited_element is None:
            unlimited_element = ET.Element("ipAddressUnlimited")
            datasets_root.insert(0, unlimited_element)
        if email_element is None:
            email_element = ET.Element("subscriptionEmailBlacklist")
            datasets_root.insert(0, email_element)
        if ip_element is None:
            ip_element = ET.Element("requestBlacklist")
            datasets_root.insert(0, ip_element)

        if unlimited_allow:
            unlimited_element.text = ",".join(self._expand_ip_addresses(unlimited_allow, False))
        if ip_blocks:
            ip_element.text = ",".join(self._expand_ip_addresses(ip_blocks, True))
        if email_blocks:
            email_element.text = ",".join(email_blocks)


    def _do_recompilation(self, skip_errored_datasets: bool, reload_all_datasets: bool):
        datasets_xml = ET.parse(self.datasets_template_file)
        datasets_root = datasets_xml.getroot()
        in_template = {ds.attrib["datasetID"]: [ds, self.datasets_template] for ds in datasets_root.iter("dataset")}
        has_errors = False

        for file in os.scandir(self.datasets_directory):
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
                self.log.exception(ex)
                has_errors = True

        if has_errors and not skip_errored_datasets:
            self.metrics.counter("erddaputil_dataset_recompilation", {
                "stage": "failed",
                "cluster": self.cluster_name,
                "host": self.hostname,
            }).increment()
            raise ValueError("Errors detected during compilation, aborting")

        self._compile_block_allow_lists(datasets_root)

        original_dataset_hashes = {}
        if self.datasets_file.exists():
            original_xml = ET.parse(self.datasets_file)
            original_root = original_xml.getroot()
            for ds in original_root.iter("dataset"):
                original_dataset_hashes[ds.attrib["datasetID"]] = self._hash_xml_element(ds)
            if self.backup_directory and self.backup_directory.exists():
                n = 1
                backup_file = self.backup_directory / f"datasets.{datetime.datetime.now().strftime('%Y%m%d%H%M')}.{n}.xml"
                while backup_file.exists():
                    n += 1
                    backup_file = self.backup_directory / f"datasets.{datetime.datetime.now().strftime('%Y%m%d%H%M')}.{n}.xml"
                shutil.copy2(self.datasets_file, backup_file)
            else:
                self.log.warning(f"Backups not configured, skipping backup process")

        with open(self.datasets_file, "wb") as h:
            # ERDDAP requires these settings
            datasets_xml.write(h, encoding="ISO-8859-1", xml_declaration=True, short_empty_elements=False)

        reload_id = None
        for ds in datasets_root.iter("dataset"):
            updated_hash = self._hash_xml_element(ds)
            ds_id = ds.attrib['datasetID']
            reload_id = ds_id
            if ds_id not in original_dataset_hashes or original_dataset_hashes[ds_id] != updated_hash:
                self._queue_dataset_reload(ds_id, 2)
            elif reload_all_datasets:
                self._queue_dataset_reload(ds_id, 1)

        if not self._datasets_to_reload:
            self._queue_dataset_reload(reload_id, 0)

        gate = (datetime.datetime.now() - datetime.timedelta(days=self._backup_retention_days)).timestamp()
        total_count = 0
        if self.backup_directory and self.backup_directory.exists():
            for backup in os.scandir(self.backup_directory):
                if backup.stat().st_mtime < gate:
                    pathlib.Path(backup.path).unlink()
                    total_count += 1

        self._flush_datasets(True)
        self.metrics.counter("erddaputil_dataset_recompilation", {
            "stage": "completed",
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).increment()

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
            print(config_root)
            if not dataset_id == config_root.attrib["datasetID"]:
                return False
            config_root.attrib["active"] = "true" if active_flag else "false"
            config_xml.write(file_path)
            return True
        except Exception as ex:
            self.log.exception(ex)
            return False

    def flush(self, force: bool = False):
        """If force is set, all changes are definitely pushed, otherwise the gates are respected"""
        self._flush_recompilation(force)
        self._flush_datasets(force)

    def _flush_datasets(self, force: bool = False):
        """For datasets"""
        for dataset_id in list(self._datasets_to_reload.keys()):
            if force or (time.monotonic() - self._datasets_to_reload[dataset_id][1]) > self._max_reload_delay:
                self._reload_dataset(dataset_id, self._datasets_to_reload[dataset_id][0])
                del self._datasets_to_reload[dataset_id]

    def _flush_recompilation(self, force: bool = False):
        if self._compilation_requested is None:
            return
        if force or (time.monotonic() - self._compilation_requested[2] > self._max_recompilation_delay):
            self._do_recompilation(self._compilation_requested[0], self._compilation_requested[1])
            self._compilation_requested = None
