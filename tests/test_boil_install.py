import shutil, json
from pathlib import Path
from click.testing import CliRunner
from parboil.parboil import boil
from parboil.project import PRJ_FILE, META_FILE


def test_boil_install(boil_runner):
    # use without args not allowed
    result = boil_runner.invoke(boil, ["install"])
    assert result.exit_code == 2
    assert "Missing argument 'SOURCE'" in result.output

    # help message
    result = boil_runner.invoke(boil, ["install", "--help"])
    assert result.exit_code == 0
    assert "Usage: boil install [OPTIONS] SOURCE [TEMPLATE]" in result.output


def test_boil_install_local(boil_runner, tpl_path):
    """Test install from local filesystem"""
    local_name = "test"
    local_path = (tpl_path / local_name).resolve()
    local_install_path = boil_runner.repo_path / local_name

    install_name = "tpl"
    install_path = boil_runner.repo_path / install_name

    #with boil_runner.isolated_filesystem(tmp_dir=tmp_path):
    # Install with default name
    result = boil_runner.invoke(boil, ["install", str(local_path)])
    assert result.exit_code == 0
    assert f"Installed template {local_name}" in result.output
    assert local_install_path.is_dir()
    assert (local_install_path / PRJ_FILE).is_file()
    assert (local_install_path / META_FILE).is_file()

    with open(local_install_path / META_FILE) as meta:
        first_run = json.load(meta)["created"]

    # Overwrite
    result = boil_runner.invoke(boil, ["install", str(local_path)], input="y")
    assert result.exit_code == 0
    assert f"Overwrite existing template named {local_name}" in result.output
    #assert f"Removed template {local_name}" in result.output
    assert f"Installed template {local_name}" in result.output
    assert local_install_path.is_dir()
    assert (local_install_path / PRJ_FILE).is_file()
    assert (local_install_path / META_FILE).is_file()

    with open(local_install_path / META_FILE) as meta:
        second_run = json.load(meta)["created"]

    # check metadata
    assert first_run < second_run

    # Install and overwrite from name
    result = boil_runner.invoke(boil, ["install", str(local_path), install_name])
    assert result.exit_code == 0
    assert f"Installed template {install_name}" in result.output
    assert install_path.is_dir()
    assert (install_path / PRJ_FILE).is_file()
    assert (install_path / META_FILE).is_file()


def test_boil_install_github(boil_runner):
    install_name = "pbt"
    repo_name = "jneug/parboil-template"
    repo_url = f"https://github.com/{repo_name}"

    install_path = boil_runner.repo_path / install_name

    #with boil_runner.isolated_filesystem(tpl_dir=tmp_path):
    # Install from url
    result = boil_runner.invoke(
        boil, ["install", repo_url, install_name]
    )
    assert result.exit_code == 0
    assert "Installed template pbt" in result.output
    assert install_path.is_dir()
    assert (install_path / PRJ_FILE).is_file()
    assert (install_path / META_FILE).is_file()

    # Install and overwrite from name
    result = boil_runner.invoke(
        boil, ["install", "--force", "-d", repo_name, install_name]
    )
    assert result.exit_code == 0
    #assert "Removed template pbt" in result.output
    assert "Installed template pbt" in result.output
    assert install_path.is_dir()
    assert (install_path / PRJ_FILE).is_file()
    assert (install_path / META_FILE).is_file()
