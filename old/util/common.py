import zirconium as zr
import zrlog
import pathlib
import os
import importlib

ROOT_DIR = pathlib.Path(__file__).absolute().parent.parent


def init_util(extra_files=None, override_dir=None):

    @zr.configure
    def add_config_files(config: zr.ApplicationConfig):
        config_paths = [
            ROOT_DIR,
            pathlib.Path("~").expanduser().absolute(),
            pathlib.Path(".").absolute()
        ]
        config_paths.extend(os.environ.get("ERDDAPUTIL_CONFIG_PATHS", default="").split(";"))
        config.register_files(config_paths,
                              [".clusterman.toml", ".erddaputil.toml"],
                              [".clusterman.defaults.toml", ".erddaputil.defaults.toml"])
    zrlog.init_logging()

