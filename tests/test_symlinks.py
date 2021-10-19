# -*- coding: utf-8 -*-

from pathlib import Path

import pytest

import parboil.parboil
from parboil.parboil import boil
from parboil.project import Project, Repository


def test_symlink(repo_path, tpl_path):
    repo = Repository(repo_path)

    # Install as symlink
    proj = repo.install_from_directory(
        "symlink_test", tpl_path / "hello_world", symlink=True
    )

    assert proj.exists()
    assert proj.is_symlinked()
    assert repo_path.joinpath("symlink_test").is_symlink()
    assert repo.is_installed("symlink_test")
    assert "symlink_test" in repo

    # Overwrite without symlink
    proj = repo.install_from_directory(
        "symlink_test", tpl_path / "hello_world", hard=True, symlink=False
    )
    assert proj.exists()
    assert not proj.is_symlinked()
    assert not repo_path.joinpath("symlink_test").is_symlink()

    # Overwrite again with symlink
    proj = repo.install_from_directory(
        "symlink_test", tpl_path / "hello_world", hard=True, symlink=True
    )
    assert proj.exists()
    assert proj.is_symlinked()
    assert repo_path.joinpath("symlink_test").is_symlink()

    # Delete symlink
    repo.uninstall("symlink_test")
    assert not proj.exists()
    assert not repo_path.joinpath("symlink_test").exists()
    assert not repo.is_installed("symlink_test")


def test_boil_install_w_symlink(mocker, boil_runner, tpl_path):
    mocked_ifd = mocker.patch("parboil.project.Repository.install_from_directory")
    # Test install with -s option
    boil_runner("install", str(tpl_path / "hello_world"), "-s")
    mocked_ifd.assert_called_once_with(
        "hello_world",
        str(tpl_path / "hello_world"),
        hard=True,
        is_repo=False,
        symlink=True,
    )

    mocked_ifd.reset_mock()
    # Verify install without -s option working as expected
    boil_runner("install", str(tpl_path / "hello_world"))

    mocked_ifd.assert_called_once_with(
        "hello_world",
        str(tpl_path / "hello_world"),
        hard=True,
        is_repo=False,
        symlink=False,
    )


def test_boil_list_w_symlink(monkeypatch, boil_runner, config_path, tpl_path):
    repo = Repository(config_path / "templates")
    proj = repo.install_from_directory(
        "symlink_test", str(tpl_path / "hello_world"), symlink=True
    )

    assert proj.exists()

    result = boil_runner("list")
    assert "| symlink_test* |                        - |                        - |" in result.output
