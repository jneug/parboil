# -*- coding: utf-8 -*-

import typing as t

import click
from colorama import Back, Fore, Style


def printd(
    msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = click.echo, decor: str = ""
) -> t.Any:
    """Print msg

    Prefix with decor if given and passed to echo or returned if echo==None
    """
    if callable(echo):
        return echo(f"{decor}{msg}")
    else:
        return f"{decor}{msg}"


def info(msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = click.echo) -> t.Any:
    return printd(
        msg, echo=echo, decor=f"[{Fore.BLUE}{Style.BRIGHT}i{Style.RESET_ALL}] "
    )


def warn(msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = click.echo) -> t.Any:
    return printd(
        msg, echo=echo, decor=f"[{Fore.YELLOW}{Style.BRIGHT}!{Style.RESET_ALL}] "
    )


def error(msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = click.echo) -> t.Any:
    return printd(
        msg, echo=echo, decor=f"[{Fore.RED}{Style.BRIGHT}X{Style.RESET_ALL}] "
    )


def success(msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = click.echo) -> t.Any:
    return printd(
        msg, echo=echo, decor=f"[{Fore.GREEN}{Style.BRIGHT}✓{Style.RESET_ALL}] "
    )


def indent(msg: str, echo: t.Optional[t.Callable[[str], t.Any]] = click.echo) -> t.Any:
    return printd(msg, echo=echo, decor="    ")


def question(
    msg: str,
    default: t.Optional[t.Any] = None,
    echo: t.Callable[..., t.Any] = click.prompt,
    color: t.Optional[int] = Fore.BLUE,
) -> t.Any:
    msg = printd(msg, echo=None, decor=f"[{color}{Style.BRIGHT}?{Style.RESET_ALL}] ")
    if default:
        return echo(msg, default=default)
    else:
        return echo(msg)
