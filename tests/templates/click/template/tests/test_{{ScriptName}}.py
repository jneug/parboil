"""Testing the main script command"""

from click.testing import CliRunner

from .{{PackageName}} import {{MainName}}
from .version import __version__


def test_version():
    assert __version__ == "{{Version}}"


def test_{{ScriptName}}_version({{MainName}}_runner):
    result = {{MainName}}_runner("--version")
    assert result.exit_code == 0
    assert f"{{SkriptName}}, version {__version__}\n" == result.output


def test_{{ScriptName}}_unknown({{MainName}}_runner):
    # Unknown command
    result = {{MainName}}_runner("unknown-command")
    assert result.exit_code == 2
    assert "Error: No such command 'unknown-command'." in result.output

    # Missing command
    result = {{MainName}}_runner("--foo", "bar")
    assert result.exit_code == 2
    assert "Error: Missing command." in result.output


def test_{{ScriptName}}_help({{MainName}}_runner):
    # help message
    result = {{MainName}}_runner("--help")
    assert result.exit_code == 0
