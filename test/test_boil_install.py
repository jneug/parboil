import shutil, json
from pathlib import Path
from click.testing import CliRunner
from parboil.parboil import boil, PRJ_FILE, META_FILE


TEST_REPO = Path('test/repo')
TEST_OUT  = Path('test/out')
TEST_TPL  = Path('test/templates')


def test_boil_install():
	runner = CliRunner()

	# use without args not allowed
	result = runner.invoke(boil, ['install'])
	assert result.exit_code == 2

	# help message
	result = runner.invoke(boil, ['install', '--help'])
	assert result.exit_code == 0
	assert 'Usage: boil install' in result.output


def test_local():
	"""Test install from local filesystem"""
	runner = CliRunner()

	local_name = 'test'
	local_path = (TEST_TPL / local_name).resolve()
	local_install = Path(local_name)

	install_name = 'tpl'
	install_path = Path(install_name)


	with runner.isolated_filesystem():
		# Install with default name
		result = runner.invoke(boil, ['--tpldir', '.', 'install', str(local_path)])
		assert result.exit_code == 0
		assert f'Installed template {local_name}' in result.output
		assert local_install.is_dir()
		assert (local_install / PRJ_FILE).is_file()
		assert (local_install / META_FILE).is_file()

		with open(local_install / META_FILE) as meta:
			first_run = json.load(meta)['created']

		# Overwrite
		result = runner.invoke(boil, ['--tpldir', '.', 'install', str(local_path)], input="y")
		assert result.exit_code == 0
		assert f'Overwrite existing template named {local_name}' in result.output
		assert f'Removed template {local_name}' in result.output
		assert f'Installed template {local_name}' in result.output
		assert local_install.is_dir()
		assert (local_install / PRJ_FILE).is_file()
		assert (local_install / META_FILE).is_file()

		with open(local_install / META_FILE) as meta:
			second_run = json.load(meta)['created']

		# check metadata
		assert first_run < second_run

		# Install and overwrite from name
		result = runner.invoke(boil, ['--tpldir', '.', 'install', str(local_path), install_name])
		assert result.exit_code == 0
		assert f'Installed template {install_name}' in result.output
		assert install_path.is_dir()
		assert (install_path / PRJ_FILE).is_file()
		assert (install_path / META_FILE).is_file()


def test_github():
	runner = CliRunner()

	install_name = 'pbt'
	repo_name = 'jneug/parboil-template'
	repo_url  = f'https://github.com/{repo_name}'

	install_path = Path(install_name)

	with runner.isolated_filesystem():
		# Install from url
		result = runner.invoke(boil, ['--tpldir', '.', 'install', repo_url, install_name])
		assert result.exit_code == 0
		assert 'Installed template pbt' in result.output
		assert install_path.is_dir()
		assert (install_path / PRJ_FILE).is_file()
		assert (install_path / META_FILE).is_file()

		# Install and overwrite from name
		result = runner.invoke(boil, ['--tpldir', '.', 'install', '--force', '-d', repo_name, install_name])
		assert result.exit_code == 0
		assert 'Removed template pbt' in result.output
		assert 'Installed template pbt' in result.output
		assert install_path.is_dir()
		assert (install_path / PRJ_FILE).is_file()
		assert (install_path / META_FILE).is_file()
