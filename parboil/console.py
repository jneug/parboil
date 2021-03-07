# -*- coding: utf-8 -*-

import click
from colorama import Fore, Back, Style


def printd(msg, echo=click.echo, decor=""):
    """Print msg

    Prefix with decor if given and passed to echo or returned if echo==None
    """
    if callable(echo):
        return echo(f"{decor}{msg}")
    else:
        return f"{decor}{msg}"


def info(msg, echo=click.echo):
    return printd(
        msg, echo=echo, decor=f"[{Fore.BLUE}{Style.BRIGHT}i{Style.RESET_ALL}] "
    )


def warn(msg, echo=click.echo):
    return printd(
        msg, echo=echo, decor=f"[{Fore.YELLOW}{Style.BRIGHT}!{Style.RESET_ALL}] "
    )


def error(msg, echo=click.echo):
    return printd(
        msg, echo=echo, decor=f"[{Fore.RED}{Style.BRIGHT}X{Style.RESET_ALL}] "
    )


def success(msg, echo=click.echo):
    return printd(
        msg, echo=echo, decor=f"[{Fore.GREEN}{Style.BRIGHT}✓{Style.RESET_ALL}] "
    )


def indent(msg, echo=click.echo):
    return printd(msg, echo=echo, decor="    ")


def question(msg, default=None, echo=click.prompt, color=Fore.BLUE):
    msg = printd(msg, echo=None, decor=f"[{color}{Style.BRIGHT}?{Style.RESET_ALL}] ")
    if default:
        return echo(msg, default=default)
    else:
        return echo(msg)
