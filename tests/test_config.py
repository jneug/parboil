# -*- coding: utf-8 -*-
"""Tests for loading configuration from files or cli arguments"""

import json
import os
import time
from pathlib import Path

import pytest

from parboil.parboil import CFG_DIR, CFG_FILE

def test_config_default(config_path):
    """Loading default configuration from home folder"""

    # Test default values if no config present
    cfg_path = Path(CFG_DIR).expanduser()
    cfg_file = cfg_path / CFG_FILE
