# -*- coding: utf-8 -*-
"""Unified output (and input) helpers."""


import typing as t

import click
import rich
from rich.prompt import (
    Prompt,
    PromptBase,
    IntPrompt,
    FloatPrompt,
    Confirm,
    PromptType,
    DefaultType,
)
from rich.console import Console
from rich.style import Style
from rich.theme import Theme


THEME = Theme(
    {
        "info.label": "bright_cyan bold",
        "info": "default",
        "error.label": "bright_red bold",
        "error": "red",
        "success.label": "bright_green bold",
        "success": "default",
        "question.label": "bright_blue bold",
        "question": "default",
        "project": "bright_magenta",
        "field": "indian_red bold",
        "path": "cyan italic",
        "keyword": "magenta bold",
        "input": "dark_orange",
        "cmd": "indian_red1 italic",
        "prompt.default": "indian_red",
    }
)


out = Console(theme=THEME)


def style(msg: str, highlight: str) -> str:
    return f"[{highlight}]{msg}[/{highlight}]"


def style_decoration(decor_type: str) -> str:
    return style(f"{decor_type.upper():>10}", f"{decor_type}.label")


def decoration(text: str, decor: str) -> str:
    return f"[white bold]\[[{decor}.label]i[/{decor}.label]][/]"


def printd(
    msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = out.print, decor: str = ""
) -> t.Any:
    """Print msg

    Prefix with decor if given and passed to echo or returned if echo==None
    """
    fmsg = f"{decor}  {msg}"
    if callable(echo):
        return echo(fmsg)
    else:
        return fmsg


def message(
    decor_type: str, msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = out.print
) -> t.Any:
    return printd(style(msg, decor_type), echo=echo, decor=style_decoration(decor_type))


def info(msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = out.print) -> t.Any:
    msg = f"\[[info.label]i[/]] [info]{msg}[/]"
    out.print(msg)


def warn(msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = out.print) -> t.Any:
    return printd(msg, echo=echo, decor="\[[warn.label]![/warn.label]]")


def error(msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = out.print) -> t.Any:
    msg = f"\[[error.label]X[/]] [error]{msg}[/]"
    out.print(msg)


def success(msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = out.print) -> t.Any:
    msg = f"\[[success.label]:heavy_check_mark:[/]] [success]{msg}[/]"
    out.print(msg)


def indent(msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = out.print) -> t.Any:
    return printd(msg, echo=echo, decor="    ")


def prompt(
    type: t.Type[PromptType],
    msg: t.Union[str, t.List[str]],
    default: t.Any = ...,
    secret: bool = False,
) -> PromptType:
    """Shows a prompt to the user and returns the next input."""
    if isinstance(msg, str):
        msg = msg.split("\n")
    else:
        msg = msg.copy()
    msg[0] = f"\[[question.label]?[/]] [question]{msg[0]}[/]"
    msg[1:] = map(lambda _msg: f"    [question]{_msg}[/]", msg[1:])
    for _msg in msg[:-1]:
        out.print(_msg)

    if type is int:
        return IntPrompt(msg[-1], console=out, password=secret)(default=default)  # type: ignore
    elif type is float:
        return FloatPrompt(msg[-1], console=out, password=secret)(default=default)  # type: ignore
    elif type is bool:
        return Confirm(msg[-1], console=out, password=secret)(default=default)  # type: ignore
    else:
        return Prompt(msg[-1], console=out, password=secret)(default=default)  # type: ignore


def question(msg: t.Union[str, t.List[str]], key: str, default: t.Any = ...) -> str:
    if isinstance(msg, str):
        msg = msg.split("\n")
    msg.append(f"[field]{key}[/field]")

    return prompt(str, msg, default=default)


def question_int(msg: t.Union[str, t.List[str]], key: str, default: t.Any = ...) -> int:
    if isinstance(msg, str):
        msg = msg.split("\n")
    msg.append(f"[field]{key}[/field]")

    return prompt(int, msg, default=default)


def confirm(msg: t.Union[str, t.List[str]], default: t.Any = ...) -> bool:
    return prompt(bool, msg, default=default)


def choice(
    msg: t.Union[str, t.List[str]],
    choices: t.Sequence[PromptType],
    default: t.Union[PromptType, int, None] = None,
) -> t.Tuple[int, PromptType]:
    if isinstance(msg, str):
        msg = msg.split("\n")
    for i, text in enumerate(choices):
        msg.append(f"[input]{i+1}[/] - [keyword]{text}[/]")
    msg.append(f"Select from [input]1..{len(choices)}[/]")

    # get correct index for default answer
    if isinstance(default, str):
        try:
            i = choices.index(default)
        except ValueError:
            default = None
        else:
            default = i + 1
    elif isinstance(default, int) and not (0 <= default < len(choices)):
        default = None

    while True:
        answer = prompt(int, msg, default=default or ...)
        if not (0 <= (answer - 1) < len(choices)):
            warn(
                f"{answer} is not a valid choice. Please select from range [input]1..{len(choices)}[/]."
            )
        else:
            return answer, choices[answer - 1]


def clear():
    out.clear()


def sep():
    out.print("=" * out.size.width, style="gray66")
