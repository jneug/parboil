# -*- coding: utf-8 -*-

import shutil
import json
from pathlib import Path


import pytest
from click.testing import CliRunner


@pytest.fixture(autouse=True)
def mock_home(monkeypatch, tmp_path):
    """Monkeypatch the user home folder."""
    root_path = tmp_path.joinpath("home")
    root_path.mkdir()
    #config_path = root_path.joinpath(".config", "parboil")
    #config_path.mkdirs(parents=True)

    monkeypatch.setenv("HOME", str(root_path))
    monkeypatch.setenv("USERPROFILE", str(root_path))


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


@pytest.fixture()
def tpl_path(request):
    """Get the path to the test folder"""
    #return request.fspath / "templates"
    return Path("tests/templates")


@pytest.fixture()
def repo_path(tmp_path):
    """
    Create a temporary repository folder
    """
    repo_dir = tmp_path / "repository"
    repo_dir.mkdir()
    return repo_dir


@pytest.fixture()
def out_path(tmp_path):
    """Create a temporary repository folder"""
    out_dir = tmp_path / "output"
    out_dir.mkdir(exist_ok=True)

    return out_dir


@pytest.fixture()
def boil_runner(repo_path):
    runner = CliRunner()
    
    def boil_run(*args, **kwargs):
        return runner.invoke("boil", args, **kwargs)
    
    return boil_run
