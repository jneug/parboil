# -*- coding: utf-8 -*-

import sys
import typing as t
from collections.abc import MutableMapping
from dataclasses import dataclass, field

import click
import rich
import rich.prompt
from colorama import Back, Fore, Style
from rich import inspect

import parboil.console as console
from .errors import ProjectConfigError

if t.TYPE_CHECKING:
    from parboil.project import Template, Project

VTYPE = t.TypeVar("VTYPE")

OptStr = t.Optional[str]
OptVtype = t.Optional[VTYPE]


MSG_DEFAULT = 'Enter a value for "[field]{{FIELDNAME}}[/field]"'
MSG_CHOICE = 'Chose a value for "[field]{{FIELDNAME}}[/field]"'
MSG_DISABLE = 'Do you want do [italic]disable[/] "[field]{{FIELDNAME}}[/field]"'
MSG_ENABLE = 'Do you want do [italic]enable[/] "[field]{{FIELDNAME}}[/field]"'


def create_field(name: str, definition: t.Dict[t.Any, t.Any]) -> "Field":
    global FIELD_TYPES

    # deal with shorthand definition
    if isinstance(definition, list):
        definition = dict(field_type='choice', choices=definition)
    elif not isinstance(definition, dict):
        definition = dict(default=definition)

    ## determine field type
    field_type = definition.get("field_type", "default")
    if "field_type" in definition:
        del definition["field_type"]

    ## Special case subtemplates
    if field_type == 'template':
        definition['template_name'] = definition['template']
        del definition['template']

    # select proper field instance based on default value
    if field_type == "default":
        _d = definition.get("default", None)
        _c = definition.get("choices", None)
        if isinstance(_d, bool):
            field_type = "confirm"
        elif isinstance(_c, list):
            field_type = "choice"
        elif isinstance(_c, dict):
            field_type = "dict"

    # create field instance
    try:
        return FIELD_TYPES[field_type](name, **definition)
    except NameError:
        raise ProjectConfigError(f'Unknown field type {field_type}.')


@dataclass(init=False)
class Field(t.Generic[VTYPE]):
    name: str
    value: OptVtype = None
    default: OptVtype = None
    help: str = MSG_DEFAULT
    condition: OptStr = None
    optional: bool = False

    ## Holds arbitrary arguments passed to __init__
    args: t.Dict[str, t.Any] = field(default_factory=dict)

    type: str = "str"

    def __init__(
        self,
        name: str,
        value: OptVtype = None,
        default: OptVtype = None,
        help: OptStr = None,
        condition: OptStr = None,
        optional: bool = False,
        type: str = "str",
        **kwargs,
    ):
        self.name = name

        self.default = default
        self._value = value
        if help:
            self.help = help
        self.condition = condition
        self.optional = optional

        self.args = dict()
        if kwargs:
            self.args.update(kwargs)

        self.type = type

    def __templates__(self) -> t.Generator[str, str, None]:
        for key in ["help", "default", "value", "condition"]:
            val = getattr(self, key, None)
            if val is not None and isinstance(val, str):
                setattr(self, key, (yield val))

    def prompt(self, project: "Project") -> OptVtype:
        """
        Prompts the user for an answer and stores the result in self.value.

        If the field already has a value, no prompt is shown. To force a prompt
        call `del field.value` first.
        """
        if not self.value:
            self._prompt(project)
        return self.value

    def _prompt(self, project: "Project") -> None:
        """Actually prompt the user for an answer and store the
        result in `self.value`."""
        self.value = console.question(
            self.help.format(name=self.name),
            key=self.name,
            default=self.default,
        )


class ConfirmField(Field):
    def __init__(self, name, **kwargs):
        if bool(getattr(kwargs, "default", False)):
            self.help = MSG_DISABLE
        else:
            self.help = MSG_ENABLE
        super().__init__(name, **kwargs)

    def _prompt(self, project: "Project") -> None:
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


class ChoiceField(Field):
    _choices: t.List[str] = field(default_factory=list)

    def __init__(self, name, choices: t.List[t.Any], **kwargs):
        self.help = MSG_CHOICE
        self._choices = choices.copy()
        super().__init__(name, **kwargs)

    def __templates__(self) -> t.Generator[str, str, None]:
        super().__templates__()
        for i, choice in enumerate(self.choices):
            self._choices[i] = (yield choice)

    @property
    def choices(self) -> t.List[str]:
        return self._choices

    def _prompt(self, project: "Project") -> None:
        if len(self.choices) > 1:
            index, self.value = console.choice(
                self.help.format(name=self.name),
                choices=self.choices,
                default=self.default,
            )
            project.context[f"{self.name}_index"] = index
        elif len(self.choices) == 1:
            self.value = self.choices[0]
            project.context[f"{self.name}_index"] = 0
        else:
            self.value = None


class FileselectField(ChoiceField):
    def _prompt(self, project: "Project") -> None:
        super()._prompt(project)

        if self.value:
            project.template.templates.append(f"includes:{self.value}")
            # optionally update file config with filename
            if "filename" in self.args:
                file_config = getattr(project.template.files, self.value, dict())
                file_config.update({"filename": self.args["filename"]})
                project.template.files[self.value] = file_config


class ChoiceDictField(ChoiceField):
    _values: t.List[str] = field(default_factory=list)

    def __init__(self, name, choices: t.Dict[t.Any, str], **kwargs):
        self.help = MSG_CHOICE
        self._values = list(choices.values())
        super().__init__(name, choices=list(choices.keys()), **kwargs)

    def __templates__(self) -> t.Generator[str, str, None]:
        super().__templates__()
        for i, val in enumerate(self._values):
            self._values[i] = (yield val)

    def _prompt(self, project: "Project") -> None:
        super()._prompt(project)

        if self.value:
            i = project.context[f"{self.name}_index"]
            project.context[f"{self.name}_key"] = self.value
            self.value = self._values[i]


class ProjectField(Field):
    _template_name: str = ''

    def __init__(self, name, template_name: str, **kwargs):
        self._template_name = template_name
        super().__init__(name, **kwargs)

    def __templates__(self) -> t.Generator[str, str, None]:
        super().__templates__()
        self._template_name = (yield self._template_name)

    @property
    def template_name(self) -> str:
        return self._template_name

    def _prompt(self, project: "Project") -> None:
        console.info(f'Including subproject "[project]{self.template_name}[/]":')

        if project.template.repository:
            subproject = project.template.repository.get_template(self.template_name)
        else:
            try:
                subproject = Template(self.template_name, project.template.root.parent)
            except NameError:
                from .project import Template
                subproject = Template(self.template_name, project.template.root.parent)

        if subproject.is_project:
            subproject.load()
            _project = Project(subproject, project.target_dir, {**project.context})
            _project.fill()
            project.template.templates.append(subproject)
            project.context.maps.append(subproject.context)


FIELD_TYPES = {
    "default": Field,
    "confirm": ConfirmField,
    "choice": ChoiceField,
    "file_select": FileselectField,
    "dict": ChoiceDictField,
    "template": ProjectField
}
