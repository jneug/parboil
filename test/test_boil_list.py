from click.testing import CliRunner
from parboil.parboil import boil

def test_general():
	runner = CliRunner()

	# help message
	result = runner.invoke(boil, ['list', '--help'])
	assert result.exit_code == 0
	assert 'Usage: boil list' in result.output

def test_list_1():
	runner = CliRunner()

	# normal use
	result = runner.invoke(boil, ['list'])
	assert result.exit_code == 0

	# wrong tpldir
	result = runner.invoke(boil, ['--tpldir', 'SOME/UNKNOWN/DIR', 'list'])
	assert result.exit_code == 1
	assert 'Template folder does not exist.' in result.output

	# custom tpldir
	result = runner.invoke(boil, ['--tpldir', 'test/repo', 'list'])
	assert result.exit_code == 0
	assert 'Listing templates in test/repo' in result.output

	# missing config file
	result = runner.invoke(boil, ['-c', 'SOME/UNKNOWN/FILE.json', 'list'])
	assert result.exit_code == 2
	assert 'No such file or directory' in result.output

	# custom config file
	result = runner.invoke(boil, ['-c', 'test/config.json', 'list'])
	assert result.exit_code == 0
	assert 'Listing templates in test/repo' in result.output

