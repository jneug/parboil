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
    from parboil.recipes import Boiler, Recipe

VTYPE = t.TypeVar("VTYPE")

OptStr = t.Optional[str]
OptVtype = t.Optional[VTYPE]


MSG_DEFAULT = 'Enter a value for "[ingredient]{{INGREDIENT.name}}[/]"'
MSG_CHOICE = 'Chose a value for "[ingredient]{{INGREDIENT.name}}[/]"'
MSG_DISABLE = 'Do you want do [italic]disable[/] "[ingredient]{{INGREDIENT.name}}[/]"'
MSG_ENABLE = 'Do you want do [italic]enable[/] "[ingredient]{{INGREDIENT.name}}[/]"'
MSG_CONFIRM = 'Do you want do [italic]enable[/] "[ingredient]{{INGREDIENT.name}}[/]"'


def get_ingredient(name: str, definition: t.Dict[t.Any, t.Any]) -> "Ingredient":
    global INGREDIENT_TYPES

    # deal with shorthand definition
    if isinstance(definition, list):
        definition = dict(field_type="choice", choices=definition)
    elif not isinstance(definition, dict):
        definition = dict(default=definition)

    ## determine field type
    field_type = definition.get("field_type", "default")
    if "field_type" in definition:
        del definition["field_type"]

    ## Special case subtemplates
    if field_type == "recipe":
        definition["recipe_name"] = definition["name"]

    # name key is reserved
    if "name" in definition:
        del definition["name"]

    # select proper field instance based on default value
    if field_type == "default":
        _d = definition.get("default", None)
        _c = definition.get("choices", None)
        if isinstance(_d, bool):
            field_type = "confirm"
        if isinstance(_d, int):
            definition["type"] = "int"
        elif isinstance(_c, list):
            field_type = "choice"
        elif isinstance(_c, dict):
            field_type = "dict"

    # create field instance
    try:
        return INGREDIENT_TYPES[field_type](name, **definition)
    except NameError:
        raise ProjectConfigError(f"Unknown field type {field_type}.")


@dataclass(init=False)
class Ingredient(t.Generic[VTYPE]):
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

    def prompt(self, boiler: "Boiler") -> OptVtype:
        """
        Prompts the user for an answer and stores the result in self.value.

        If the field already has a value, no prompt is shown. To force a prompt
        call `del field.value` first.
        """
        if not self.value:
            self._prompt(boiler)
        return self.value

    def _prompt(self, boiler: "Boiler") -> None:
        """Actually prompt the user for an answer and store the
        result in `self.value`."""
        if self.type == "int":
            self.value = console.question_int(
                self.help,
                key=self.name,
                default=self.default,
            )
        else:
            self.value = console.question(
                self.help,
                key=self.name,
                default=self.default,
            )


class ConfirmIngredient(Ingredient):
    def __init__(self, name, **kwargs):
        # if bool(getattr(kwargs, "default", False)):
        #     self.help = MSG_DISABLE
        # else:
        #     self.help = MSG_ENABLE
        self.help = MSG_CONFIRM
        super().__init__(name, **kwargs)

    def _prompt(self, boiler: "Boiler") -> None:
        self.value = console.confirm(
            self.help,
            default=bool(self.default),
        )
        # if bool(self.default):
        #     self.value = not console.confirm(
        #         self.help,
        #         default=True,
        #     )
        # else:
        #     self.value = console.confirm(
        #         self.help,
        #         default=False,
        #     )


class ChoiceIngredient(Ingredient):
    _choices: t.List[str] = field(default_factory=list)

    def __init__(self, name, choices: t.List[t.Any], **kwargs):
        self.help = MSG_CHOICE
        self._choices = choices.copy()
        super().__init__(name, **kwargs)

    def __templates__(self) -> t.Generator[str, str, None]:
        yield from super().__templates__()
        for i, choice in enumerate(self.choices):
            self._choices[i] = yield choice

    @property
    def choices(self) -> t.List[str]:
        return self._choices

    def _prompt(self, boiler: "Boiler") -> None:
        if len(self.choices) > 1:
            index, self.value = console.choice(
                self.help,
                choices=self.choices,
                default=self.default,
            )
            boiler.context[f"{self.name}_index"] = index
        elif len(self.choices) == 1:
            self.value = self.choices[0]
            boiler.context[f"{self.name}_index"] = 0
        else:
            self.value = None


class FileselectIngredient(ChoiceIngredient):
    def _prompt(self, boiler: "Boiler") -> None:
        super()._prompt(boiler)

        if self.value:
            boiler.recipe.templates.append(f"includes:{self.value}")
            # optionally update file config with filename
            if "filename" in self.args:
                file_config = getattr(boiler.recipe.files, self.value, dict())
                file_config.update({"filename": self.args["filename"]})
                boiler.recipe.files[self.value] = file_config


class ChoiceDictIngredient(ChoiceIngredient):
    _values: t.List[str] = field(default_factory=list)

    def __init__(self, name, choices: t.Dict[t.Any, str], **kwargs):
        self.help = MSG_CHOICE
        self._values = list(choices.values())
        super().__init__(name, choices=list(choices.keys()), **kwargs)

    def __templates__(self) -> t.Generator[str, str, None]:
        super().__templates__()
        for i, val in enumerate(self._values):
            self._values[i] = yield val

    def _prompt(self, boiler: "Boiler") -> None:
        super()._prompt(boiler)

        if self.value:
            i = boiler.context[f"{self.name}_index"]
            boiler.context[f"{self.name}_key"] = self.value
            self.value = self._values[i]


class RecipeIngredient(Ingredient):
    _recipe_name: str = ""

    def __init__(self, name, recipe_name: str, **kwargs):
        self._recipe_name = recipe_name
        super().__init__(name, **kwargs)

    def __templates__(self) -> t.Generator[str, str, None]:
        super().__templates__()
        self._recipe_name = yield self._recipe_name

    @property
    def recipe_name(self) -> str:
        return self._recipe_name

    def _prompt(self, boiler: "Boiler") -> None:
        console.info(f'Including subrecipe "[recipe]{self.recipe_name}[/]"')

        if boiler.recipe.repository:
            subrecipe = boiler.recipe.repository.get_recipe(self._recipe_name)
        else:
            try:
                Recipe.__name__
            except NameError:
                from .recipes import Recipe

            subrecipe = Recipe(self._recipe_name, boiler.recipe.root.parent)

        if subrecipe.is_valid():
            prefilled = boiler.prefilled.copy()
            if "pass_context" not in self.args or self.args["pass_context"] is True:
                prefilled.update(boiler.context)

            try:
                Boiler.__name__
            except NameError:
                from .recipes import Boiler

            subrecipe.load()
            subboiler = Boiler(subrecipe, boiler.target_dir, prefilled)
            subboiler.fill()
            boiler.recipe.templates.append(subrecipe)
            boiler.context.maps.append({self.name: subrecipe.context})


INGREDIENT_TYPES = {
    "default": Ingredient,
    "confirm": ConfirmIngredient,
    "choice": ChoiceIngredient,
    "file_select": FileselectIngredient,
    "dict": ChoiceDictIngredient,
    "recipe": RecipeIngredient,
}
