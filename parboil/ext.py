# -*- coding: utf-8 -*-

from datetime import datetime

from jinja2 import nodes
from jinja2.ext import Extension

class JinjaTimeExtension(Extension):
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
