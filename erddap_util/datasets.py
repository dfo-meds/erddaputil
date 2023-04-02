import zirconium as zr
from autoinject import injector
import os
import pathlib


class ErddapDatasetManager:

    config: zr.ApplicationConfig = None

    HARD_FLAG = 2
    BAD_FILES = 1
    SOFT_FLAG = 0

    @injector.construct
    def __init__(self):
        self.bpd = self.config.as_path(("erddaputil", "big_parent_dir"))
        if (not self.bpd) or not self.bpd.exists():
            raise ValueError(f"BigParentDirectory not configured properly: {self.bpd}")
        self.datasets_file = self.config.as_path(("erddaputil", "datasets_file"))
        if (not self.datasets_file) or not self.datasets_file.exists():
            raise ValueError(f"Datasets file not configured properly: {self.datasets_file}")
        self.datasets_d = self.config.as_path(("erddaputil", "datasets_d"))
        self.datasets_template = self.config.as_path(("erddaputil", "datasets_template"))

    def reload_dataset(self, dataset_id: str, flag: int = 0):
        subdir = "flag"
        if flag == ErddapDatasetManager.BAD_FILES:
            subdir = "badFilesFlag"
        elif flag == ErddapDatasetManager.HARD_FLAG:
            subdir = "hardFlag"
        flag_file = self.bpd / subdir / dataset_id
        with open(flag_file, "w") as h:
            h.write("1")

    def set_active_flag(self, dataset_id: str, active_flag: bool):
        if self.datasets_d:
            for file in os.scandir(self.datasets_d):
                if self._try_setting_active_flag(pathlib.Path(file.path), dataset_id, active_flag):
                    self.compile_datasets()
            else:
                if not self._try_setting_active_flag(self.datasets_file, dataset_id, active_flag):
                    print(f"Could not find dataset {dataset_id} in {self.datasets_d}")
                    return
        else:
            if not self._try_setting_active_flag(self.datasets_file, dataset_id, active_flag):
                print(f"Could not find dataset {dataset_id} in {self.datasets_d}")
                return
        self.reload_dataset(dataset_id)

    def compile_datasets(self):
        pass

    def _try_setting_active_flag(self, file_path: pathlib.Path, dataset_id: str, active_flag: bool) -> bool:
        return False
