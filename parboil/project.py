# -*- coding: utf-8 -*-

import os
import re
import subprocess
import json
import shutil
import time
from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, PrefixLoader

from .ext import JinjaTimeExtension, jinja_filter_fileify, jinja_filter_slugify


PRJ_FILE  = 'project.json'
META_FILE = '.parboil'


class Project(object):

	def __init__(self, name):
		self._name = name

	@property
	def name(self):
		return self._name

	def setup(self, config, load_project=False):
		if not 'TPLDIR' in config:
			raise AttributeError('PARBOIL: key TPLDIR is mandatory in config')
		self.root_dir = (Path(config['TPLDIR']) / self._name).resolve()

		# setup config files and paths
		self.project_file = self.root_dir / PRJ_FILE
		self.meta_file = self.root_dir / META_FILE
		self.templates_dir = self.root_dir / 'template'
		self.includes_dir = self.root_dir / 'includes'


		self.meta = dict()
		self.config = dict()
		self.fields = dict()
		self.variables = dict()
		self.templates = list()
		self.includes = list()


		self.templates = list()
		for root, dirs, files in os.walk(self.templates_dir):
			root = Path(root).resolve()
			for name in files:
				dirname = root.relative_to(self.templates_dir)
				self.templates.append(dirname / name)

		self.includes = list()
		for root, dirs, files in os.walk(self.includes_dir):
			root = Path(root).resolve()
			for name in files:
				dirname = root.relative_to(self.includes_dir)
				self.includes.append(dirname / name)

		if load_project:
			self.load(config)

	def load(self, config=dict()):
		"""Loads the project file and some metadata"""

		if not self.project_file:
			self.setup(config)

		## project file
		if self.project_file.exists():
			with open(self.project_file) as f:
				self.config = json.load(f)
		else:
			raise FileNotFoundError(
					f'PARBOIL: Project file for template {self._name} not found.'
					 '\n         Requested file: {str(self.project_file)}')

		if 'fields' in self.config:
			for k,v in self.config['fields'].items():
				if type(v) is not dict:
					self.fields[k] = dict(
						type='default', default=v)
				else:
					self.fields[k] = v
			del self.config['fields']

		## metafile
		if self.meta_file.is_file():
			with open(self.meta_file) as f:
				self.meta = {**self.meta, **json.load(f)}

	def compile(self, target_dir, jinja=None):
		if not jinja:
			jinja = Environment(
				loader=ChoiceLoader([
					FileSystemLoader(self.templates_dir),
					PrefixLoader(
						{'includes': FileSystemLoader(self.includes_dir)},
						delimiter=':'
					)
				]),
				extensions=[JinjaTimeExtension]
			)
			jinja.filters['fileify'] = jinja_filter_fileify
			jinja.filters['slugify'] = jinja_filter_slugify

		target_dir = Path(target_dir).resolve()

		result = (list(), list())
		for file_in in self.templates:
			file_out = Path(file_in)
			if str(file_in) in self.config['files']:
				if type(self.config['files'][str(file_in)]) is str:
					file_out = self.config['files'][str(file_in)]

			rel_path = file_in.parent
			abs_path = target_dir / rel_path

			# Set some dynamic values
			boil_vars = dict(
				TPLNAME = self._name,
				RELDIR  = '' if rel_path.name == '' else str(rel_path),
				ABSDIR  = str(abs_path),
				OUTDIR  = str(target_dir)
			)

			path_render = jinja.from_string(str(file_out)).render(**self.variables, BOIL=boil_vars)

			boil_vars['FILENAME'] = Path(path_render).name
			boil_vars['FILEPATH'] = path_render

			# Render template
			tpl_render = jinja.get_template(str(file_in)).render(**self.variables, BOIL=boil_vars)

			path_render_abs = target_dir / path_render
			if len(tpl_render) > 0:
				if not path_render_abs.parent.exists():
					path_render_abs.parent.mkdir(parents=True)

				with open(path_render_abs, 'w') as f:
					f.write(tpl_render)

				yield (True, file_in, path_render)
			else:
				yield (False, file_in, '')
