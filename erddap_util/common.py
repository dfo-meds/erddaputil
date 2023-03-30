import zirconium as zr
import zrlog
import pathlib
import os

ROOT_DIR = pathlib.Path(__file__).absolute().parent


def init_util(extra_files=None):

    @zr.configure
    def add_config_files(config: zr.ApplicationConfig):
        config_paths = [
            ROOT_DIR,
            pathlib.Path("~").expanduser().absolute(),
            pathlib.Path(".").absolute()
        ]
        extra_paths = os.environ.get("ERDDAPUTIL_CONFIG_PATH", default="")
        if extra_paths:
            config_paths.extend([pathlib.Path(x) for x in extra_paths.split(";")])
        for path in config_paths:
            config.register_default_file(path / ".erddaputil.defaults.yaml")
            config.register_default_file(path / ".erddaputil.defaults.toml")
            config.register_file(path / ".erddaputil.yaml")
            config.register_file(path / ".erddaputil.toml")
            for file in extra_paths or []:
                config.register_file(path / file)

    zrlog.init_logging()
