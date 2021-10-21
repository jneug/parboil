# -*- coding: utf-8 -*-

import click
from colorama import Back, Fore, Style
import typing as t
from parboil.project import Project

import parboil.console as console


def field_default(
    key: str, project: Project, default: t.Any = "", value: t.Any = None
) -> t.Any:
    if value:
        console.info(f'Used prefilled value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
        return value
    else:
        if type(default) == list:
            return field_choice(key, project, value=value, choices=default)
        elif type(default) is bool:
            if default:
                return not console.question(
                    f'Do you want do disable "{Fore.MAGENTA}{key}{Style.RESET_ALL}"',
                    echo=click.confirm,
                )
            else:
                return console.question(
                    f'Do you want do enable "{Fore.MAGENTA}{key}{Style.RESET_ALL}"',
                    echo=click.confirm,
                )
        else:
            return console.question(
                f'Enter a value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"',
                default=default,
            )


def field_choice(
    key: str,
    project: Project,
    default: int = 1,
    value: t.Optional[int] = None,
    choices: t.List[str] = list(),
) -> t.Any:
    if value and value < len(choices):
        console.info(f'Used prefilled value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
        project.variables[f"{key}_index"] = value
        return choices[value]
    else:
        if len(choices) > 1:
            console.question(
                f'Chose a value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"',
                echo=click.echo,
            )
            for n, choice in enumerate(choices):
                console.indent(f'{Style.BRIGHT}{n+1}{Style.RESET_ALL} -  "{choice}"')
            n = click.prompt(
                console.indent(f"Select from 1..{len(choices)}", echo=None),
                default=default,
            )
            if n > len(choices):
                console.warn(f"{n} is not a valid choice. Using default.")
                n = default
        else:
            n = 1
        project.variables[f"{key}_index"] = n - 1
        return choices[n - 1]


def field_dict(
    key: str,
    project: Project,
    default: int = 1,
    value: t.Optional[t.Union[str, int]] = None,
    choices: t.Dict[str, t.Any] = dict(),
) -> t.Any:
    _keys: t.List[str] = list(choices.keys())
    _keys_len = len(_keys)

    if value and (value in choices or int(value) < _keys_len):
        console.info(f'Used prefilled value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
        project.variables[f"{key}_key"] = value
        if value in choices:
            return choices[str(value)]
        else:
            return choices[_keys[int(value)]]
        return choices[value]
    else:
        if _keys_len > 1:
            console.question(
                f'Chose a value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"',
                echo=click.echo,
            )
            for n, choice in enumerate(_keys):
                console.indent(f'{Style.BRIGHT}{n+1}{Style.RESET_ALL} - "{choice}"')
            n = click.prompt(
                console.indent(f"Select from 1..{_keys_len}", echo=None),
                default=default,
            )
            if n > _keys_len:
                console.warn(f"{n} is not a valid choice. Using default.")
                if default in choices:
                    k = str(default)
                else:
                    k = _keys[int(default)]
        else:
            k = _keys[0]
        project.variables[f"{key}_key"] = k
        return choices[k]


def field_mchoice(
    key: str,
    project: Project,
    default: int = 1,
    value: t.Any = None,
    choices: t.List[str] = list(),
) -> t.Any:
    return value


def field_file_select(
    key: str,
    project: Project,
    default: int = 1,
    value: t.Optional[str] = None,
    choices: t.List[str] = list(),
    filename: t.Optional[str] = None,
) -> t.Any:
    if value and value in choices:
        console.info(f'Used prefilled value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
    else:
        if len(choices) > 1:
            console.question(
                f'Chose a value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"',
                echo=click.echo,
            )
            for n, choice in enumerate(choices):
                console.indent(f'{Style.BRIGHT}{n+1}{Style.RESET_ALL} -  "{choice}"')
            n = click.prompt(
                console.indent(f"Select from 1..{len(choices)}", echo=None),
                default=default,
            )
            if n > len(choices):
                console.warn(f"{n} is not a valid choice. Using default.")
                n = default
            value = choices[n - 1]
        else:
            value = choices[0]

    project.templates.append(f"includes:{value}")
    if filename:
        project.files[value] = {"filename": filename}
    return value
