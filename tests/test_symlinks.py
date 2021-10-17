# -*- coding: utf-8 -*-

from pathlib import Path

import pytest

from parboil.project import Project, ProjectFileNotFoundError

def test_symlink(repo_path, tpl_path):
    repo = Repository(repo_path)
    proj = repo.install_from_directory("symlink_test", tpl_path / "hello_world", symlink=True)
    
    assert proj.exists()
    assert proj.is_symlinked()
    assert repo_path.joinpath("symlink_test").is_symlink()
