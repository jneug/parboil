# -*- coding: utf-8 -*-

from pathlib import Path

import pytest

from parboil.project import Project, Repository


def test_repo_install_from_directory(repo_path, tpl_path):
    repo = Repository(repo_path)
    proj = repo.install_from_directory(
        "hello_world", tpl_path / "hello_world"
    )[0]

    assert proj.exists()
    assert not proj.is_symlinked()
    assert repo_path.joinpath("hello_world").is_dir()
    assert repo.is_installed("hello_world")
    assert "hello_world" in repo


def test_repo(repo_path):
    repo = Repository(repo_path)
    assert repo.root == repo_path

    for tpl in repo:
        assert tpl in ["license", "test"]

    for tpl in repo.templates():
        assert isinstance(tpl, Project)
        assert tpl.name in ["license", "test"]
