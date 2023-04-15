import datetime
import time

import os

from .daemon import ErddapUtil
import sqlite3
import zirconium as zr
from autoinject import injector
import uuid
import universalio as uio
from .datasets import ErddapDatasetManager
import pathlib
import toml
import logging


@injector.injectable
class SyncDatabase:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        db_path = self.config.as_path(("erddaputil", "sync", "local_db"))
        self.local_storage_root = self.config.as_path(("erddaputil", "sync", "local_root")).resolve()
        self._security_check_root(self.local_storage_root)
        self._conn = sqlite3.connect(db_path)
        self._build_structure()
        self.log = logging.getLogger("erddaputil.sync_db")

    def _security_check_root(self, root):
        root_str = str(root)
        if root_str == "/":
            raise ValueError("LSR cannot be unix root")
        if root_str == "C:/" or root_str == "C:\\":
            raise ValueError("LSR cannot be C:/")

    def _build_structure(self):
        cur = self._conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS sync_ops (
        
            from_path TEXT NOT NULL,
            to_path TEXT NOT NULL,
            state TEXT NOT NULL,
            locked_by TEXT,
            locked_since INTEGER,
            erddap_dataset_id TEXT,
            operation TEXT,
            priority INTEGER
            
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS local_reference (
            
            local_path TEXT NOT NULL,
            remote_print TEXT,
            locked_by TEXT,
            locked_since INTEGER
            
        )""")
        cur.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_fingerprints ON local_reference(local_path)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS sync_mappings (
            source_path TEXT NOT NULL,
            target_path TEXT NOT NULL,
            recrawl_interval INTEGER,
            last_crawled INTEGER,
            erddap_dataset_id TEXT NOT NULL
        )""")
        cur.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_mappings ON sync_mappings(source_path, target_path)""")
        self._conn.commit()

    def sync_maps_from_file(self, map_file):
        map_info = toml.load(map_file)
        for key in map_info:
            info = map_info[key]
            if "active" in info and not info["active"]:
                self.remove_sync_mapping(info["source_path"], info["target_path"])
            elif "source" not in info:
                self.log.warning(f"Source path missing from {key}, ignoring it")
            elif "target" not in info:
                self.log.warning(f"Target path missing from {key}, ignoring it")
            else:
                self.add_sync_mapping(
                    info["source"],
                    info["target"],
                    info["dataset_id"] if "dataset_id" in info else "",
                    int(info["recrawl"]) if "recrawl" in info else None
                )

    def add_sync_mapping(self, source_path, target_path, erddap_dataset_id="", recrawl_interval=None):
        # target must be a directory
        if not target_path.endswith("/"):
            target_path += "/"
        if not source_path.endswith("/"):
            source_path += "/"
        if recrawl_interval is None:
            recrawl_interval = self.config.as_int(("erddaputil", "sync", "default_recrawl_interval_seconds"), default=604800)
        if recrawl_interval <= 0 or recrawl_interval is False:
            recrawl_interval = None  # Never recrawl
        cur = self._conn.cursor()
        cur.execute("INSERT INTO sync_mappings (source_path, target_path, recrawl_interval, erddap_dataset_id VALUES (?, ?, ?, ?) ON CONFLICT (source_path, target_path) DO UPDATE SET recrawl_interval=excluded.recrawl_interval, erddap_dataset_id=excluded.erddap_dataset_id", [
            source_path,
            target_path,
            int(recrawl_interval) if recrawl_interval else None,
            erddap_dataset_id
        ])
        self._conn.commit()
        self.request_sync(source_path, target_path, erddap_dataset_id, "sync")

    def sync_from_source(self, source_file, force: bool = False):
        for _, source_prefix, target_path, _, _, edsid in self._list_source_paths():
            if source_file.startswith(source_prefix):
                self._setup_sync_from_source_request(source_file, source_prefix, target_path, edsid, force)
                return True
        return False

    def enqueue_sync_times(self):
        cur = self._conn.cursor()
        for rowid, source_prefix, target_path, recrawl_interval, last_crawled, edsid in self._list_source_paths():
            if recrawl_interval is None or recrawl_interval <= 0:
                continue
            if not self._needs_recrawl(recrawl_interval, last_crawled):
                continue
            cur.execute("UPDATE sync_mappings SET last_crawled = ? WHERE rowid = ?", [
                datetime.datetime.utcnow().timestamp(),
                rowid
            ])
            self.request_sync(source_prefix, target_path, edsid)
            self._conn.commit()

    def _needs_recrawl(self, interval, last):
        if last is None:
            return True
        diff = datetime.datetime.utcnow().timestamp() - last
        return diff >= interval

    def _list_source_paths(self):
        cur = self._conn.cursor()
        for row in cur.execute("SELECT rowid, source_path, target_path, recrawl_interval, last_crawled, erddap_dataset_id FROM sync_mappings ORDER BY LENGTH(source_path) DESC"):
            yield row[0], row[1], row[2], row[3], row[4], row[5]

    def _setup_sync_from_source_request(self, source_file, source_path, target_path, erddap_dataset_id, force):
        file_suffix = source_file[len(source_path):]
        target_file = target_path + file_suffix
        self.request_sync(source_file, target_file, erddap_dataset_id, "sync" if not force else "force_sync")

    def remove_sync_mapping(self, source_path, target_path):
        cur = self._conn.cursor()
        row = cur.execute("SELECT rowid, erddap_dataset_id FROM sync_mappings WHERE source_path = ? AND target_path = ?", [source_path, target_path]).fetchone()
        if row:
            cur.execute("DELETE FROM sync_mappings WHERE source_path = ? AND target_path = ?", [source_path, target_path])
            self._conn.commit()
            self.request_sync("", target_path, row[0], "cleanup")
            return True
        return False

    def get_fingerprint(self, to_path):
        cur = self._conn.cursor()
        row = cur.execute("SELECT remote_print FROM local_reference WHERE local_path = ?", [to_path]).fetchone()
        return row[0] if row else None

    def set_fingerprint(self, to_path, remote_print):
        cur = self._conn.cursor()
        cur.execute("INSERT INTO local_reference(local_path, remote_print) VALUES (?, ?) ON CONFLICT(local_path) DO UPDATE SET remote_print=excluded.remote_print ", [
            to_path,
            remote_print
        ])
        self._conn.commit()

    def request_sync(self, from_path, to_path, erddap_dataset_id=None, operation="sync", priority=None):
        cur = self._conn.cursor()
        if priority is None:
            if operation == 'sync':
                priority = 50
            elif operation == 'force_sync':
                priority = 100
            else:
                priority = 0
        check = cur.execute("SELECT rowid, priority FROM sync_ops WHERE from_path = ? AND to_path = ? AND state = 'pending' AND operation = ?", [from_path, to_path, operation]).fetchone()
        if check:
            # Sync already requested, prevent duplicates but update the priority if necessary
            if check[1] < priority:
                cur.execute("UPDATE sync_ops SET priority = ? WHERE rowid = ?", [priority, check[0]])
                self._conn.commit()
        else:
            cur.execute("""
                INSERT 
                    INTO sync_ops (from_path, to_path, state, locked_by, locked_since, erddap_dataset_id, operation, priority) 
                    VALUES (?, ?, 'pending', NULL, NULL, ?, ?, ?)
            """, [
                from_path,
                to_path,
                erddap_dataset_id,
                operation,
                priority
            ])
            self._conn.commit()

    def get_sync_op(self):
        my_id = str(uuid.uuid4())
        top_cur = self._conn.cursor()
        top_cur.execute("SELECT rowid, to_path FROM sync_ops WHERE locked_by IS NULL AND state = 'pending' ORDER BY priority DESC, rowid ASC")
        row = top_cur.fetchone()
        while row:
            cur = self._conn.cursor()
            row2 = cur.execute("SELECT rowid, locked_by FROM local_reference WHERE local_path = ?", [row[1]]).fetchone()
            if row2 is None:
                cur.execute("INSERT INTO local_reference (local_path, remote_print) VALUES (?, None)", [row[1]])
                self._conn.commit()
            elif row2[1]:
                row = top_cur.fetchone()
                continue
            cur.execute("UPDATE sync_ops SET locked_by = ?, state = 'in_progress', locked_since = ? WHERE rowid = ? AND locked_by IS NULL", [
                my_id,
                datetime.datetime.utcnow().timestamp(),
                row[0],
            ])
            cur.execute("UPDATE local_reference SET locked_by = ?, locked_since = ? WHERE local_path = ?", [
                my_id,
                datetime.datetime.utcnow().timestamp(),
                row[1]
            ])
            self._conn.commit()
            row = cur.execute("SELECT rowid, from_path, to_path, locked_by, erddap_dataset_id, operation FROM sync_ops WHERE rowid = ?", [row[0]]).fetchone()
            row2 = cur.execute("SELECT rowid, locked_by FROM local_reference WHERE local_path = ?", [row[2]]).fetchone()
            if row[3] != my_id:
                if row2[1] == my_id:
                    cur.execute("UPDATE local_reference SET locked_by = NULL, locked_since = NULL WHERE local_path = ?", [row[2]])
                    self._conn.commit()
                row = top_cur.fetchone()
                continue
            elif row2[1] != my_id:
                cur.execute("UPDATE sync_ops SET locked_by = NULL, locked_since = NULL, state = 'pending' WHERE rowid = ?", [row[0]])
                self._conn.commit()
                row = top_cur.fetchone()
                continue
            else:
                return {
                    "rowid": row[0],
                    "from_path": row[1],
                    "to_path": str(self.local_storage_root / row[2]),
                    "erddap_dataset_id": row[4],
                    "operation": row[5]
                }

    def release_lock(self, op, success: bool, retry: bool = False):
        cur = self._conn.cursor()
        cur.execute("UPDATE sync_ops SET state = ?, locked_by = NULL, locked_since = NULL WHERE rowid = ?", [
            'complete' if success else ('pending' if retry else 'failed'),
            op['rowid']
        ])
        self._conn.commit()


class ErddapFileSync(ErddapUtil):

    sync_db: SyncDatabase = None

    @injector.construct
    def __init__(self, raise_error: bool = False):
        super().__init__("sync", raise_error, 2)
        self.dsm = ErddapDatasetManager()
        self._pending_reloads = set()
        self._pending_file_count = 0
        self._max_pending_reloads = 2
        self._max_pending_file_count = 1000
        self._mono_time_start = None
        self._max_reload_delay_seconds = 60

    def _flush_reloads(self):
        for ds_id in self._pending_reloads:
            self.dsm.reload_dataset(ds_id)
        self._pending_reloads = set()
        self._pending_file_count = 0
        self._mono_time_start = None

    def _reload_erddap_dataset(self, dataset_id):
        if dataset_id is None or dataset_id == "":
            return
        if dataset_id not in self._pending_reloads:
            if len(self._pending_reloads) >= self._max_pending_reloads:
                self._flush_reloads()
            self._pending_reloads.add(dataset_id)
        self._pending_file_count += 1
        if self._mono_time_start is None:
            self._mono_time_start = time.monotonic()
        elif 0 <= self._max_reload_delay_seconds <= (time.monotonic() - self._mono_time_start):
            self._flush_reloads()
        if self._pending_file_count > self._max_pending_file_count >= 0:
            self._flush_reloads()

    def _init(self):
        pass

    def _run(self, *args, **kwargs):
        row = None
        success = False
        retry = True
        try:
            row = self.sync_db.get_sync_op()
            if not row:
                self._flush_reloads()
                success = True
                retry = False
            elif row['operation'] in ('sync', 'force_sync'):
                success, retry = self._handle_copy(row)
            elif row['operation'] == 'cleanup':
                success, retry = self._handle_cleanup(row)
            else:
                retry = False
                self.log.error(f"Unknown operation type {row['operation']}")
        finally:
            if row:
                self.sync_db.release_lock(row, success, retry)
        return success

    def _handle_cleanup(self, row) -> (bool, bool):
        dest = pathlib.Path(row['to_path'])
        if not dest.is_symlink():
            dest = dest.resolve(True)
            if not str(dest).startswith(str(self.sync_db.local_storage_root)):
                self.log.error(f"Path {dest} is outside of the local storage root, ignoring")
                return False, False
            # Does not exist
            elif not dest.exists():
                return True, False
            # Is a directory
            elif dest.is_dir():
                for file in os.scandir(dest):
                    if not file.is_symlink():
                        self.sync_db.request_sync("", file.path, row['erddap_dataset_id'], 'cleanup')
                return True, False
            # Is a file
            elif dest.is_file():
                dest.unlink(True)
                self._reload_erddap_dataset(row['erddap_dataset_id'])
                return True, False
        else:
            self.log.warning(f"Attempt to remove symlink {dest}, skipping")
        return False, False

    def _handle_copy(self, row) -> (bool, bool):
        src = uio.FileWrapper(row['from_path'])
        dest = uio.FileWrapper(row['to_path'])
        try:
            # If it is a directory, process it recursively
            if src.is_dir():
                for path, mirror in src.crawl(dest, True, True):
                    self.sync_db.request_sync(str(path), str(mirror), row['erddap_dataset_id'], row['operation'])
                return True, False
            # Otherwise, we will check the fingerprint and continue
            else:
                current_print = src.fingerprint()
                last_print = self.sync_db.get_fingerprint(row['to_path']) if row['operation'] == 'sync' else None
                if current_print is None or last_print != current_print:
                    src.copy(dest, require_not_exists=False, allow_overwrite=True, recursive=True, use_partial_file=True)
                    self.sync_db.set_fingerprint(row['to_path'], current_print)
                    self._reload_erddap_dataset(row['erddap_dataset_id'])
                return True, False
        except Exception as ex:
            self.log.error(f"Error copying {src} to {dest}: {str(ex)}")
        return False, False

    def _cleanup(self):
        self._flush_reloads()
