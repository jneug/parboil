# -*- coding: utf-8 -*-

from pathlib import Path

import pytest

import parboil.parboil
from parboil.parboil import boil
from parboil.project import Project, Repository


def test_symlink(repo_path, tpl_path):
    repo = Repository(repo_path)
    proj = repo.install_from_directory(
        "symlink_test", tpl_path / "hello_world", symlink=True
    )

    assert proj.exists()
    assert proj.is_symlinked()
    assert repo_path.joinpath("symlink_test").is_symlink()
    assert repo.is_installed("symlink_test")
    assert "symlink_test" in repo


def test_boil_install_w_symlink(mocker, boil_runner, tpl_path):
    mocker.patch("parboil.project.Repository.install_from_directory")
    boil_runner("install", str(tpl_path / "hello_world"), "-s")
    Repository.install_from_directory.assert_called_once_with(
        "hello_world",
        str(tpl_path / "hello_world"),
        hard=True,
        is_repo=False,
        symlink=True,
    )


def test_boil_list_w_symlink(monkeypatch, boil_runner, config_path, tpl_path):
    repo = Repository(config_path / "templates")
    proj = repo.install_from_directory(
        "symlink_test", str(tpl_path / "hello_world"), symlink=True
    )

    assert proj.exists()

    result = boil_runner("list")
    assert "| symlink_test* |                        - |                        - |" in result.output
