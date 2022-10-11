# -*- coding: utf-8 -*-

import sys
import typing as t
from dataclasses import dataclass, field

import click
import rich
import rich.prompt
from colorama import Back, Fore, Style
from rich import inspect

import parboil.console as console

if t.TYPE_CHECKING:
    from parboil.project import Project

VTYPE = t.TypeVar("VTYPE")

OptStr = t.Optional[str]
OptVtype = t.Optional[VTYPE]


MSG_DEFAULT = 'Enter a value for "[field]{name!s}[/field]"'
MSG_CHOICE = 'Chose a value for "[field]{name!s}[/field]"'
MSG_PREFILLED = 'Used prefilled value for "[field]{name!s}[/]"'
MSG_DISABLE = 'Do you want do [italic]disable[/] "[field]{name!s}[/field]"'
MSG_ENABLE = 'Do you want do [italic]enable[/] "[field]{name!s}[/field]"'


def get_field(field_type: str, field_def: t.Dict[str, t.Any]) -> "Field":
    global FIELD_TYPES

    # select proper field instance if not defined in def
    if field_type == "default":
        if "default" in field_def:
            _d = field_def["default"]
            if isinstance(_d, bool):
                field_type = "confirm"
            elif isinstance(_d, list):
                field_type = "choice"

    # create field instance
    return FIELD_TYPES[field_type](**field_def)
    # if field_type == "confirm":
    #     return ConfirmField(**field_def)
    # elif field_type == 'choice':
    #     return ChoiceField(**field_def)
    # else:
    #     return Field(**field_def)


@dataclass(init=False)
class Field(object):
    name: str
    project: "Project"
    type: str = "default"
    default: t.Any = None
    _value: OptVtype = None
    help: str = MSG_DEFAULT
    condition: OptStr = None
    optional: bool = False
    args: t.Dict[str, t.Any] = field(default_factory=dict)
    caster: t.Callable[[t.Any], t.Any] = str

    def __init__(
        self,
        name: str,
        project: "Project",
        type: str = "str",
        default: OptVtype = None,
        value: OptVtype = None,
        help: OptStr = None,
        condition: OptStr = None,
        optional: bool = False,
        args: t.Dict[str, t.Any] = dict(),
        caster: t.Callable[[t.Any], t.Any] = str,
        **kwargs,
    ):
        self.name = name
        self.project = project
        self.type = type
        self.default = default
        self._value = value
        if help:
            self.help = help
        self.condition = condition
        self.optional = optional
        self.args = args.copy()
        if kwargs:
            self.args.update(kwargs)
        self.caster = caster

    def __templates__(self) -> t.Generator[str, str, None]:
        for key in ["help", "default", "value"]:
            val = getattr(self, key, None)
            if val is not None and isinstance(val, str):
                setattr(self, key, (yield val))

    @property
    def value(self):
        if self._value and self.caster:
            return self.caster(self._value)
        return self._value

    @value.setter
    def value(self, new_value: t.Any):
        self._value = new_value

    @value.deleter
    def value(self):
        self._value = None

    def prompt(self) -> None:
        """
        Prompts the user for an answer and stores the result in self.value.

        If the field already has a value, no prompt is shown. To force a prompt
        call `del field.value` first.
        """
        if not self.value:
            self._prompt()
        else:
            console.info(MSG_PREFILLED.format(name=self.name))

    def _prompt(self) -> None:
        self.value = console.question(
            self.help.format(name=self.name),
            key=self.name,
            default=self.default,
        )


@dataclass(init=False)
class ConfirmField(Field):
    def __init__(self, name, **kwargs):
        if bool(getattr(kwargs, "default", False)):
            self.help = MSG_DISABLE
        else:
            self.help = MSG_ENABLE
        super().__init__(name, **kwargs)

    def _prompt(self) -> None:
        if bool(self.default):
            self.value = not console.confirm(
                self.help.format(name=self.name),
                default=True,
            )
        else:
            self.value = console.confirm(
                self.help.format(name=self.name),
                default=False,
            )


@dataclass(init=False)
class ChoiceField(Field):
    choices: t.List[str] = field(default_factory=list)

    def __init__(self, name, choices: t.List[t.Any], **kwargs):
        self.help = MSG_CHOICE
        self.choices = choices.copy()
        super().__init__(name, **kwargs)

    def __templates__(self) -> t.Generator[str, str, None]:
        super().__templates__()
        for i, choice in enumerate(self.choices):
            self.choices[i] = (yield choice)

    def _prompt(self) -> None:
        if len(self.choices) > 1:
            index, self.value = console.choice(
                self.help.format(name=self.name),
                choices=self.choices,
                default=self.default,
            )
            self.project.variables[f"{self.name}_index"] = index
        elif len(self.choices) == 1:
            self.value = self.choices[0]
            self.project.variables[f"{self.name}_index"] = 0
        else:
            self.value = None


@dataclass(init=False)
class FileselectField(ChoiceField):
    def _prompt(self) -> None:
        super()._prompt()

        if self.value:
            self.project.templates.append(f"includes:{self.value}")
            # optionally update file config with filename
            if "filename" in self.args:
                file_config = getattr(self.project.files, self.value, dict())
                file_config.update({"filename": self.args["filename"]})
                self.project.files[self.value] = file_config


@dataclass(init=False)
class ChoiceDictField(ChoiceField):
    values: t.List[str] = field(default_factory=list)

    def __init__(self, name, choices: t.Dict[t.Any, str], **kwargs):
        self.help = MSG_CHOICE
        self.values = list(choices.values())
        super().__init__(name, choices=list(choices.keys()), **kwargs)

    def __templates__(self) -> t.Generator[str, str, None]:
        super().__templates__()
        for i, val in enumerate(self.values):
            self.values[i] = (yield val)

    def _prompt(self) -> None:
        super()._prompt()

        if self.value:
            i = self.project.variables[f"{self.name}_index"]
            self.project.variables[f"{self.name}_key"] = self.value
            self.value = self.values[i]


@dataclass(init=False)
class ProjectField(Field):
    template: str = ''

    def __init__(self, name, template: str, **kwargs):
        self.template = template
        super().__init__(name, **kwargs)

    def __templates__(self) -> t.Generator[str, str, None]:
        super().__templates__()
        self.template = (yield self.template)

    def _prompt(self) -> None:
        console.info(f'Including subproject "[project]{self.template}[/]":')

        # try:
        #     subproject = Project(self.template, self.project.root.parent)
        # except NameError:
        #     from .project import Project
        #     subproject = Project(self.template, self.project.repository)
        if self.project.repository:
            subproject = self.project.repository.get_project(self.template)
        else:
            try:
                subproject = Project(self.template, self.project.root.parent)
            except NameError:
                from .project import Project
                subproject = Project(self.template, self.project.root.parent)
        console.info(f'from [path]{subproject.root}[/]"!')

        if subproject.is_project:
            subproject.setup(load_project=True)
            subproject.fill({**self.project.prefilled, **self.project.variables})
            self.project.templates.append(subproject)


FIELD_TYPES = {
    "default": Field,
    "confirm": ConfirmField,
    "choice": ChoiceField,
    "file_select": FileselectField,
    "dict": ChoiceDictField,
    "project": ProjectField
}
