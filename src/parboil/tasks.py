# -*- coding: utf-8 -*-

import os
import shlex
import subprocess
import typing as t
from dataclasses import dataclass, field

from jinja2 import Environment
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


@dataclass
class Task:
    """Stores and esecutes commands to run before or after compiling a recipe."""

    cmd: t.Union[str, t.List[str]]
    env: t.Optional[dict] = None
    quiet: bool = False

    returncode: int = field(init=False, default=-1)

    _shell: bool = field(default=False, init=False)

    def __post_init__(self):
        # make sure command is a list
        if isinstance(self.cmd, str):
            self._shell = True
            self.cmd = [self.cmd]
            # self.cmd = shlex.split(self.cmd)

    @classmethod
    def from_dict(self, descr: t.Dict[str, t.Any]) -> "Task":
        for k in list(descr.keys()):
            # everything not in instance variables is removed
            if k not in Task.__dict__["__annotations__"].keys():
                del descr[k]
        return Task(**descr)

    def __templates__(self) -> t.Generator[str, str, None]:
        if isinstance(self.cmd, str):
            self.cmd = yield self.cmd
        else:
            for i, c in enumerate(self.cmd):
                self.cmd[i] = yield c

    def execute(self) -> bool:
        if self.env:
            environ = os.environ.copy().update(self.env)
        else:
            environ = os.environ.copy()

        result = subprocess.run(
            self.cmd,
            shell=self._shell,
            # check=True,
            env=environ,
            stdout=subprocess.DEVNULL if self.quiet else None,
            stderr=subprocess.STDOUT,
        )
        self.returncode = result.returncode
        return result.returncode == 0

    def quoted(self):
        return " ".join(shlex.quote(c) for c in self.cmd)

    def __str__(self):
        return self.quoted()
