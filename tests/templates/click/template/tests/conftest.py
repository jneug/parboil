# -*- coding: utf-8 -*-
"""Common fixtures for testing click apps."""

import pytest
from click.testing import CliRunner

from .{{PackageName}} import {{MainName}}


# Uncomment for patching userhome in tests
# @pytest.fixture(autouse=True)
# def mock_home(monkeypatch, tmp_path):
#     """Monkeypatch the user home folder."""
#     home_path = tmp_path.joinpath("home")

#     monkeypatch.setenv("HOME", str(home_path))
#     monkeypatch.setenv("USERPROFILE", str(home_path))
#     monkeypatch.setattr(Path, "home", lambda: home_path)

@pytest.fixture()
def {{MainName}}_runner():
    runner = CliRunner()

    def {{MainName}}_run(*args, **kwargs):
        return runner.invoke({{MainName}}, args, **kwargs)

    return {{MainName}}_run
