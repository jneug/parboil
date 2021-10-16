# -*- coding: utf-8 -*-

import shutil
import json
from pathlib import Path


import pytest
from click.testing import CliRunner


@pytest.fixture()
def config_file(tmp_path, repo_path):
    """Create a temporary repository folder"""
    config_file = tmp_path / "config.json"
    if not config_file.is_file():
        config_file.write_text(
            json.dumps(dict(TPLDIR=str(repo_path), prefilled=dict(Name="Clark Kent")))
        )

    return config_file


@pytest.fixture()
def tpl_path(tmp_path):
    """Create a temporary repository folder"""
    tpl_dir = tmp_path / "tmp_templates"
    if not tpl_dir.is_dir():
        # repo_dir.mkdir()
        shutil.copytree("tests/templates", tpl_dir)

    return tpl_dir


@pytest.fixture()
def repo_path(tmp_path):
    """Create a temporary repository folder"""
    repo_dir = tmp_path / "tmp_repository"
    repo_dir.mkdir(exist_ok=True)
    return repo_dir


@pytest.fixture()
def out_path(tmp_path):
    """Create a temporary repository folder"""
    out_dir = tmp_path / "tmp_output"
    out_dir.mkdir(exist_ok=True)

    return out_dir


@pytest.fixture()
def boil_runner(repo_path):
    return BoilRunner(repo_path)


class BoilRunner(CliRunner):
    def __init__(self, repo_path, *args, **kwargs):
        super(BoilRunner, self).__init__(*args, **kwargs)
        self.repo_path = repo_path

    def invoke(
        self,
        cli,
        args=None,
        input=None,
        env=None,
        catch_exceptions=True,
        color=False,
        **extra
    ):
        if not args:
            args = list()
        if type(args) is list and '--tpldir' not in args:
            args = ["--tpldir", str(self.repo_path)] + args
        return super(BoilRunner, self).invoke(
            cli,
            args=args,
            input=input,
            env=env,
            catch_exceptions=catch_exceptions,
            color=color,
            **extra
        )
