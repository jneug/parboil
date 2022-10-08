# -*- coding: utf-8 -*-

import os
import subprocess
import typing as t
from dataclasses import dataclass, field
from collections import ChainMap

from jinja2 import Environment
from rich import inspect

import parboil.console as console


@dataclass
class Task:
    cmd: t.Union[str, t.List[str]]
    env: t.Optional[dict] = None

    _cmd_rendered = None  # type: t.Optional[t.Union[str, t.List[str]]]

    def execute(self) -> bool:
        if self.env:
            environ = ChainMap(self.env, os.environ)
        else:
            environ = ChainMap(os.environ)

        try:
            result = subprocess.run(self.cmd_safe, shell=isinstance(self.cmd, str), check=True, env=environ)
            return result.returncode == 0
        except subprocess.CalledProcessError as cpe:
            console.error(str(cpe))
            return False

    def render(self, jinja: Environment, context: dict = dict()) -> None:
        if isinstance(self.cmd, str):
            tpl = jinja.from_string(self.cmd)
            self._cmd_rendered = tpl.render(**context)  # type: t.Union[str, t.List[str]]
        else:
            _tpls = [jinja.from_string(c) for c in self.cmd]
            self._cmd_rendered = [tpl.render(**context) for tpl in _tpls]

    @property
    def cmd_safe(self) -> t.Union[str, t.List[str]]:
        if self._cmd_rendered:
            return self._cmd_rendered
        else:
            return self.cmd
