# -*- coding: utf-8 -*-

from pathlib import Path

import pytest

from parboil.project import Project, Repository

TPLDIR = 'test/repo'

def test_repo():
	repo = Repository(TPLDIR)
	assert str(repo.root) == TPLDIR

	for tpl in repo:
		assert tpl in ['pbt', 'test']

	for tpl in repo.projects():
		assert type(tpl) is Project
		assert tpl.name in ['pbt', 'test']
