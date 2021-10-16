# -*- coding: utf-8 -*-

from pathlib import Path

import pytest

from parboil.project import Project, ProjectFileNotFoundError


def test_project_files(tpl_path):


    prj = Project("test", tpl_path)
    prj.setup()

    for file in ["rename_and_move_me.txt", "subfolder/rename_me.txt"]:
        assert Path(file) in prj.templates
    for file in ["a.txt", "b.txt", "c.txt"]:
        assert Path(file) in prj.includes

    prj.load()
    for file in ["rename_and_move_me.txt", "subfolder/rename_me.txt"]:
        assert file in prj.files
    # assert 'created' in prj.meta
    # assert 'source_type' in prj.meta and prj.meta['source_type'] == 'local'
    assert "Project" in prj.fields
    assert "default" in prj.fields["Project"]
    assert prj.fields["Project"]["default"] == "Test"


def test_project_errors(repo_path):
    prj = Project("_MISSING_", repo_path)
    prj.setup()

    assert not prj.templates
    assert not prj.includes

    with pytest.raises(ProjectFileNotFoundError) as e:
        prj.load()
        assert "Project file not found." in e.message
