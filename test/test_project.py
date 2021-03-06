# -*- coding: utf-8 -*-

from pathlib import Path

import pytest
from click.testing import CliRunner

from parboil.parboil import boil
from parboil.project import Project


GLOABL_CONFIG = {'TPLDIR': 'test/repo'}

def test_project_files():
	prj = Project('test')
	prj.setup(GLOABL_CONFIG)

	for file in ['rename_me.txt', 'aaa/rename_me.txt']:
		assert Path(file) in prj.templates
	for file in ['a.txt', 'b.txt', 'c.txt']:
		assert Path(file) in prj.includes

	prj.load()
	assert 'files' in prj.config
	assert 'created' in prj.meta
	assert 'source_type' in prj.meta and prj.meta['source_type'] == 'local'
	assert 'Project' in prj.fields and prj.fields['Project'] == 'Test'

def test_project_errors():
	prj = Project('MISSING')
	with pytest.raises(AttributeError) as e:
		prj.setup({})
		assert 'PARBOIL: key TPLDIR is mandatory in config' in e.message

	prj.setup(GLOABL_CONFIG)

	assert not prj.templates
	assert not prj.includes

	with pytest.raises(FileNotFoundError) as e:
		prj.load(GLOABL_CONFIG)
		assert 'PARBOIL: Project file for template MISSING not found.' in e.message
