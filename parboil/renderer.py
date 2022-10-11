# -*- coding: utf-8 -*-
"""
Initialisation of Jinja2 environment and rendering of templates
from files or strings.
"""


import os
import sys
import typing as t
from collections.abc import MutableSequence
from dataclasses import dataclass
from pathlib import Path

import jinja2_ansible_filters
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader, Template
from jinja2.sandbox import SandboxedEnvironment
from rich import inspect

from .ext import jinja_filter_fileify, jinja_filter_roman, jinja_filter_slugify

if t.TYPE_CHECKING:
    from parboil.project import Project


class ParboilRenderable(t.Protocol):
    def __templates__(self) -> t.Generator[str, str, None]:
        ...


class ParboilRenderer:
    __slots__ = ["_project", "_env", "_environ", "_context"]

    def __init__(self, project: "Project", context: dict = dict()):
        self._project = project
        self._env = None  # type: t.Optional[Environment]
        self._environ = os.environ.copy()
        self._context = context

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
                extensions=[jinja2_ansible_filters.AnsibleCoreFiltersExtension],
            )
            self._env.filters["fileify"] = jinja_filter_fileify
            self._env.filters["slugify"] = jinja_filter_slugify
            self._env.filters["roman"] = jinja_filter_roman

        return self._env

    def _render_template(self, template: Template, **kwargs) -> str:
        if "BOIL" not in kwargs:
            kwargs["BOIL"] = dict()
        kwargs["BOIL"]["TPLNAME"] = self._project.name
        kwargs["BOIL"]["RUNTIME"] = sys.executable

        return template.render(
            **self._project.variables, **self._context, **kwargs, ENV=self._environ, PROJECT=self._project
        )

    def render_string(self, template: str, **kwargs) -> str:
        return self._render_template(self.env.from_string(str(template)), **kwargs)

    def render_strings(self, templates: t.MutableSequence[str], **kwargs) -> t.MutableSequence[str]:
        """Render a sequence of string templates in place."""
        for i, tpl in enumerate(templates):
            templates[i] = self.render_string(tpl, **kwargs)
        return templates

    def render_obj(self, renderable: ParboilRenderable, **kwargs):
        templates = renderable.__templates__()
        try:
            # start generator function
            template = next(templates)
            while True:
                rendered = self.render_string(template, **kwargs)
                template = templates.send(rendered)
        except StopIteration:
            templates.close()

    def render_file(
        self, file: t.Union[str, Path], render_file: bool = False, **kwargs
    ) -> str:
        """Renders a file as jinja2 tempalte and stores the output in another file."""
        if render_file:
            file = self.render_string(str(file), **kwargs)
        else:
            file = str(file)

        return self._render_template(self.env.get_template(file))


def renderable(cls=None, /, *, attr='__templates__'):
    def wrapper(cls):
        if not hasattr(cls, attr) or not isinstance(getattr(cls, attr), MutableSequence):
            setattr(cls, attr, list())

        def getter(self, i):
            return getattr(self, attr)[i]
        setattr(cls, '__getitem__', getter)

        def setter(self, i, v):
            getattr(self, attr)[i] = v
        setattr(cls, '__setitem__', setter)

        def unsetter(self, i):
            del getattr(self, attr)[i]
        setattr(cls, '__delitem__', unsetter)

        def length(self):
            return len(getattr(self, attr))
        setattr(cls, '__len__', length)

        def insert(self, i, v):
            getattr(self, attr).insert(i, v)
        setattr(cls, 'insert', insert)

        # Not perfect, because append, ... are not guaranteed to be implemented
        MutableSequence.register(cls)
        return cls

    if cls is None:
        return wrapper
    return wrapper(cls)
