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

	def __init__(self, name, repository):
		self._name = name
		if type(repository) is Repository:
			self._repo = repository
			self._root_dir = (repository.root / self._name).resolve()
		else:
			self._repo = None
			self._root_dir = (Path(repository) / self._name).resolve()

	@property
	def name(self):
		return self._name

	@property
	def root(self):
		return self._root_dir

	def exists(self):
		self._root_dir.is_dir() and (self._root_dir / PRJ_FILE).is_file()

	def setup(self, load_project=False):
		# setup config files and paths
		self.project_file = self._root_dir / PRJ_FILE
		self.meta_file = self._root_dir / META_FILE
		self.templates_dir = self._root_dir / 'template'
		self.includes_dir = self._root_dir / 'includes'


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
			self.load()

	def load(self):
		"""Loads the project file and some metadata"""

		if not self.project_file:
			self.setup()

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

	def save(self):
		"""Saves the current meta file to disk"""
		if self.meta_file:
			with open(self.meta_file, 'w') as f:
				json.dump(self.meta, f)

	def update(self, hard=False):
		"""Update the template from the original source"""
		pass


class Repository(object):

	def __init__(self, root):
		self._root = Path(root)
		self.load()

	@property
	def root(self):
		return self._root

	def exists(self):
		return self._root.is_dir()

	def load(self):
		self._projects = list()
		for child in self._root.iterdir():
			if child.is_dir():
				project_file = child / PRJ_FILE
				if project_file.is_file():
					self._projects.append(child.name)

	def __len__(self):
		return len(self._projects)

	def __iter__(self):
		yield from self._projects

	def is_installed(self, template):
		tpl_dir = self._root / template
		return tpl_dir.is_dir()
		#return Project(template, self).exists()

	def projects(self):
		for prj in self._projects:
			yield Project(prj, self)

	def install_from_directory(self, template, source, hard=False):
		"""IF source contains a valid project template it is installed
		into this local repository and the Project object is returned.
		"""
		# check source directory
		source = Path(source).resolve()

		project_file = source / PRJ_FILE
		template_dir = source / 'template'

		if not source.is_dir():
			raise FileNotFoundError('Source does not exist')

		if not project_file.is_file():
			raise FileNotFoundError(f'The source does not contain a {PRJ_FILE} file')

		if not template_dir.is_dir():
			raise FileNotFoundError('The source does not contain a template directory')

		if self.is_installed(template):
			if not hard:
				raise FileExistsError('The template already exists. Delete first or retry install with hard=True')
			else:
				self.delete(template)

		project = Project(template, self)

		# copy files
		shutil.copytree(source, project.root)

		# create meta file
		project.setup()
		project.meta = {'created': time.time(), 'source_type':'local', 'source': str(source)}
		project.save()

		return project

	def install_from_github(self, template, url, hard=False):
		# check target dir
		if self.is_installed(template):
			if not hard:
				raise FileExistsError('The template already exists. Delete first or retry install with hard=True')
			else:
				self.delete(template)

		project = Project(template, self)

		# do git clone
		# TODO: Does this work on windows?
		git = subprocess.Popen(['git', 'clone', url, str(project.root)])
		git.wait(30)

		# create meta file
		project.setup()
		project.meta = {'created': time.time(), 'source_type':'github', 'source': url}
		project.save()

		return project

	def uninstall(self, template):
		self.delete(template)

	def delete(self, template):
		"""Delete a project template from this repository."""
		tpl_dir = self._root / template
		if tpl_dir.is_dir():
			if tpl_dir.is_symlink():
				tpl_dir.unlink()
			else:
				shutil.rmtree(tpl_dir)
