"""Tools for managing ERDDAP"""
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
    """Manage ERDDAP configuration"""

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
        self._email_block_list_file = self.config.as_path(("erddaputil", "erddap", "subscription_block_list"), default=None)
        self._backup_retention_days = self.config.as_int(("erddaputil", "dataset_manager", "backup_retention_days"), default=30)
        self._ip_block_list_file = self.config.as_path(("erddaputil", "erddap", "ip_block_list"), default=None)
        self._unlimited_allow_list_file = self.config.as_path(("erddaputil", "erddap", "unlimited_allow_list"), default=None)
        self.hostname = self.config.as_str(("erddaputil", "ampq", "hostname"), default=None)
        if self.hostname is None:
            self.hostname = socket.gethostname()
        self.cluster_name = self.config.as_str(("erddaputil", "ampq", "cluster_name"), default="default")
        if self.bpd:
            if self._email_block_list_file is None:
                self._email_block_list_file = self.bpd / ".email_block_list.txt"
            if self._ip_block_list_file is None:
                self._ip_block_list_file = self.bpd / ".ip_block_list.txt"
            if self._unlimited_allow_list_file is None:
                self._unlimited_allow_list_file = self.bpd / ".unlimited_allow_list.txt"
        self._email_block_list = AllowBlockListFile(self._email_block_list_file)
        self._ip_block_list = AllowBlockListFile(self._ip_block_list_file)
        self._unlimited_allow_list = AllowBlockListFile(self._unlimited_allow_list_file)
        self._datasets_to_reload = {}
        self._compilation_requested = None

    def check_can_compile(self):
        """Check if the configuration allows the datasets.xml file to be compiled from datasets.d"""
        if not (self.datasets_template_file and self.datasets_template_file.exists()):
            raise ValueError("Datasets template file is missing or not configured")
        if not (self.datasets_directory and self.datasets_directory.exists()):
            raise ValueError("Datasets.d directory is missing or not configured")
        if not (self.datasets_file and self.datasets_file.parent.exists()):
            raise ValueError("The datasets.xml directory is missing or not configured properly")
        return self.check_can_reload()

    def check_datasets_exist(self):
        """Check if the datasets.xml file exists"""
        if not self.datasets_file:
            raise ValueError("Datasets.xml not configured")
        if not self.datasets_file.exists():
            raise ValueError(f"No datasets.xml file found at {self.datasets_file}")
        return True

    def check_can_reload(self):
        """Check if the configuration allows datasets to be reloaded."""
        if not self.bpd:
            raise ValueError("ERDDAP bigParentDirectory is not configured")
        if not self.bpd.exists():
            raise ValueError(f"ERDDAP bigParentDirectory does not exist {self.bpd}")
        return True

    def check_can_http(self):
        """Check if the configuration allows for HTTP communication to ERDDAP"""
        if not self.erddap_url:
            raise ValueError("ERDDAP URL must be configured")
        return True

    def get_status_page(self):
        """Retrieve the status.html page contents."""
        self.check_can_http()
        self.log.info(f"Retrieving ERDDAP's status.html page")
        base = self.erddap_url
        if base.endswith("/"):
            base += "status.html"
        else:
            base += "/status.html"
        resp = requests.get(base)
        resp.raise_for_status()
        return resp.text

    def flush_logs(self):
        """Ensure ERDDAP's logs have been flushed to disk."""
        self.get_status_page()

    def set_active_flag(self, dataset_id: STR_OR_ITER, active_flag: bool, flush: bool = False):
        """Set an ERDDAP dataset's active flag to true or false"""
        self.check_can_compile()
        self.log.info(f"Setting active flag on {dataset_id} to {active_flag}")
        successes = []
        failures = []
        noop = []
        for ds_id in AllowBlockListFile.input_to_set(dataset_id):
            with os.scandir(self.datasets_directory) as files:
                for file in files:
                    res = self._try_setting_active_flag(pathlib.Path(file.path), dataset_id, active_flag)
                    if res == 1:
                        self._queue_dataset_reload(dataset_id, 0)
                        successes.append(ds_id)
                        break
                    elif res == 2:
                        noop.append(ds_id)
                        break
                else:
                    failures.append(ds_id)
        if successes:
            self._queue_recompilation(immediate=flush)
        if failures:
            raise ValueError(f"Failed to find dataset(s): {','.join(failures)}")

    def update_email_block_list(self, email_address: STR_OR_ITER, block: bool, flush: bool = False):
        """Block or unblock an email address from subscriptions"""
        self.check_can_compile()
        self.log.info(f"Updating email block list")
        if self._email_block_list.append_or_remove(email_address, block, 'email'):
            self.compile_datasets(False, False, flush)

    def update_ip_block_list(self, ip_address: STR_OR_ITER, block: bool = True, flush: bool = False):
        """Block or unblock an IP address"""
        self.check_can_compile()
        self.log.info("Updating IP block list")
        if self._ip_block_list.append_or_remove(ip_address, block, 'ip'):
            self.compile_datasets(False, False, flush)

    def update_allow_unlimited_list(self, ip_address: STR_OR_ITER, allow: bool = True, flush: bool = False):
        """Add or remove an IP address from the unlimited allow list"""
        self.check_can_compile()
        self.log.info("Updating unlimited allow list")
        if self._unlimited_allow_list.append_or_remove(ip_address, allow, 'ip'):
            self.compile_datasets(False, False, flush)

    def list_datasets(self):
        """List the existing datasets"""
        self.check_datasets_exist()
        original_xml = ET.parse(self.datasets_file)
        original_root = original_xml.getroot()
        return "Datasets:\n" + "\n".join(
            f"{ds.attrib['datasetID']} ({ds.attrib['active'] if 'active' in ds.attrib else 'true'})"
            for ds in original_root.iter("dataset")
        )

    def clear_erddap_cache(self, dataset_id: t.Optional[STR_OR_ITER] = None):
        """Remove the cache and decompressed folders (optionally for a given dataset)"""
        self.check_can_reload()
        initial_work = []
        # Caching not working well right now
        if dataset_id:
            for ds_id in AllowBlockListFile.input_to_set(dataset_id):
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
                self.log.out(f"Removing {next_rem.path}")
                os.unlink(next_rem.path)

    def reload_all_datasets(self, flag: int = 0, flush: bool = False):
        """Reload all datasets"""
        self.check_can_reload()
        self.check_datasets_exist()
        self.log.info(f"Reload[{flag}] of all datasets requested")
        config_xml = ET.parse(self.datasets_file)
        config_root = config_xml.getroot()
        for ds in config_root.iter("dataset"):
            # Skip inactive datasets
            if "active" in ds.attrib and ds.attrib["active"] == "false":
                continue
            self._queue_dataset_reload(ds.attrib["datasetID"], flag)
        self._flush_datasets(flush)

    def compile_datasets(self, skip_errored_datasets: bool = None, reload_all_datasets: bool = False, immediate: bool = False):
        """Queue a recompile of the datasets"""
        self.check_can_compile()
        self.log.info(f"Recompilation of datasets requested")
        self._queue_recompilation(skip_errored_datasets, reload_all_datasets, immediate)

    def reload_dataset(self, dataset_ids: STR_OR_ITER, flag: int = 0, flush: bool = False):
        """Queue a dataset for reloading."""
        self.check_can_reload()
        if flag not in (0, 1, 2):
            raise ValueError(f"Invalid flag value: {flag}")
        self.log.info(f"Reload[{flag}] of {dataset_ids} requested")
        for ds_id in AllowBlockListFile.input_to_set(dataset_ids):
            ds_id = ds_id.strip()
            if not ds_id:
                continue
            self._queue_dataset_reload(ds_id, flag)
        self._flush_datasets(flush)

    def flush(self, force: bool = False):
        """Ensure all changes are flushed to disk"""
        self._flush_recompilation(force)
        self._flush_datasets(force)

    def _try_setting_active_flag(self, file_path: pathlib.Path, dataset_id: str, active_flag: bool) -> int:
        try:
            config_xml = ET.parse(file_path)
            config_root = config_xml.getroot()
            if not dataset_id == config_root.attrib["datasetID"]:
                return 0
            new_value = "true" if active_flag else "false"
            if str(config_root.attrib["active"]) == new_value:
                return 2
            self.log.out(f"Setting {dataset_id} to {new_value} in {file_path}")
            config_root.attrib["active"] = new_value
            config_xml.write(file_path)
            return 1
        except Exception as ex:
            self.log.exception(ex)
            return 0

    def _queue_dataset_reload(self, dataset_id: str, flag: int):
        if dataset_id not in self._datasets_to_reload:
            self._datasets_to_reload[dataset_id] = [flag, time.monotonic()]
            self.log.debug(f"Queued {dataset_id} for reload")
        else:
            if flag > self._datasets_to_reload[dataset_id][0]:
                self._datasets_to_reload[dataset_id][0] = flag
                self.log.debug(f"Updated flag for reloading {dataset_id}")
            self._datasets_to_reload[dataset_id][1] = time.monotonic()

    def _reload_dataset(self, dataset_id, flag):
        """Actually reload a dataset"""
        subdir = "flag"
        if flag == ErddapDatasetManager.BAD_FLAG:
            subdir = "badFilesFlag"
        elif flag == ErddapDatasetManager.HARD_FLAG:
            subdir = "hardFlag"
        flag_file = self.bpd / subdir / dataset_id
        if flag_file.exists():
            return
        if not flag_file.parent.exists():
            flag_file.parent.mkdir()
        with open(flag_file, "w") as h:
            h.write("1")
        self.log.out(f"{dataset_id} reload[{flag}] set")

    def _queue_recompilation(self, skip_errored_datasets: bool = None, reload_all_datasets: bool = None, immediate: bool = False):
        self.log.debug(f"Dataset recompiliation queued")
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
        if immediate:
            self._flush_recompilation(immediate)

    def _do_recompilation(self, skip_errored_datasets: bool, reload_all_datasets: bool):
        try:
            # Load the template file
            datasets_xml = ET.parse(self.datasets_template_file)
            datasets_root = datasets_xml.getroot()

            # Track useful information here
            in_template = {ds.attrib["datasetID"]: [ds, self.datasets_template] for ds in datasets_root.iter("dataset")}

            # Compile the datasets from datasets.d
            self._compile_datasets(datasets_root, in_template)

            # Compile the block and allow lists
            self._compile_block_allow_lists(datasets_root)

            original_dataset_hashes = {}
            if self.datasets_file.exists():
                # Hash the original XML for each dataset to see if anything has changed
                original_dataset_hashes = self._load_original_hashes()

                # Backup the datasets if it exists
                self._backup_original_dataset_file()

            # Write the new datasets.xml file
            self._write_datasets_xml(datasets_xml)

            # Reload datasets as needed
            self._reload_datasets_on_compile(datasets_root, original_dataset_hashes, reload_all_datasets)

            # Ensure all the dataset reloads are pushed out
            self._flush_datasets(True)

            # Cleanup the backup files
            self._cleanup_backup_files()

            self.log.out(f"Dataset recompilation completed")

        except Exception as ex:
            self.log.exception(ex)

    def _cleanup_backup_files(self):
        """Cleanup backup files as needed"""
        gate = (datetime.datetime.now() - datetime.timedelta(days=self._backup_retention_days)).timestamp()
        total_count = 0
        if self.backup_directory and self.backup_directory.exists():
            for backup in os.scandir(self.backup_directory):
                if backup.stat().st_mtime < gate:
                    self.log.info(f"Removing {backup.path}")
                    pathlib.Path(backup.path).unlink()
                    total_count += 1

    def _reload_datasets_on_compile(self, datasets_root: ET.Element, original_dataset_hashes: dict, reload_all_datasets: bool):
        """Reload datasets as needed on recompilation"""
        has_new_datasets = False
        reload_found = False
        for ds in datasets_root.iter("dataset"):
            updated_hash = self._hash_xml_element(ds)
            ds_id = ds.attrib['datasetID']

            # Only datasets that were in the previous file can be reloaded, so we will limit ourselves to
            # those files
            if ds_id in original_dataset_hashes:
                # If the entry is in the previous file and the entry has changed, do a hard reload
                if original_dataset_hashes[ds_id] != updated_hash:
                    self._queue_dataset_reload(ds_id, 2)
                    reload_found = True

                # If we are reloading all datasets, we will do a bad files reload
                elif reload_all_datasets:
                    self._queue_dataset_reload(ds_id, 1)
                    reload_found = True
            else:
                has_new_datasets = True

        # If we haven't reloaded another dataset, we'll do a soft reload of one at random just to get ERDDAP
        # to reload the datasets.xml file for anything new.
        if has_new_datasets and original_dataset_hashes and not reload_found:
            self._queue_dataset_reload(list(original_dataset_hashes.keys())[0], 0)

    def _write_datasets_xml(self, datasets_xml):
        """Write the datasets.xml file"""
        self.log.info(f"Writing datasets.xml")
        with open(self.datasets_file, "w") as h:
            # Ensure each element has a new line after it
            indent(datasets_xml.getroot())
            # Convert to a string
            out_str = ET.tostring(datasets_xml.getroot(), encoding="unicode", short_empty_elements=False)
            # Remove extra spaces
            while "\n\n" in out_str:
                out_str = out_str.replace("\n\n", "\n")
            # ERDDAP doesn't like non-encoded XML characters, so we will replace them with entities here
            real_out_str = ""
            for c in out_str:
                if c == "\n" and real_out_str and real_out_str[-1] == "\n":
                    continue
                o = ord(c)
                if o < 128:
                    real_out_str += c
                else:
                    real_out_str += f"&#{o};"
            # Header
            h.write("<?xml version='1.0' encoding='ISO-8859-1'?>\n")
            # Keep track of the depth to indent lines
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

    def _backup_original_dataset_file(self):
        """Backup the current datasets.xml file"""
        if self.backup_directory and self.backup_directory.exists():
            n = 1
            backup_file = self.backup_directory / f"datasets.{datetime.datetime.now().strftime('%Y%m%d%H%M')}.{n}.xml"
            while backup_file.exists():
                n += 1
                backup_file = self.backup_directory / f"datasets.{datetime.datetime.now().strftime('%Y%m%d%H%M')}.{n}.xml"
            shutil.copy2(self.datasets_file, backup_file)
        else:
            self.log.warning(f"Backups not configured, skipping backup process")

    def _load_original_hashes(self) -> dict:
        """Load the original hashes from the original XML document"""
        try:
            return {
                ds.attrib["datasetID"]: self._hash_xml_element(ds)
                for ds in ET.parse(self.datasets_file).getroot().iter("dataset")
            }
        except ET.ParseError:
            pass

    def _compile_datasets(self, datasets_root, in_template: dict):
        """Compile the datasets into the new dataset XML element"""
        for ds_id, ds_root, file_path in self._find_datasets():
            if ds_id in in_template:
                self.log.warning(f"Overwriting definition of {ds_id} defined in {in_template[ds_id][1]}")
                datasets_root.remove(in_template[ds_id][0])
            datasets_root.append(ds_root)
            in_template[ds_id] = [ds_root, file_path]

    def _find_datasets(self, skip_errored_datasets: bool = False):
        """Find all datasets"""
        for file in os.scandir(self.datasets_directory):
            try:
                config_xml = ET.parse(file.path)
                config_root = config_xml.getroot()
                ds_id = config_root.attrib["datasetID"]
                yield ds_id, config_root, file.path
            except Exception as ex:
                if not skip_errored_datasets:
                    raise ex
                else:
                    self.log.exception(ex)

    def _hash_xml_element(self, element) -> str:
        """Generate a stable hash of an XML element"""
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

    def _expand_ip_addresses(self, ip_list: set, allow_ranges: bool = False):
        """Convert IP addresses and subnets to a list of IP addresses that ERDDAP will recognize"""
        for ip in ip_list:

            # Remove blanks
            if not ip:
                continue

            # Handle subnets which ERDDAP doesn't natively support
            if "/" in ip:
                for subnet_ip in self._subnet_to_erddap_range(ip, allow_ranges):
                    yield str(subnet_ip)

            # Handle converting ERDDAP ranges to individual IPs where ERDDAP doesn't support them (allow unlimited)
            elif "*" in ip and not allow_ranges:
                for ip in self._erddap_range_to_ips(ip):
                    yield ip

            # Just a plain IP address
            else:
                yield ip

    def _erddap_range_to_ips(self, ip):
        # Expand ERDDAP's asterisk ranges for unlimitedIP if it was used (probably not a good practice)
        pieces = ip.split(".")
        if pieces[0] == "*" or pieces[1] == "*" or (pieces[3] == "*" and not pieces[2] == "*"):
            self.log.warning(f"Bad format for ERDDAP range: {ip}")
        elif pieces[2] != "*" and pieces[3] == "*":
            for i in range(0, 256):
                yield f"{pieces[0]}.{pieces[1]}.{pieces[2]}.{i}"
        elif pieces[2] == "*" and pieces[3] == "*":
            for i in range(0, 256):
                for j in range(0, 256):
                    yield f"{pieces[0]}.{pieces[1]}.{i}.{j}"

    def _subnet_to_erddap_range(self, ip_address: str, allow_ranges: bool):
        """Handle conversion to ERDDAP ranges to reduce overhead"""

        # IPv6 not supported for ERDDAP (I think? TBD)
        if "." not in ip_address:
            subnet = ipaddress.IPv6Network(ip_address)
            for subnet_ip in subnet:
                yield subnet_ip

        # IPv4 support
        subnet = ipaddress.IPv4Network(ip_address)
        base_addr = int(subnet.network_address)
        subnet_size = int(subnet.broadcast_address) - base_addr

        # Smaller than 256 addresses, nothing we can do to simplify (X.Y.Z.* is too big) (or we aren't allowing ranges)
        if (not allow_ranges) or subnet_size < 256:
            for subnet_ip in subnet:
                yield subnet_ip

        # [256, 65536) addresses means we are smaller than an X.Y.*.* range but enclose at least one X.Y.Z.* range
        elif subnet_size < 65536:
            for i in range(0, subnet_size, 256):
                addr = str(subnet[i]).split(".")
                addr[3] = '*'
                yield '.'.join(addr)

        # Otherwise, we can do are X.Y.*.* ranges (ERDDAP does not support X.*.*.* ranges)
        else:
            for i in range(0, subnet_size, 65536):
                addr = str(subnet[i]).split(".")
                addr[3] = '*'
                addr[2] = '*'
                yield '.'.join(addr)

    def _compile_block_allow_lists(self, datasets_root):
        """Compile all of the allow and block lists onto the dataset root"""
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
        ip_blocks.update(self._ip_block_list.read_all())
        email_blocks.update(self._email_block_list.read_all())
        unlimited_allow.update(self._unlimited_allow_list.read_all())

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

    def _flush_recompilation(self, force: bool = False):
        """Flush the recompilation if necessary"""
        if self._compilation_requested is None:
            return
        if force or (time.monotonic() - self._compilation_requested[2] > self._max_recompilation_delay):
            try:
                self._do_recompilation(self._compilation_requested[0], self._compilation_requested[1])
            except Exception as ex:
                self.log.exception(ex)
            finally:
                self._compilation_requested = None

    def _flush_datasets(self, force: bool = False):
        """Flush all dataset changes"""
        ds_ids = [(k, self._datasets_to_reload[k][1]) for k in self._datasets_to_reload]
        ds_ids.sort(key=lambda x: x[1])
        auto_reload = (len(ds_ids) - self._max_pending_reloads) if self._max_pending_reloads > 0 else -1
        now_t = time.monotonic()
        for dataset_id, _ in ds_ids:
            if force or auto_reload > 0 or (now_t - self._datasets_to_reload[dataset_id][1]) > self._max_reload_delay:
                auto_reload -= 1
                try:
                    self._reload_dataset(dataset_id, self._datasets_to_reload[dataset_id][0])
                except Exception as ex:
                    self.log.exception(ex)
                finally:
                    del self._datasets_to_reload[dataset_id]


def indent(elem, level=0):
    """Indent an XML file"""
    elem.tail = "\n"
    for se in elem:
        indent(se, level + 1)
    return elem


class AllowBlockListFile:
    """Manage an allow or block file"""

    def __init__(self, file_path: pathlib.Path):
        self.file_path = file_path
        self.file_entries = None
        self._mtime_at_load = None
        self._entry_cache = None
        self.log = logging.getLogger("erddaputil.erddap")

    def check_config(self) -> bool:
        """Check if the configuration is valid"""
        if not self.file_path:
            raise ValueError(f"Missing allow/block list file")
        if not self.file_path.parent.exists():
            raise ValueError(f"Parent directory {self.file_path.parent} does not exist")
        return True

    def read_all(self) -> set:
        """Read all entries into a set"""
        if self._check_cache_reload():
            if not self.file_path.exists():
                self._entry_cache = []
            else:
                self.log.info(f"Reading {self.file_path} from disk")
                self._mtime_at_load = os.stat(self.file_path).st_mtime
                with open(self.file_path, "r") as h:
                    self._entry_cache = set(x.strip("\r\n\t ").lower() for x in h)
        return self._entry_cache

    def _check_cache_reload(self) -> bool:
        """Check if the cache needs reloading"""
        if self._entry_cache is None:
            return True
        if self._mtime_at_load is None:
            return True
        if self.file_path is None or not self.file_path.exists():
            return False
        return os.stat(self.file_path).st_mtime > self._mtime_at_load

    def write_all(self, lst: t.Iterable):
        """Write all items in the given lst to the file"""
        self.log.info(f"Writing {self.file_path} to disk")
        with open(self.file_path, "w") as h:
            for entry in lst:
                h.write(entry)
                h.write("\n")
        self._mtime_at_load = os.stat(self.file_path).st_mtime

    def append_or_remove(self, entries: t.Union[t.Iterable, str], append: bool, validate_as: t.Optional[str] = None) -> bool:
        """Append or remove, depending on a flag."""
        self.check_config()

        # Ensure we have a set
        entries = AllowBlockListFile.input_to_set(entries)

        # Do the validation
        if validate_as == 'email':
            for email in entries:
                self._validate_email(email)
        elif validate_as == "ip":
            for ip in entries:
                self._validate_ip_address(ip)
        elif validate_as is not None:
            raise ValueError(f"Unknown validation method {validate_as}")

        # Append or remove as needed
        if append:
            return self.append(entries)
        else:
            return self.remove(entries)

    def append(self, entries: t.Iterable) -> bool:
        """Append items to the file"""
        lst = self.read_all()
        lst_changed = False
        for entry in entries:
            entry = entry.lower()
            if entry not in lst:
                self.log.out(f"Adding {entry} to {self.file_path}")
                lst.add(entry)
                lst_changed = True
        if lst_changed:
            self.write_all(lst)
            return True
        else:
            return False

    def remove(self, entries: t.Iterable) -> bool:
        """Remove items from the file"""
        lst = self.read_all()
        lst_changed = False
        for entry in entries:
            entry = entry.lower()
            if entry in lst:
                self.log.out(f"Removing {entry} from {self.file_path}")
                lst.remove(entry)
                lst_changed = True
        if lst_changed:
            self.write_all(lst)
            return True
        else:
            return False

    @staticmethod
    def input_to_set(original_input: t.Union[str, t.Iterable[str]]) -> set[str]:
        """Convert a comma-delimited string or iterable to a set()"""
        if isinstance(original_input, str):
            if "," in original_input:
                return set(x for x in original_input.split(","))
            else:
                return {original_input}
        else:
            return set(x for x in original_input)

    def _validate_email(self, email_address: str):
        """Validate an Email address for ERDDAP"""
        if email_address.count("@") != 1:
            raise ValueError(f"Invalid email address: {email_address}")
        if email_address[0] == "@":
            raise ValueError(f"Invalid email address: {email_address}")
        if "." not in email_address[email_address.find("@"):]:
            raise ValueError(f"Invalid email address: {email_address}")
        if "," in email_address:
            raise ValueError(f"ERDDAP does not allow commas in email addresses: {email_address}")

    def _validate_ip_address(self, ip_address: str):
        """Validate an IP address for ERDDAP"""
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
            for p in pieces:
                if p == "*":
                    continue
                if not 0 <= int(p) <= 255:
                    raise ValueError(f"Invalid IP address: {ip_address}")
        else:
            # Test the IP address to make sure it is a valid IP address
            # raises ValueError if the address is invalid
            if "/" in ip_address:
                ipaddress.ip_network(ip_address)
            else:
                ipaddress.ip_address(ip_address)
