"""Unified output (and input) helpers."""


import textwrap
import typing as t
from functools import partial

import click
import rich
from rich.console import Console
from rich.prompt import (
    Confirm,
    DefaultType,
    FloatPrompt,
    IntPrompt,
    Prompt,
    PromptBase,
    PromptType,
)
from rich.style import Style
from rich.theme import Theme

THEME = Theme(
    {
        # Decorations
        "info.label": "bright_cyan bold",
        "info": "default",
        "error.label": "bright_red bold",
        "error": "red",
        "warn.label": "orange_red1 bold",
        "warn": "orange3",
        "success.label": "bright_green bold",
        "success": "default",
        "question.label": "yellow bold",
        "question": "default",
        # Custom highlight
        "recipe": "bright_magenta",
        "ingredient": "indian_red bold",
        "path": "cyan italic",
        "keyword": "magenta bold",
        "input": "dark_orange",
        "cmd": "indian_red1 italic",
        # Change some default
        "prompt.default": "indian_red",
        "repr.path": "cyan italic",
        "repr.filename": "bright_cyan italic",
    }
)
DECORATIONS = {
    "error": "X",
    "info": "i",
    "question": "?",
    "success": "✓",
    "warn": "!",
}

out = Console(theme=THEME)


def decoration(decor: str) -> str:
    """Creates a decoration for a message shown to the user."""
    # return f"\[[{decor}.label]{DECORATIONS[decor]}[/{decor}.label]]"
    return f"  [{decor}.label]{DECORATIONS[decor]}[/{decor}.label]  "


def clear():
    """Clear the terminal."""
    out.clear()


def sep():
    """Draw a separator with the full width of the terminal."""
    out.print("┄" * out.size.width, style="gray66")


def printd(
    msg: t.Union[str, t.List[str]], decor: str = "info", indent: int = 4
) -> None:
    if isinstance(msg, str):
        msg = msg.split("\n")
    else:
        msg = msg.copy()

    tab = " " * max(0, indent)

    out.print(f"{decoration(decor)} {msg[0]}")
    for line in msg[1:]:
        out.print(f"{tab}{line}")


info = partial(printd, decor="info")
warn = partial(printd, decor="warn")
error = partial(printd, decor="error")
success = partial(printd, decor="success")


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
    msg[0] = f"{decoration('question')} [question]{msg[0]}[/]"
    msg[1:] = map(lambda _msg: f"    [question]{_msg}[/]", msg[1:])
    for _msg in msg[:-1]:
        out.print(_msg)

    if type is int:
        return IntPrompt(msg[-1], console=out, password=secret)(default=default or ...)  # type: ignore
    elif type is float:
        return FloatPrompt(msg[-1], console=out, password=secret)(default=default or ...)  # type: ignore
    elif type is bool:
        return Confirm(msg[-1], console=out, password=secret)(default=default)  # type: ignore
    else:
        return Prompt(msg[-1], console=out, password=secret)(default=default or ...)  # type: ignore


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
    return bool(prompt(bool, msg, default=bool(default)))


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
