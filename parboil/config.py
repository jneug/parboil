"""Utilities to load and manage parboil configurations"""

import json
import logging
from copy import deepcopy
from pathlib import Path

import typing as t

logger = logging.getLogger(__name__)


PARBOIL_DIR = "~/.config/parboil"

USER_CONFIG = PARBOIL_DIR + "/config.json"

DEFAULT_CONFIG = dict(TPLPATH=PARBOIL_DIR + "/templates")


def merge_configs(main: dict, secondary: dict) -> dict:
    config = deepcopy(main)

    for k, v in secondary.items():
        if isinstance(v, dict) and isinstance(config[k], dict):
            config[k] = merge_configs(config[k], v)
        else:
            config[k] = v

    return config


def load_configs(*args: t.Union[t.Dict[str, t.Any], Path, str]) -> dict:
    config = dict()  # type: t.Dict[str, t.Any]

    for cfg in reversed(args):
        if isinstance(cfg, dict):
            config = merge_configs(config, cfg)
        else:
            cfg = Path(cfg)
            if cfg.is_file():
                try:
                    cfg_data = json.loads(cfg.read_text())
                    config = merge_configs(config, cfg_data)
                    logger.debug(f"Added config from {str(cfg)}!")
                except json.JSONDecodeError:
                    logger.error(f"Could not load config from {str(cfg)}!")
                    pass

    return config


def get_user_config(config_file: str = None) -> dict:
    if config_file:
        return load_configs(DEFAULT_CONFIG, config_file)
    else:
        return DEFAULT_CONFIG
