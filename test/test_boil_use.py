from click.testing import CliRunner
from parboil.parboil import boil

def test_boil_use():
	runner = CliRunner()

	# use without args not allowed
	result = runner.invoke(boil, ['use'])
	assert result.exit_code == 2

	# help message
	result = runner.invoke(boil, ['use', '--help'])
	assert result.exit_code == 0
	assert 'Usage: boil use' in result.output
