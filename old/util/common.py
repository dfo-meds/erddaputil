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


def load_object(obj_name: str):
    package_dot_pos = obj_name.rfind(".")
    package = obj_name[0:package_dot_pos]
    specific_cls_name = obj_name[package_dot_pos + 1:]
    mod = importlib.import_module(package)
    return getattr(mod, specific_cls_name)
