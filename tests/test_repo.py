# -*- coding: utf-8 -*-

from pathlib import Path

import pytest

from parboil.project import Project, Repository


def test_repo(repo_path):
    repo = Repository(repo_path)
    assert repo.root == repo_path

    for tpl in repo:
        assert tpl in ["license", "test"]

    for tpl in repo.projects():
        assert type(tpl) is Project
        assert tpl.name in ["license", "test"]
