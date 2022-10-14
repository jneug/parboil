# -*- coding: utf-8 -*-

import os
import platform
import re
import string
import typing as t
import unicodedata
from datetime import datetime
from functools import update_wrapper

from click import pass_context
from jinja2 import nodes
from jinja2.ext import Environment, Extension
from jinja2.parser import Parser


def pass_tpldir(f: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    @pass_context
    def new_func(ctx, *args, **kwargs):
        if ctx.obj and "TPLDIR" in ctx.obj:
            return ctx.invoke(f, ctx.obj["TPLDIR"], *args, **kwargs)
        else:
            return ctx.invoke(f, ctx.obj["TPLDIR"], *args, **kwargs)

    return update_wrapper(new_func, f)


DEFAULT_REPLACE = dict(ä="ae", ö="oe", ü="ue", ß="ss")


def jinja_filter_fileify(
    s: t.Any,
    sep: str = "_",
    replace: t.Dict[str, str] = DEFAULT_REPLACE,
    char_limit: int = 88,
) -> str:
    """
    Django util.text.get_valid_filename
    """
    # s = str(s).strip().replace(" ", "_")
    # return re.sub(r"(?u)[^-\w.]", "", s)

    # https://gist.github.com/wassname/1393c4a57cfcbf03641dbc31886123b8
    # replace spaces
    s = str(s).strip().replace(" ", sep)
    for k, v in replace.items():
        s = s.replace(k, v)

    # keep only valid ascii chars
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode()

    if "windows" in platform.system().lower():
        if len(s) > 255:
            s, ext = os.path.splitext(s)
            return s[: (char_limit - len(ext))] + ext
    return s


def jinja_filter_slugify(value: t.Any, allow_unicode: bool = False) -> str:
    """
    Django util.text.slugify
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def jinja_filter_roman(value: t.Any) -> str:
    """Convert an integer to a Roman numeral.
    https://www.oreilly.com/library/view/python-cookbook/0596001673/ch03s24.html
    """

    # if not isinstance(value, type(1)):
    if not isinstance(value, int):
        return str(value)
    if not 0 < value < 4000:
        return str(value)
    ints = (1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1)
    nums = ("M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I")
    result = []
    for i in range(len(ints)):
        count = int(value / ints[i])
        result.append(nums[i] * count)
        value -= ints[i] * count
    return "".join(result)
