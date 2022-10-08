# -*- coding: utf-8 -*-
"""
Initialisation of Jinja2 environment and rendering of templates
from files or strings.
"""

import os
import typing as t
from pathlib import Path

import jinja2_ansible_filters
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader, Template
from jinja2.sandbox import SandboxedEnvironment

from .ext import (
    JinjaTimeExtension,
    jinja_filter_fileify,
    jinja_filter_roman,
    jinja_filter_slugify,
    jinja_filter_time,
)
from .project import Project


class ParboilRenderer:
    __slots__ = ['_project', '_env', '_environ']

    def __init__(self, project: Project):
        self._project = project
        self._env = None  # type: t.Optional[Environment]
        self._environ = os.environ.copy()

    @property
    def env(self) -> Environment:
        """Creates a jinja Environment for this project and caches it"""
        if not self._env:
            self._env = SandboxedEnvironment(
                loader=ChoiceLoader(
                    [
                        FileSystemLoader(self._project.templates_dir),
                        PrefixLoader(
                            {"includes": FileSystemLoader(self._project.includes_dir)},
                            delimiter=":",
                        ),
                    ]
                ),
                extensions=[
                    jinja2_ansible_filters.AnsibleCoreFiltersExtension
                ],
            )
            self._env.filters["fileify"] = jinja_filter_fileify
            self._env.filters["slugify"] = jinja_filter_slugify
            self._env.filters["roman"] = jinja_filter_roman

        return self._env

    def _render_template(self, template: Template, **kwargs) -> str:
        return template.render(
            **kwargs, ENV=self._environ
        )

    def render_string(self, template: str, **kwargs) -> str:
        return self._render_template(self.env.from_string(template))

    def render_file(self, file: t.Union[str, Path], render_file: bool = False, **kwargs) -> str:
        """Renders a file as jinja2 tempalte and stores the output in another file."""
        if render_file:
            file = self.render_string(str(file), **kwargs)
        else:
            file = str(file)

        return self._render_template(self.env.get_template(file))
