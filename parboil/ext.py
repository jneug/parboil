# -*- coding: utf-8 -*-

from datetime import datetime
from functools import update_wrapper

from click import pass_context

from jinja2 import nodes
from jinja2.ext import Extension


def pass_tpldir(f):
	@pass_context
	def new_func(ctx, *args, **kwargs):
		if ctx.obj and 'TPLDIR' in ctx.obj:
			return ctx.invoke(f, ctx.obj['TPLDIR'], *args, **kwargs)
		else:
			return ctx.invoke(f, ctx.obj['TPLDIR'], *args, **kwargs)
	return update_wrapper(new_func, f)


class JinjaTimeExtension(Extension):
	"""
	Adds a {% time %} tag to jinja2

	The argument gets passed to time.strftime.
	"""
	tags = {"time"}

	def __init__(self, environment):
		super(JinjaTimeExtension, self).__init__(environment)

		environment.extend(datetime_format='%Y-%m-%d')

	def _time(self, datetime_format):
		if datetime_format is None:
			datetime_format = self.environment.datetime_format

		return datetime.now().strftime(datetime_format)


	def parse(self, parser):
		lineno = next(parser.stream).lineno

		arg = parser.parse_expression()

		call_method = self.call_method(
        '_time',
        [arg],
        lineno=lineno,
    )

		return nodes.Output([call_method], lineno=lineno)
