# -*- coding: utf-8 -*-


"""
Parboil lets you generate boilerplate projects from template files.

Run boil --help for more info.
"""

import os
import re
import subprocess
import json
import shutil
import time
from pathlib import Path

import click
from colorama import Fore, Back, Style
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, PrefixLoader

import parboil.console as console
import parboil.fields as fields

from .version import __version__
from .project import Project, Repository
from .ext import pass_tpldir, JinjaTimeExtension, jinja_filter_fileify, jinja_filter_slugify


# set global defaults
CFG_FILE  = 'config.json'

# TODO: use click.get_app_dir to be plattform independent
CFG_DIR = Path.home() /  '.config' / 'parboil'


# Some helper
def log( msg, echo=click.echo, decor='' ):
	if callable(echo):
		return echo(f'{decor}{msg}')
	else:
		return f'{decor}{msg}'

def log_info( msg, echo=click.echo ):
	return log(msg, echo=echo, decor=f'[{Fore.BLUE}{Style.BRIGHT}i{Style.RESET_ALL}] ')

def log_warn( msg, echo=click.echo ):
	return log(msg, echo=echo, decor=f'[{Fore.YELLOW}{Style.BRIGHT}!{Style.RESET_ALL}] ')

def log_error( msg, echo=click.echo ):
	return log(msg, echo=echo, decor=f'[{Fore.RED}{Style.BRIGHT}X{Style.RESET_ALL}] ')

def log_success( msg, echo=click.echo ):
	return log(msg, echo=echo, decor=f'[{Fore.GREEN}{Style.BRIGHT}✓{Style.RESET_ALL}] ')

def log_line( msg, echo=click.echo ):
	return log(msg, echo=echo, decor='    ')

def log_question( msg, default=None, echo=click.prompt, color=Fore.BLUE ):
	msg = log(msg, echo=None, decor=f'[{color}{Style.BRIGHT}?{Style.RESET_ALL}] ')
	if default:
		return echo(msg, default=default)
	else:
		return echo(msg)


# TODO: Options for debug/verbosity and colors
@click.group()
@click.version_option(version=__version__, prog_name='parboil')
@click.option('-c', '--config', type=click.File(), envvar='BOIL_CONFIG',
		help='Provides a different json config file for this run. Read from stdin with -.')
@click.option('--tpldir', type=click.Path(file_okay=False, dir_okay=True), envvar='BOIL_TPLDIR',
		help='Location of the local template repository.')
@click.pass_context
def boil(ctx, config, tpldir):
	ctx.ensure_object(dict)

	# Set default values
	ctx.obj['TPLDIR'] = CFG_DIR / 'templates'

	# Load config file
	if config:
		user_cfg = json.load(config)
		ctx.obj = {**ctx.obj, **user_cfg}
	else:
		cfg_file = CFG_DIR / CFG_FILE
		if cfg_file.exists():
			with open(cfg_file) as f:
				cmd_cfg = json.load(f)
				ctx.obj = {**ctx.obj, **cmd_cfg}

	if tpldir:
		ctx.obj['TPLDIR'] = tpldir
	ctx.obj['TPLDIR'] = Path(ctx.obj['TPLDIR'])


@boil.command()
@click.option('-p', '--plain', is_flag=True)
@pass_tpldir
def list(TPLDIR, plain):
	repo = Repository(TPLDIR)
	if repo.exists():
		if len(repo) > 0:
			if plain:
				for project in repo:
					click.echo(project)
			else:
				console.info(f'Listing templates in {Style.BRIGHT}{TPLDIR}{Style.RESET_ALL}.')
				print()
				console.indent(f'⎪ {"name":^12} ⎪ {"created":^24} ⎪ {"updated":^24} ⎪')
				console.indent(f'|{"-"*14}⎪{"-"*26}⎪{"-"*26}|')
				for project in repo.projects():
					project.setup(load_project=True)

					meta = dict()
					if 'updated' not in project.meta:
						meta['updated'] = 'never'
					else:
						meta['updated'] = time.ctime(int(project.meta['updated']))
					if 'created' not in project.meta:
						meta['created'] = 'unknown'
					else:
						meta['created'] = time.ctime(int(project.meta['created']))

					console.indent(f'| {Fore.CYAN}{project.name:<12}{Style.RESET_ALL} | {meta["created"]:>24} | {meta["updated"]:>24} |')
				print()
		else:
			console.info('No templates installed yet.')
	else:
		console.warn('Template folder does not exist.')
		exit(1)


@boil.command()
@click.option('-f', '--force', is_flag=True,
		help='Set this flag to overwrite existing templates named TEMPLATE without prompting.')
@click.option('-d', '--download', is_flag=True,
		help='Set this flag if SOURCE is a github repository to download instead of a local directory.')
@click.argument('source')
@click.argument('template', required=False)
@click.pass_context
def install(ctx, source, template, force, download):
	"""
	Install a project template named TEMPLATE from SOURCE to the local template repository.

	SOURCE may be a local directory or the url of a GitHub repository. You may also pass in
	the name of a repository in the form user/repo, but need to set the -d flag to indicate
	it isn't a local directory.
	"""
	# TODO: validate templates!
	# TODO: handle both github urls and local directories
	TPLDIR = ctx.obj['TPLDIR']

	if re.match(r'https?://(www\.)?github\.com', source):
		download = True
	if download:
		# TODO: validate github urls
		if re.match('[A-Za-z_-]+/[A-Za-z_-]+', source):
			source = f'https://github.com/{source}'
		if not template:
			template = source.split('/')[-1]
	else:
		source = Path(source).resolve()
		project_file = source / 'project.json'
		template_dir = source / 'template'

		if not source.is_dir():
			log_error('Source does not exist', echo=ctx.fail)

		if not project_file.is_file():
			log_error('The source directory does not contain a project.json file', echo=ctx.fail)

		if not template_dir.is_dir():
			log_error('The source directory does not contain a template directory', echo=ctx.fail)

		if not template:
			template = source.name

	# Check target dir
	tpl_dir = TPLDIR  / template
	if tpl_dir.is_dir():
		rm = force
		if not force:
			rm = log_question(f'Overwrite existing template named {Fore.CYAN}{template}{Style.RESET_ALL}', color=Fore.YELLOW, echo=click.confirm)
		if rm:
			try:
				shutil.rmtree(str(tpl_dir))
				log_success(f'Removed template {Fore.CYAN}{template}{Style.RESET_ALL}')
			except shutil.Error:
				log_error(f'Error while removing template {Fore.CYAN}{template}{Style.RESET_ALL}')
				log_line('You might need to manually delete the template directory at')
				log_line(f'{Style.BRIGHT}{tpl_dir}{Style.RESET_ALL}')
				ctx.exit(1)
		else:
			ctx.exit(1)

	try:
		meta = {'created': time.time(), 'source': str(source)}
		if download:
			# TODO: Does this work on windows?
			git = subprocess.Popen(['git', 'clone', str(source), str(tpl_dir)])
			git.wait(30)
			meta['source_type'] = 'github'
		else:
			shutil.copytree(source, tpl_dir)
			meta['source_type'] = 'local'
			meta['source'] = str(source.resolve())
		# Create .parboil for later updates
		with open(tpl_dir / META_FILE, 'w') as f:
			json.dump(meta, f)
		log_success(f'Installed template {Style.BRIGHT}{template}{Style.RESET_ALL}')
		log_line(f'Use with {Fore.MAGENTA}boil use {template}{Style.RESET_ALL}')
	except shutil.Error:
		log_error(f'Could not install template {Fore.CYAN}{template}{Style.RESET_ALL}', echo=ctx.fail)


@boil.command()
@click.option('-f', '--force', is_flag=True)
@click.argument('template')
@pass_tpldir
def uninstall(TPLDIR, force, template):
	tpl_dir = TPLDIR  / template
	if tpl_dir.is_dir():
		rm = force
		if not force:
			rm = log_question(f'Do you really want to uninstall template {Fore.CYAN}{template}{Style.RESET_ALL}', color=Fore.YELLOW, echo=click.confirm)
		if rm:
			try:
				shutil.rmtree(str(tpl_dir))
				log_success(f'Removed template {Style.BRIGHT}{template}{Style.RESET_ALL}')
			except:
				log_error(f'Error while uninstalling template {Fore.CYAN}{template}{Style.RESET_ALL}')
				log_line(f'You might need to manually delete the template directory at')
				log_line(f'{Style.BRIGHT}{tpl_dir}{Style.RESET_ALL}')
	else:
		log_warn(f'Template {Fore.CYAN}{template}{Style.RESET_ALL} does not exist')


@boil.command()
@click.argument('template')
@click.pass_context
def update(ctx, template):
	"""
	Update TEMPLATE from the source it was first installed from.
	"""
	cfg = ctx.obj
	tpl_dir = ctx['TPLDIR']  / template
	meta_file = tpl_dir / META_FILE

	if not tpl_dir.is_dir():
		log_error('Template does not exist.', echo=ctx.fail)

	if not meta_file.is_file():
		log_error('Template metafile does not exist. Can\'t read update information.', echo=ctx.fail)

	with open(meta_file) as f:
		meta = json.load(f)

	if meta['source_type'] == 'github':
		git = subprocess.Popen(['git', 'pull', '--rebase'], cwd=tpl_dir)
		git.wait(30)
		log_success(f'Updated template {Fore.CYAN}{template}{Style.RESET_ALL} from GitHub.')
	else:
		shutil.rmtree(tpl_dir)
		shutil.copytree(meta['source'], tpl_dir)
		log_success(f'Updated template {Fore.CYAN}{template}{Style.RESET_ALL} from local filesystem.')
	meta['updated'] = time.time()
	# Create .parboil for later updates
	with open(tpl_dir / '.parboil', 'w') as f:
		json.dump(meta, f)


@boil.command()
@click.option('--hard', is_flag=True,
		help='Force overwrite of existing output directory. If the directory OUT exists and is not empty, it will be deleted and newly created.')
@click.option('-v', '--value', multiple=True, nargs=2,
	  help='Sets a prefilled value for the template.')
@click.argument('template')
@click.argument('out', default='.',
	type=click.Path(file_okay=False, dir_okay=True, writable=True))
@click.pass_context
def use(ctx, template, out, hard, value):
	"""
	Generate a new project from TEMPLATE.

	If OUT is given and a directory, the template is created there.
	Otherwise the cwd is used.
	"""
	cfg = ctx.obj

	# Check teamplate and read configuration
	project = Project(template)
	try:
		project.setup(cfg, load_project=True)
	except FileNotFoundError:
		console.warn(f'No valid template found for key {Fore.CYAN}{template}{Style.RESET_ALL}')
		ctx.exit(1)

	# Prepare output directory
	if out == '.':
		out = Path.cwd()
	else:
		out = Path(out)

	if out.exists() and len(os.listdir(out)) > 0:
		#log_warn(f'The output directory exists and is not empty.')
			#answ = log_question(f'Do you want to [{Style.BRIGHT}O{Style.RESET_ALL}]verwrite, [{Style.BRIGHT}M{Style.RESET_ALL}]erge or [{Style.BRIGHT}A{Style.RESET_ALL}]bort [o/m/a]')
		if hard:
			shutil.rmtree(out)
			out.mkdir(parents=True)
			console.success(f'Cleared {Style.BRIGHT}{out}{Style.RESET_ALL}')
	elif not out.exists():
		out.mkdir(parents=True)
		console.success(f'Created {Style.BRIGHT}{out}{Style.RESET_ALL}')

	# Read user input (if necessary)
	if project.fields:
		# Prepare dict for prefilled values
		prefilled = project.config['prefilled'] if 'prefilled' in project.config else dict()
		if value:
			for k, v in value:
				prefilled[k] = v

		for key, descr in project.fields.items():
			value = None
			if key in prefilled:
				value = prefilled[key]

			if type(descr) is dict and 'type' in descr:
				field_callable = f'field_{descr["type"]}'
				del descr["type"]
				if hasattr(fields, field_callable):
					project.variables[key] = getattr(fields, field_callable)(key=key, **descr, project=project)

	for success, file_in, file_out in project.compile(out):
		if success:
			console.success(f'Created {Style.BRIGHT}{file_out}{Style.RESET_ALL}')
		else:
			console.warn(f'Skipped {Style.BRIGHT}{file_out}{Style.RESET_ALL} due to empty content')

	console.success(f'Generated project template "{Fore.CYAN}{template}{Style.RESET_ALL}" in {Style.BRIGHT}{out}{Style.RESET_ALL}')
