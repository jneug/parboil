# -*- coding: utf-8 -*-

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from parboil.parboil import boil


@pytest.fixture(autouse=True)
def mock_home(monkeypatch, tmp_path):
    """Monkeypatch the user home folder."""
    home_path = tmp_path.joinpath("home")
    config_path = home_path.joinpath(".config", "parboil", "templates")
    config_path.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(home_path))
    monkeypatch.setenv("USERPROFILE", str(home_path))
    monkeypatch.setattr(Path, "home", lambda: home_path)


@pytest.fixture()
def boil_runner():
    runner = CliRunner()

    def boil_run(*args, **kwargs):
        return runner.invoke(boil, args, **kwargs)

    return boil_run


@pytest.fixture()
def config_path(tmp_path):
    """Get the path to the test folder"""
    return tmp_path.joinpath("home", ".config", "parboil")


@pytest.fixture()
def tpl_path():
    """Get the path to the test folder"""
    return Path("tests/templates")


@pytest.fixture()
def repo_path(tmp_path):
    """Create a temporary repository folder"""
    repo_dir = tmp_path / "repository"
    repo_dir.mkdir()
    return repo_dir


@pytest.fixture()
def out_path(tmp_path):
    """Create a temporary output folder"""
    out_dir = tmp_path / "output"
    out_dir.mkdir(exist_ok=True)

    return out_dir


@pytest.fixture()
def config_file(tmp_path, repo_path):
    """
    Create a temporary repository folder
    """
    config_file = tmp_path / "config.json"
    if not config_file.is_file():
        config_file.write_text(
            json.dumps(dict(TPLDIR=str(repo_path), prefilled=dict(Name="Clark Kent")))
        )

    return config_file
