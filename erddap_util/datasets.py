import zirconium as zr
from autoinject import injector


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

    def reload_dataset(self, dataset_id: str, flag: int = 0):
        subdir = "flag"
        if flag == ErddapDatasetManager.BAD_FILES:
            subdir = "badFilesFlag"
        elif flag == ErddapDatasetManager.HARD_FLAG:
            subdir = "hardFlag"
        flag_file = self.bpd / subdir / dataset_id
        with open(flag_file, "w") as h:
            h.write("1")

