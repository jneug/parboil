# -*- coding: utf-8 -*-

import shutil, json
from pathlib import Path

import pytest
from click.testing import CliRunner

from parboil.parboil import boil
from parboil.project import Project, ProjectFileNotFoundError, PRJ_FILE, META_FILE


def test_environment(repo_path, tpl_path):
    shutil.copytree(tpl_path, repo_path, dirs_exist_ok=True)

    prj = Project("environ", repo_path)
    prj.setup(load_project=True)

    assert "Project" in prj.fields
