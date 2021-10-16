# -*- coding: utf-8 -*-

import shutil

from click.testing import CliRunner
from parboil.parboil import boil


def test_boil_list(boil_runner):
    # help message
    result = boil_runner.invoke(boil, ["list", "--help"])
    assert result.exit_code == 0
    assert "Usage: boil list [OPTIONS]" in result.output


def test_boil_list_config(boil_runner, repo_path, tpl_path, config_file):
    runner = CliRunner()

    # Install necessary templates
    result = boil_runner.invoke(boil, ["install", f"{tpl_path}/test"])
    assert result.exit_code == 0
    result = boil_runner.invoke(boil, ["install", f"{tpl_path}/license"])
    assert result.exit_code == 0

    # normal use
    result = boil_runner.invoke(boil, ["list"])
    assert result.exit_code == 0

    # wrong tpldir
    result = runner.invoke(boil, ["--tpldir", "SOME/UNKNOWN/DIR", "list"])
    assert result.exit_code == 1
    assert "Template folder does not exist." in result.output

    # custom tpldir
    result = runner.invoke(boil, ["--tpldir", str(repo_path), "list"])
    assert result.exit_code == 0
    assert "Listing templates in " + str(repo_path) in result.output
    assert "test" in result.output
    assert "license" in result.output

    # custom tpldir via envvar
    result = runner.invoke(boil, ["list"], env=dict(BOIL_TPLDIR=str(repo_path)))
    assert result.exit_code == 0
    assert "Listing templates in " + str(repo_path) in result.output
    assert "test" in result.output
    assert "license" in result.output

    # missing config file
    result = runner.invoke(boil, ["-c", "SOME/UNKNOWN/FILE.json", "list"])
    assert result.exit_code == 2
    assert "No such file or directory" in result.output

    # custom config file
    result = runner.invoke(boil, ["-c", str(config_file), "list"])
    assert result.exit_code == 0
    assert "Listing templates in " + str(repo_path) in result.output
    assert "test" in result.output
    assert "license" in result.output


def test_boil_list_plain(boil_runner, tpl_path):
    # Install necessary templates
    result = boil_runner.invoke(boil, ["install", f"{tpl_path}/test"])
    assert result.exit_code == 0
    result = boil_runner.invoke(boil, ["install", f"{tpl_path}/license"])
    assert result.exit_code == 0

    result = boil_runner.invoke(boil, ["list", "-p"])
    assert result.exit_code == 0
    assert "license\ntest\n" == result.output
