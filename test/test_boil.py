from click.testing import CliRunner
from parboil.parboil import boil
from parboil.version import __version__

def test_boil():
	runner = CliRunner()
	result = runner.invoke(boil)
	assert result.exit_code == 0

	# Version information
	result = runner.invoke(boil, ['--version'])
	assert result.exit_code == 0
	assert __version__ in result.output

	# Unknwon command
	result = runner.invoke(boil, ['unknown-command'])
	assert result.exit_code == 2
	assert 'No such command \'unknown-command\''

	# Missing command
	result = runner.invoke(boil, ['--tpldir', 'SOME/DIR'])
	assert result.exit_code == 2
	assert 'Missing command' in result.output
