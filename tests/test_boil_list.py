# -*- coding: utf-8 -*-

import shutil

import pytest

from click.testing import CliRunner
from parboil.parboil import boil


def test_boil_list_help(boil_runner):
    # help message
    result = boil_runner("list", "--help")
    assert result.exit_code == 0
    assert result.output.startswith("Usage: boil list [OPTIONS]")


@pytest.mark.repo_path_contents('license', 'test')
def test_boil_list_config(boil_runner, repo_path, tpl_path, config_file):
    # Install necessary templates
    result = boil_runner("install", f"{tpl_path}/test")
    assert result.exit_code == 0
    result = boil_runner("install", f"{tpl_path}/license")
    assert result.exit_code == 0

    # normal use
    result = boil_runner("list")
    assert result.exit_code == 0

    # wrong tpldir
    result = boil_runner("--tpldir", "SOME/UNKNOWN/DIR", "list")
    assert result.exit_code == 1
    assert "Template folder does not exist." in result.output

    # custom tpldir
    result = boil_runner("--tpldir", str(repo_path), "list")
    assert result.exit_code == 0
    assert "Listing templates in " + str(repo_path) in result.output.replace('\n', '')
    assert "test" in result.output
    assert "license" in result.output

    # custom tpldir via envvar
    result = boil_runner("list", env=dict(BOIL_TPLDIR=str(repo_path)))
    assert result.exit_code == 0
    assert "Listing templates in " + str(repo_path) in result.output.replace('\n', '')
    assert "test" in result.output
    assert "license" in result.output

    # missing config file
    result = boil_runner("-c", "SOME/UNKNOWN/FILE.json", "list")
    assert result.exit_code == 2
    assert "No such file or directory" in result.output

    # custom config file
    result = boil_runner("-c", str(config_file), "list")
    assert result.exit_code == 0
    assert "Listing templates in " + str(repo_path) in result.output.replace('\n', '')
    assert "test" in result.output
    assert "license" in result.output


@pytest.mark.repo_path_contents('hello_world', 'test')
def test_boil_list_plain(boil_runner, repo_path):
    result = boil_runner("--tpldir", str(repo_path), "list", "-p")
    assert result.exit_code == 0
    assert "hello_world\ntest\n" == result.output
