# -*- coding: utf-8 -*-

import click
from colorama import Fore, Back, Style


import parboil.console as console


def field_default(key, project, default="", value=None):
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


def field_choice(key, project, default=1, value=None, choices=list()):
    if value:
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


def field_file_select(
    key, project, default=1, value=None, choices=list(), filename=None
):
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
