# -*- coding: utf-8 -*-

import os
import subprocess
import shlex
import typing as t
from dataclasses import dataclass, field
from collections import ChainMap
from collections.abc import MutableSequence

from jinja2 import Environment
from rich.panel import Panel
from rich.live import Live
from rich.text import Text


@dataclass
class Task(MutableSequence):
    cmd: t.Union[str, t.List[str]]
    env: t.Optional[dict] = None
    quiet: bool = False

    _shell: bool = field(default=False, init=False)

    def __post_init__(self):
        # make sure command is a list
        if isinstance(self.cmd, str):
            # self.cmd = shlex.split(self.cmd)
            self._shell = True
            self.cmd = [self.cmd]
        # store original cmd before jinja rendering
        self._cache = self.cmd.copy()

    @classmethod
    def from_dict(self, descr: t.Dict[str, t.Any]) -> "Task":
        for k in list(descr.keys()):
            # everything not in instance variables is removed
            if k not in Task.__dict__["__annotations__"].keys():
                del descr[k]
        return Task(**descr)

    def __templates__(self) -> t.Generator[str, str, None]:
        if isinstance(self.cmd, str):
            self.cmd = (yield self.cmd)
        else:
            for i, c in enumerate(self.cmd):
                self.cmd[i] = yield c

    def __getitem__(self, i):
        return self.cmd[i]

    def __setitem__(self, i, v):
        self.cmd[i] = v

    def insert(self, i, v):
        self.cmd.insert(i, v)

    def __delitem__(self, i):
        del self.cmd[i]

    def __len__(self):
        return len(self.cmd)

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
        return result.returncode == 0

    def quoted(self):
        return " ".join(shlex.quote(c) for c in self.cmd)

    def __str__(self):
        return self.quoted()

    def reset_template(self) -> None:
        self.cmd = self._cache.copy()
