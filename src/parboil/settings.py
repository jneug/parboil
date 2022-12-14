"""Some global settings for parboil."""

from pathlib import Path

from .console import out

CFG_DIR = Path("~/.config/parboil").expanduser()
CFG_FILE = CFG_DIR / "config.json"
TPL_DIR = CFG_DIR / "templates"

PRJ_FILE = "parboil.json"
META_FILE = ".parboil"

ERROR_LOG_FILENAME = CFG_DIR / "parboil-errors.log"

DEFAULT_CONFIG = {"exclude": ["**/.DS_Store", "**/Thumbs.db"]}

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s:%(name)s:%(process)d:%(lineno)d "
            "%(levelname)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "%(message)s",
        },
    },
    "handlers": {
        "logfile": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "filename": ERROR_LOG_FILENAME,
            "formatter": "default",
            "backupCount": 2,
        },
        "verbose_output": {
            # "class": "logging.StreamHandler",
            # "stream": "ext://sys.stdout",
            "class": "rich.logging.RichHandler",
            "level": "DEBUG",
            "formatter": "simple",
            "rich_tracebacks": True,
            "tracebacks_suppress": ["click"],
            "console": out,
            "show_time": False,
        },
    },
    "loggers": {
        "parboil": {
            "level": "WARN",
            "handlers": [
                "verbose_output",
            ],
        },
    },
    "root": {"level": "INFO", "handlers": ["logfile"]},
}
