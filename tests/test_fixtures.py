# -*- coding: utf-8 -*-
"""Tests for custom pytest fixtures (got to test them all)"""

import json
import os
import time
from pathlib import Path

import pytest

from parboil.project import META_FILE


def test_fixture_mock_home(tmp_path):
    """
    The home folder is automatically monkeypatched to a temporary location.
    """
    assert Path.home().parent == tmp_path
    assert os.path.expanduser("~") == str(Path.home())


def test_fixture_tpl_path(tpl_path):
    """
    Should return a path to the location of the test templates.
    """
    test_templates = ["test", "hello_world", "license", "environ"]
    assert all(tpl_path.joinpath(tpl).is_dir() for tpl in test_templates)


def test_fixture_mockinstall(mockinstall, tmp_path, tpl_path):
    """
    Test mock installs of templates to a temporary location.
    """
    src_path = tpl_path.joinpath("hello_world").resolve()
    dest_path = tmp_path / "hw"

    # Default install
    assert not dest_path.is_dir()
    mockinstall(src_path, dest_path)
    meta_path = dest_path / META_FILE

    assert dest_path.is_dir()
    assert meta_path.is_file()
    meta_data = json.loads(meta_path.read_text())

    assert meta_data["source"] == str(src_path)
    assert meta_data["created"] == 946681200.0
    assert "updated" not in meta_data

    # Custom install
    dest_path = tmp_path / "hw2"
    ctime = time.time() - 3600
    mtime = time.time()

    assert not dest_path.is_dir()
    mockinstall(src_path, dest_path, created=ctime, updated=mtime)
    meta_path = dest_path / META_FILE

    assert dest_path.is_dir()
    assert meta_path.is_file()
    meta_data = json.loads(meta_path.read_text())

    assert meta_data["source"] == str(src_path)
    assert meta_data["created"] == ctime
    assert meta_data["updated"] == mtime

    # Symlinked install
    dest_path = tmp_path / "hw3"

    assert not dest_path.is_dir()
    mockinstall(src_path, dest_path, symlink=True)
    meta_path = dest_path / META_FILE

    assert dest_path.is_dir()
    assert dest_path.is_symlink()
    assert not meta_path.is_file()


def test_fixture_temp_paths(config_path, repo_path, out_path):
    """
    Test if the temporary paths are created and are children to a function scoped temp location.
    """
    assert not config_path == repo_path
    assert not config_path == out_path
    assert config_path.parent.parent.parent == repo_path.parent
    assert repo_path.parent == out_path.parent


@pytest.mark.repo_path_contents("hello_world", "test")
def test_fixture_repo_path(repo_path, request):
    marker = request.node.get_closest_marker("repo_path_contents")
    for tpl in marker.args:
        assert repo_path.joinpath(tpl).is_dir()
        assert repo_path.joinpath(tpl, META_FILE).is_file()


def test_fixture_tpl_repo(tpl_repo, request):
    for tpl in ("hello_world", "test"):
        assert tpl_repo.joinpath(tpl).is_dir()


@pytest.mark.tpl_repo_contents("license", "test")
def test_fixture_tpl_repo_w_mark(tpl_repo, request):
    marker = request.node.get_closest_marker("tpl_repo_contents")
    for tpl in marker.args:
        assert tpl_repo.joinpath(tpl).is_dir()


def test_fixture_config_file(config_file, repo_path):
    assert config_file.is_file()
    cfg_data = json.loads(config_file.read_text())
    assert cfg_data["TPLDIR"] == str(repo_path)
    assert cfg_data["prefilled"]["Name"] == "Clark Kent"
    assert cfg_data["prefilled"]["Email"] == "kent@daily-planet.com"


@pytest.mark.prefilled_values(Name="Bruce Wayne", Position="Batman")
def test_fixture_config_file_w_mark(request, config_file, repo_path):
    assert config_file.is_file()
    cfg_data = json.loads(config_file.read_text())

    assert cfg_data["TPLDIR"] == str(repo_path)
    assert "Email" not in cfg_data["prefilled"]

    marker = request.node.get_closest_marker("prefilled_values")
    for k, v in marker.kwargs.items():
        assert cfg_data["prefilled"][k] == v
