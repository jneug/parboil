# -*- coding: utf-8 -*-
"""Main entrypoint for the script."""

import typing as t

import click
import rich

from .console import console


__version__ = "0.1.0"
__cmdname__ = "{{ScriptName}}"


@click.group(__cmdname__)
@click.version_option(version=__version__, prog_name=__cmdname__)
def {{MainName}}() -> None:
    console.print(f"{__cmdname__} {__version__}", style="yellow bold")
