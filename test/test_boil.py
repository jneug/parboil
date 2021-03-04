from click.testing import CliRunner
from parboil.parboil import boil
from parboil.version import __version__

def test_boil():
	runner = CliRunner()
	result = runner.invoke(boil)
	assert result.exit_code == 0

	result = runner.invoke(boil, ['--version'])
	assert result.exit_code == 0
	assert __version__ in result.output

	result = runner.invoke(boil, ['unknown-command'])
	assert result.exit_code == 2
