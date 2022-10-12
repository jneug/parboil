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
from functools import cached_property

import jinja2_ansible_filters
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader, Template as JinjaTemplate
from jinja2.sandbox import SandboxedEnvironment
from rich import inspect

from .ext import jinja_filter_fileify, jinja_filter_roman, jinja_filter_slugify

if t.TYPE_CHECKING:
    from parboil.project import Project


class ParboilRenderable(t.Protocol):
    """Protocol for classes that can be rendered by ParboilRenderer.render_obj()"""
    def __templates__(self) -> t.Generator[str, str, None]:
        ...


def renderable(cls=None, *attrs, strict: bool = True, render_empty: bool = False):
    """Decorator to make a class a ParboilREnderable."""
    def wrapper(cls):
        if not hasattr(cls, '__templates__'):
            def _render(self) -> t.Generator[str, str, None]:
                for key in attrs:
                    if hasattr(self, key):
                        val = getattr(self, key, None)
                        if isinstance(val, str):
                            setattr(self, key, (yield val))
                        elif not strict:
                            setattr(self, key, (yield str(val)))
                    elif render_empty:
                        # set attr directly to empty string?
                        setattr(self, key, (yield ""))
            setattr(cls, '__templates__', _render)
        return cls

    if cls is None:
        return wrapper
    return wrapper(cls)


# TODO Exception handling
class ParboilRenderer:
    def __init__(self, project: "Project"):
        self._project = project
        self._environ = os.environ.copy()

    @cached_property
    def env(self) -> Environment:
        """Creates a jinja Environment for this project and caches it"""
        env = SandboxedEnvironment(
            loader=ChoiceLoader(
                [
                    FileSystemLoader(self._project.template.templates_dir),
                    PrefixLoader(
                        {"includes": FileSystemLoader(self._project.template.includes_dir)},
                        delimiter=":",
                    ),
                ]
            ),
            extensions=[jinja2_ansible_filters.AnsibleCoreFiltersExtension],
        )
        env.filters["fileify"] = jinja_filter_fileify
        env.filters["slugify"] = jinja_filter_slugify
        env.filters["roman"] = jinja_filter_roman

        return env

    def _render_template(self, template: JinjaTemplate, **kwargs) -> str:
        if "BOIL" not in kwargs:
            kwargs["BOIL"] = dict()
        kwargs["BOIL"]["TPLNAME"] = self._project.template.name
        kwargs["BOIL"]["RUNTIME"] = sys.executable

        return template.render(
            **self._project.context, **kwargs, ENV=self._environ, PROJECT=self._project, TEMPLATE=self._project.template
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
        self, filename: t.Union[str, Path], render_filename: bool = False, **kwargs
    ) -> str:
        """Renders a file as jinja2 template.

        If `render_filename`is `True`, the `filename` will be rendered with `render_string` first, before attempting to load the template file."""
        if render_filename:
            filename = self.render_string(str(filename), **kwargs)
        else:
            filename = str(filename)

        return self._render_template(self.env.get_template(filename))
