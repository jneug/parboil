"""Testing the basic boil command"""

from click.testing import CliRunner

from parboil.parboil import boil
from parboil.version import __version__


def test_version():
    assert __version__ == "0.9.2"


def test_boil_version(boil_runner):
    result = boil_runner("--version")
    assert result.exit_code == 0
    assert f"parboil, version {__version__}\n" == result.output


def test_boil_unknown(boil_runner):
    # Unknown command
    result = boil_runner("unknown-command")
    assert result.exit_code == 2
    assert "Error: No such command 'unknown-command'." in result.output

    # Missing command
    result = boil_runner("--tpldir", "SOME/DIR")
    assert result.exit_code == 2
    assert "Error: Missing command." in result.output


def test_boil_help(boil_runner):
    usage_str = "Usage: boil [OPTIONS] COMMAND [ARGS]..."

    # invoking without args should show help
    result = boil_runner()
    assert result.exit_code == 0
    assert result.output.startswith(usage_str)
    assert "Options:" in result.output
    assert "Commands:" in result.output

    # help message
    result = boil_runner("--help")
    assert result.exit_code == 0
    assert result.output.startswith(usage_str)
    assert "Options:" in result.output
    assert "Commands:" in result.output
