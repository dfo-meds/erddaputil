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
import requests
import typing as t


STR_OR_ITER = t.Union[str, t.Iterable]


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
        self.erddap_url = self.config.as_str(("erddaputil", "erddap", "base_url"), default=None)

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

    def check_can_reload(self):
        if not self.bpd:
            raise ValueError("ERDDAP bigParentDirectory is not configured")
        if not self.bpd.exists():
            raise ValueError(f"ERDDAP bigParentDirectory does not exist {self.bpd}")
        return True

    def flush_logs(self):
        if not self.erddap_url:
            raise ValueError("ERDDAP URL must be configured")
        base = self.erddap_url
        if base.endswith("/"):
            base += "status.html"
        else:
            base += "/status.html"
        resp = requests.get(base)
        resp.raise_for_status()

    def set_active_flag(self, dataset_id: STR_OR_ITER, active_flag: bool, flush: bool = False):
        if not self.can_recompile():
            raise ValueError("Configuration not sufficient to recompile")
        self.log.info(f"Setting active flag on {dataset_id} to {active_flag}")
        self.metrics.counter("erddaputil_dataset_activations", {
            "mode": str(active_flag),
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).inc()
        successes = []
        failures = []
        for ds_id in self._handle_list_input(dataset_id):
            for file in os.scandir(self.datasets_directory):
                if self._try_setting_active_flag(pathlib.Path(file.path), dataset_id, active_flag):
                    self._queue_dataset_reload(dataset_id, 0)
                    successes.append(ds_id)
                    break
            else:
                failures.append(ds_id)
        if successes:
            self.compile_datasets(False, False, flush)
        if failures:
            raise ValueError(f"Failed to find dataset(s): {','.join(failures)}")

    def update_email_block_list(self, email_address: STR_OR_ITER, block: bool, flush: bool = False):
        if not (self._email_block_list and self._email_block_list.parent.exists()):
            raise ValueError("Email block list not configured")
        if not self.can_recompile():
            raise ValueError("Configuration not sufficient to recompile")
        emails = self._handle_list_input(email_address)
        for email_address in emails:
            self._validate_email(email_address)
        if self._update_file_entry(self._email_block_list, block, emails):
            self.compile_datasets(False, False, flush)

    def update_ip_block_list(self, ip_address: STR_OR_ITER, block: bool = True, flush: bool = False):
        if not (self._ip_block_list and self._ip_block_list.parent.exists()):
            raise ValueError("IP block list not configured")
        if not self.can_recompile():
            raise ValueError("Configuration not sufficient to recompile")
        ip_addresses = self._handle_list_input(ip_address)
        for ip_address in ip_addresses:
            self._validate_ip_address(ip_address)
        if self._update_file_entry(self._ip_block_list, block, ip_addresses):
            self.compile_datasets(False, False, flush)

    def update_allow_unlimited_list(self, ip_address: STR_OR_ITER, allow: bool = True, flush: bool = False):
        if not (self._unlimited_allow_list and self._unlimited_allow_list.parent.exists()):
            raise ValueError("Unlimited allow list not configured")
        if not self.can_recompile():
            raise ValueError("Configuration not sufficient to recompile")
        ip_addresses = self._handle_list_input(ip_address)
        for ip_address in ip_addresses:
            self._validate_ip_address(ip_address)
        if self._update_file_entry(self._unlimited_allow_list, allow, ip_addresses):
            self.compile_datasets(False, False, flush)

    def _update_file_entry(self, file: pathlib.Path, add_to_list: bool, new_entries: t.Iterable):
        if add_to_list:
            return self._add_to_file_entry(file, new_entries)
        else:
            return self._remove_from_file_entry(file, new_entries)

    def _remove_from_file_entry(self, file: pathlib.Path, remove_entries: t.Iterable):
        if not file.exists():
            return False
        file_list = set()
        with open(file, "r") as h:
            file_list = set(x.strip("\r\n\t ").lower() for x in h.readlines())
        found = False
        for item in remove_entries:
            if item in file_list:
                file_list.remove(item)
                found = True
        if not found:
            return False
        with open(file, "w") as h:
            for entry in file_list:
                h.write(entry + "\n")
        return True

    def _add_to_file_entry(self, file: pathlib.Path, new_entries: t.Iterable):
        file_list = set()
        if file.exists():
            with open(file, "r") as h:
                file_list = set(x.strip("\r\n\t ").lower() for x in h.readlines())
        found = False
        for new_entry in new_entries:
            new_entry = new_entry.lower()
            if new_entry in file_list:
                continue
            found = True
            file_list.add(new_entry)
        if not found:
            return False
        with open(file, "w") as h:
            for entry in file_list:
                h.write(entry + "\n")
        return True

    def list_datasets(self):
        if not self.datasets_file:
            raise ValueError("Datasets.xml not configured")
        if not self.datasets_file.exists():
            raise ValueError(f"No datasets.xml file found at {self.datasets_file}")
        original_xml = ET.parse(self.datasets_file)
        original_root = original_xml.getroot()
        return "Datasets:\n" + "\n".join(
            f"{ds.attrib['datasetID']} ({ds.attrib['active'] if 'active' in ds.attrib else 'true'})"
            for ds in original_root.iter("dataset")
        )

    def clear_erddap_cache(self, dataset_id: t.Optional[STR_OR_ITER] = None):
        if not self.check_can_reload():
            raise ValueError("Unable to find big parent directory")
        initial_work = []
        # Caching not working well right now
        if dataset_id:
            for ds_id in self._handle_list_input(dataset_id):
                initial_work.extend([
                    # self.bpd / "cache" / ds_id[-2:] / ds_id,
                    self.bpd / "decompressed" / ds_id[-2:] / ds_id
                ])
        else:
            initial_work.extend([
                #self.bpd / "cache",
                self.bpd / "decompressed"
            ])
        to_remove = []
        for base_dir in initial_work:
            to_remove.extend(file for file in os.scandir(base_dir) if not file.is_symlink())
        while to_remove:
            next_rem = to_remove.pop()
            if next_rem.is_symlink():
                continue
            elif next_rem.is_dir():
                to_remove.extend(file for file in os.scandir(next_rem.path) if not file.is_symlink())
            else:
                os.unlink(next_rem.path)

    def reload_all_datasets(self, flag: int = 0, flush: bool = False):
        if not (self.datasets_file and self.datasets_file.parent.exists()):
            raise ValueError("Datasets file is not set")
        if not self.check_can_reload():
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

    def flush(self, force: bool = False):
        """If force is set, all changes are definitely pushed, otherwise the gates are respected"""
        self._flush_recompilation(force)
        self._flush_datasets(force)

    def reload_dataset(self, dataset_ids: STR_OR_ITER, flag: int = 0, flush: bool = False):
        """Queue a dataset for reloading."""
        self.check_can_reload()
        if flag not in (0, 1, 2):
            raise ValueError(f"Invalid flag value: {flag}")
        self.log.info(f"Reload[{flag}] of {dataset_ids} requested")
        for ds_id in self._handle_list_input(dataset_ids):
            self._queue_dataset_reload(ds_id, flag)
        self._flush_datasets(flush)

    def _queue_recompilation(self, skip_errored_datasets: bool, reload_all_datasets: bool):
        self.metrics.counter("erddaputil_dataset_recompilation", {
            "stage": "queued",
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).inc()
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
            if not ip:
                continue
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
            if a1.text:
                unlimited_allow.update(x.strip("\r\n\t ").lower() for x in a1.text.split(","))
            unlimited_element = a1
        for a2 in datasets_root.iter("subscriptionEmailBlacklist"):
            if a2.text:
                email_blocks.update(x.strip("\r\n\t ").lower() for x in a2.text.split(","))
            email_element = a2
        for a3 in datasets_root.iter("requestBlacklist"):
            if a3.text:
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
            email_element.text = ",".join(e for e in email_blocks if e)

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
            }).inc()
            raise ValueError("Errors detected during compilation, aborting")

        self._compile_block_allow_lists(datasets_root)

        reload_id = None
        original_dataset_hashes = {}
        if self.datasets_file.exists():
            try:
                original_xml = ET.parse(self.datasets_file)
                original_root = original_xml.getroot()
                for ds in original_root.iter("dataset"):
                    reload_id = ds.attrib["datasetID"]
                    original_dataset_hashes[ds.attrib["datasetID"]] = self._hash_xml_element(ds)
            except ET.ParseError:
                pass
            if self.backup_directory and self.backup_directory.exists():
                n = 1
                backup_file = self.backup_directory / f"datasets.{datetime.datetime.now().strftime('%Y%m%d%H%M')}.{n}.xml"
                while backup_file.exists():
                    n += 1
                    backup_file = self.backup_directory / f"datasets.{datetime.datetime.now().strftime('%Y%m%d%H%M')}.{n}.xml"
                shutil.copy2(self.datasets_file, backup_file)
            else:
                self.log.warning(f"Backups not configured, skipping backup process")

        with open(self.datasets_file, "w") as h:
            # ERDDAP requires these settings
            indent(datasets_xml.getroot())
            out_str = ET.tostring(datasets_xml.getroot(), encoding="unicode", short_empty_elements=False)
            real_out_str = ""
            for c in out_str:
                if c == "\n" and real_out_str and real_out_str[-1] == "\n":
                    continue
                o = ord(c)
                if o < 128:
                    real_out_str += c
                else:
                    real_out_str += f"&#{o};"
            h.write("<?xml version='1.0' encoding='ISO-8859-1'?>\n")
            level = 0
            for line in real_out_str.split("\n"):
                line = line.strip()
                if line.startswith("</"):
                    level -= 1
                if line.startswith("<"):
                    h.write("  " * level)
                h.write(line)
                h.write("\n")
                if line.startswith("<") and "</" not in line and "/>" not in line:
                    level += 1
                elif "</" in line and not line.startswith("<"):
                    level -= 1

        for ds in datasets_root.iter("dataset"):
            updated_hash = self._hash_xml_element(ds)
            ds_id = ds.attrib['datasetID']
            if ds_id not in original_dataset_hashes or original_dataset_hashes[ds_id] != updated_hash:
                self._queue_dataset_reload(ds_id, 2)
            elif reload_all_datasets:
                self._queue_dataset_reload(ds_id, 1)

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
        }).inc()

    def _flush_recompilation(self, force: bool = False):
        if self._compilation_requested is None:
            return
        if force or (time.monotonic() - self._compilation_requested[2] > self._max_recompilation_delay):
            try:
                self._do_recompilation(self._compilation_requested[0], self._compilation_requested[1])
            except Exception as ex:
                self.log.exception(ex)
            finally:
                self._compilation_requested = None

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

    def _handle_list_input(self, original_input: t.Union[str, t.Iterable[str]]) -> set[str]:
        if isinstance(original_input, str):
            if "," in original_input:
                return set(x for x in original_input.split(","))
            else:
                return {original_input}
        else:
            return set(x for x in original_input)

    def _queue_dataset_reload(self, dataset_id: str, flag: int):
        self.metrics.counter("erddaputil_dataset_reloads_staged", {
            "flag": str(flag),
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).inc()
        if dataset_id not in self._datasets_to_reload:
            self._datasets_to_reload[dataset_id] = [flag, time.monotonic()]
        else:
            if flag > self._datasets_to_reload[dataset_id][0]:
                self._datasets_to_reload[dataset_id][0] = flag
            self._datasets_to_reload[dataset_id][1] = time.monotonic()

    def _flush_datasets(self, force: bool = False):
        """For datasets"""
        ds_ids = [(k, self._datasets_to_reload[k][1]) for k in self._datasets_to_reload]
        ds_ids.sort(key=lambda x: x[1])
        auto_reload = (len(ds_ids) - self._max_pending_reloads) if self._max_pending_reloads > 0 else -1
        for dataset_id in ds_ids:
            if force or auto_reload > 0 or (time.monotonic() - self._datasets_to_reload[dataset_id][1]) > self._max_reload_delay:
                auto_reload -= 1
                try:
                    self._reload_dataset(dataset_id, self._datasets_to_reload[dataset_id][0])
                except Exception as ex:
                    self.log.exception(ex)
                finally:
                    del self._datasets_to_reload[dataset_id]

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
        self.metrics.counter("erddaputil_dataset_reloads_completed", {
            "flag": str(flag),
            "cluster": self.cluster_name,
            "host": self.hostname,
        }).inc()

    def _validate_email(self, email_address: str):
        if email_address.count("@") != 1:
            raise ValueError("Invalid email address")
        if email_address[0] == "@":
            raise ValueError("Invalid email address")
        if "." not in email_address[email_address.find("@"):]:
            raise ValueError("Invalid email address")
        if "," in email_address:
            raise ValueError("ERDDAP does not allow commas in email addresses")

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


def indent(elem, level=0):
    elem.tail = "\n"
    for se in elem:
        indent(se, level + 1)
    return elem
