# -*- coding: utf-8 -*-
"""
Initialisation of Jinja2 environment and rendering of templates
from files or strings.
"""


import os
import sys
from collections.abc import MutableSequence
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Protocol, Union

import jinja2_ansible_filters
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader
from jinja2 import Template as JinjaTemplate
from jinja2.sandbox import SandboxedEnvironment
from rich import inspect

from .ext import jinja_filter_fileify, jinja_filter_roman, jinja_filter_slugify

if TYPE_CHECKING:
    from parboil.recipe import Boiler


class ParboilRenderable(Protocol):
    """Protocol for classes that can be rendered by [parboil.renderer.ParboilRenderer.render_obj()][]."""

    def __templates__(self) -> Generator[str, str, None]:
        ...


def renderable(cls=None, *attrs, strict: bool = True, render_empty: bool = False):
    """Decorator to make a class a ParboilRenderable."""

    def wrapper(cls):
        if not hasattr(cls, "__templates__"):

            def _render(self) -> Generator[str, str, None]:
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

            setattr(cls, "__templates__", _render)
        return cls

    if cls is None:
        return wrapper
    return wrapper(cls)


# TODO Exception handling
class ParboilRenderer:
    def __init__(self, boiler: "Boiler"):
        self._boiler = boiler
        self._environ = os.environ.copy()

    @cached_property
    def env(self) -> Environment:
        """Creates a jinja Environment for this project and caches it"""
        env = SandboxedEnvironment(
            loader=ChoiceLoader(
                [
                    FileSystemLoader(self._boiler.recipe.templates_dir),
                    PrefixLoader(
                        {
                            "includes": FileSystemLoader(
                                self._boiler.recipe.includes_dir
                            )
                        },
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
        kwargs["BOIL"]["TPLNAME"] = self._boiler.recipe.name
        kwargs["BOIL"]["RUNTIME"] = sys.executable

        return template.render(
            **self._boiler.context,
            **kwargs,
            ENV=self._environ,
            BOILER=self._boiler,
            RECIPE=self._boiler.recipe
        )

    def render_string(self, template: str, **kwargs) -> str:
        return self._render_template(self.env.from_string(str(template)), **kwargs)

    def render_strings(
        self, templates: MutableSequence[str], **kwargs
    ) -> MutableSequence[str]:
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
        self, filename: Union[str, Path], render_filename: bool = False, **kwargs
    ) -> str:
        """Renders a file as jinja2 template.

        If `render_filename`is `True`, the `filename` will be rendered with `render_string` first, before attempting to load the template file."""
        if render_filename:
            filename = self.render_string(str(filename), **kwargs)
        else:
            filename = str(filename)

        return self._render_template(self.env.get_template(filename))
