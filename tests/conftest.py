# -*- coding: utf-8 -*-

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from parboil.parboil import boil
from parboil.project import META_FILE


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "tpl_repo_contents"
    )
    config.addinivalue_line(
        "markers", "repo_path_contents"
    )
    config.addinivalue_line(
        "markers", "prefilled_values"
    )


@pytest.fixture(autouse=True)
def mock_home(monkeypatch, tmp_path):
    """Monkeypatch the user home folder."""
    home_path = tmp_path.joinpath("home")
    config_path = home_path.joinpath(".config", "parboil", "templates")
    config_path.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(home_path))
    monkeypatch.setenv("USERPROFILE", str(home_path))
    monkeypatch.setattr(Path, "home", lambda: home_path)


def mock_install(source, dest, symlink=False, created=946681200.0, updated=None):
    """
    Simulate install of templates to a target folder by vopyong all template files and creating a metadata file with the specified data. 
    """
    if source.is_dir():
        if not symlink:
            shutil.copytree(source, dest)
            
            meta_data = dict(
                source_type = "local",
                source = str(source.resolve())
            )
            if created:
                meta_data["created"] = created
            if updated:
                meta_data["updated"] = updated
            meta_file = dest / META_FILE
            meta_file.write_text(
                json.dumps(meta_data)
            )
        else:
            dest.symlink_to(source, target_is_directory=True)


@pytest.fixture()
def mockinstall():
    return mock_install


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
    """Get the path to the test templates folder"""
    return Path("tests/templates")


@pytest.fixture()
def repo_path(tmp_path, tpl_path):
    """
    Create a temporary repository folder outside the default config_path
    
    Optionally a set of template names inside tpl_path can be passed in by using the repo_path_contents mark. These templates will be "installed" into the repository by copying them and creating mock metadata files:
    
    {
        "source_type": "local",
        "source": {source_path},
        "created":  946681200.0 # 2000-01-01
    }
    """
    repo_dir = tmp_path / "repository"
    repo_dir.mkdir()
    
    marker = request.node.get_closest_marker("tpl_repo_contents")
    if marker is not None:
        for tpl in marker.args:
            mock_install(
                tpl_path / tpl,
                repo_dir / tpl
            )
        )
    
    return repo_dir


@pytest.fixture()
def out_path(tmp_path):
    """Create a temporary output folder"""
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    return out_dir
    

@pytest.fixture()
def tpl_repo(tmp_path, tpl_path):
    """
    Creates a temporary folder containing a set of test templates.
    
    The templates to copy can be passed in by using the tpl_repo_contents mark.
    
    Used for testing installation of template directories.
    """
    repo_dir = tmp_path / "template_repository"
    repo_dir.mkdir()
    
    marker = request.node.get_closest_marker("tpl_repo_contents")
    
    templates = ["hello_world", "test"]
    if marker is not None:
        templates = marker.args
    
    for tpl in templates:
        tpl_dir = tpl_path / tpl
        if tpl_dir.is_dir():
            shutil.copytree(tpl_dir, repo_dir / tpl)

    return repo_dir


@pytest.fixture()
def config_file(tmp_path, repo_path):
    """
    Create a temporary config file to use with the -c option.
    
    The file will configure repo_path as the template repository and add any keyword arguments for the prefilled_values marker as prefilled values. If no such marker is present, the Name "Clark Kent" and Email "kent@daily-planet.com" is added.
    """
    prefilled = dict(
        Name="Clark Kent",
        Email="kent@daily-planet.com"
    )
    
    marker = request.node.get_closest_marker("prefilled_values")
    if marker:
        
    
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(dict(
            TPLDIR=str(repo_path), prefilled=prefilled
        ))
    )

    return config_file
