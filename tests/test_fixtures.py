# -*- coding: utf-8 -*-
"""Tests for custom pytest fixtures"""

import os
import json
import time
from pathlib import Path

from parboil.project import META_FILE


def test_fixture_mock_home(tmp_path):
    """
    The home folder is automatically monkeypatched to a temporary location.
    """
    assert Path.home().relative_to(tmp_path) == tmp_path
    assert os.path.expanduser('~') == str(Path.home())
    

def test_fixture_tpl_path(tpl_path):
    """
    Should return a path to the location of the test templates. 
    """
    test_templates = [
        "test",
        "hello_world",
        "license",
        "environ"
        ]
    assert all(tpl_path.joinpath(tpl).is_dir() for tpl in test_templates)
    
    
def test_fixture_mockinstall(mockinstall, tmp_path, tpl_path):
    """
    Test mock installs of templates to a temporary location.
    """
    src_path = tpl_path / "hello_world"
    dest_path = tmp_path / "hw"
    
    
    # Default install
    assert not  dest_path.is_dir()
    mockinstall(src_path, dest_path)
    meta_path = dest_path / META_FILE
    
    assert dest_path.is_dir()
    assert meta_path.is_file()
    meta_data = json.load(meta_path)
    
    assert meta_data['source'] == str(src_path)
    assert meta_data['created'] == 946681200.0
    assert 'updated' not in meta_data
    
    # Custom install
    dest_path = tmp_path / "hw2"
    ctime = time.time() - 3600
    mtime = time.time()
    
    assert not  dest_path.is_dir()
    mockinstall(
        src_path, dest_path
        created = ctime,
        updated = mtime
    )
    meta_path = dest_path / META_FILE
    
    assert dest_path.is_dir()
    assert meta_path.is_file()
    meta_data = json.load(meta_path)
    
    assert meta_data['source'] == str(src_path)
    assert meta_data['created'] == ctime
    assert meta_data['updated'] == mtime
    
    # Symlinked install
    assert not dest_path.is_dir()
    mockinstall(src_path, dest_path, symlink=True)
    meta_path = dest_path / META_FILE
    
    assert dest_path.is_dir()
    assert dest_path.is_symlink()
    assert not meta_path.is_file()
    

def test_fixture_temp_paths(config_path, repo_path, out_path):
    """
    Test if the temporary paths are created and are children to a function scoped temp location. 
    """
    assert not config_path == repo_path
    assert not config_path == out_path
    assert config_path.parent.parent.parent == repo_path.parent
    assert repo_path.parent == out_path.parent


@pytest.mark.repo_path_contents('hello_world', 'test')
der test_fixture_repo_path(repo_path, request):
    marker = request.node.get_closest_marker("repo_path_contents")
    for tpl in marker.args:
        assert repo_path.joinpath(tpl).is_dir()
        assert repo_path.joinpath(tpl, META_FILE).is_file()


@pytest.mark.tpl_repo_contents('license', 'test')
def test_fixture_tpl_repo(tpl_repo, request):
    marker = request.node.get_closest_marker("repo_path_contents")
    for tpl in marker.args:
        assert tpl_repo.joinpath(tpl).is_dir()

              
def test_fixture_tpl_repo2(tpl_repo, request):
    for tpl in ('hello_world', 'test'):
        assert tpl_repo.joinpath(tpl).is_dir()
