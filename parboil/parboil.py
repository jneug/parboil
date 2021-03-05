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

from .version import __version__
from .ext import pass_tpldir, JinjaTimeExtension, jinja_filter_fileify, jinja_filter_slugify


# set global defaults
CFG_FILE  = 'config.json'
PRJ_FILE  = 'project.json'
META_FILE = '.parboil'

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
@pass_tpldir
def list(TPLDIR):
	if TPLDIR.exists():
		log_info(f'Listing templates in {Style.BRIGHT}{TPLDIR}{Style.RESET_ALL}.')
		folders = [str(p) for p in TPLDIR.iterdir()]
		if len(folders) > 0:
			print()
			log_line(f'⎪ {"name":^12} ⎪ {"created":^24} ⎪ {"updated":^24} ⎪')
			log_line(f'|{"-"*14}⎪{"-"*26}⎪{"-"*26}|')
			for child in sorted(folders):
				meta_file = Path(child) / META_FILE

				meta = dict()
				if meta_file.is_file():
					with open(meta_file) as f:
						meta = json.load(f)
				if 'updated' not in meta:
					meta['updated'] = 'never'
				else:
					meta['updated'] = time.ctime(int(meta['updated']))
				if 'created' not in meta:
					meta['created'] = 'unknown'
				else:
					meta['created'] = time.ctime(int(meta['created']))

				tpl_name = os.path.basename(child)
				log_line(f'| {Fore.CYAN}{tpl_name:<12}{Style.RESET_ALL} | {meta["created"]:>24} | {meta["updated"]:>24} |')
			print()
		else:
			log_info('No templates installed yet.')
	else:
		log_warn('Template folder does not exist.')


@boil.command()
@click.option('-f', '--force', is_flag=True,
		help='Set this flag to overwrite existing templates named TEMPLATE without prompting.')
@click.option('-d', '--download', is_flag=True,
		help='Set this flag if SOURCE is a github repository to download instead of a local directory.')
@click.argument('source')
@click.argument('template', required=False)
@pass_tpldir
def install(TPLDIR, source, template, force, download):
	"""
	Install a project template named TEMPLATE from SOURCE to the local template repository.

	SOURCE may be a local directory or the url of a GitHub repository. You may also pass in
	the name of a repository in the form user/repo, but need to set the -d flag to indicate
	it isn't a local directory.
	"""
	# TODO: validate templates!
	# TODO: handle both github urls and local directories

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
	project = None

	project_file = cfg['TPLDIR'] / template / PRJ_FILE
	if project_file.exists():
		with open(project_file) as f:
			project = json.load(f)

	if project is None:
		log_warn(f'No valid template found for key {Fore.CYAN}{template}{Style.RESET_ALL}')
		ctx.exit(1)
		return

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
			log_success(f'Cleared {Style.BRIGHT}{out}{Style.RESET_ALL}')
	elif not out.exists():
		out.mkdir(parents=True)
		log_success(f'Created {Style.BRIGHT}{out}{Style.RESET_ALL}')


	# Prepare store for variables
	if 'fields' not in project:
		project['fields'] = dict()
	if 'files' not in project:
		project['files'] = dict()
	variables = dict()

	# Read user input (if necessary)
	if len(project['fields']) > 0:
		# Prepare dict for prefilled values
		prefilled = cfg['prefilled'] if 'prefilled' in cfg else dict()
		if value:
			for k, v in value:
				prefilled[k] = v

		for key, val in project['fields'].items():
			if key in prefilled:
				variables[key] = prefilled[key]
				log_info(f'Used prefilled value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
			else:
				if type(val) == dict:
					pass
				elif type(val) == type([]): # TODO: Seems wrong as a test for lists?
					if len(val) > 1:
						log_question(f'Chose a value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"', echo=click.echo)
						for n,choice in enumerate(val):
							log_line(f'{Style.BRIGHT}{n+1}{Style.RESET_ALL} -  "{choice}"')
						n = click.prompt(log_line(f'Select from 1..{len(val)}', echo=None), default=1)
						if n > len(val):
							log_warn(f'{n} is not a valid choice. Using default.')
							n = 1
					else:
						n = 1
					variables[key] = val[n-1]
					variables[f'{key}_index'] = n-1
				elif type(val) is bool:
					if val:
						variables[key] = not log_question(f'Do you want do disable "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
					else:
						variables[key] = log_question(f'Do you want do enable "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
				else:
					variables[key] = log_question(f'Enter a value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"', default=val)


	# Setup Jinja2 and render templates
	tpl_root = cfg['TPLDIR'] / template / 'template'
	inc_root = cfg['TPLDIR'] / template / 'includes'

	jinja = Environment(
		#loader=FileSystemLoader([tpl_root, inc_root]),
		loader=ChoiceLoader([
			FileSystemLoader(tpl_root),
			PrefixLoader(
				{'includes': FileSystemLoader(inc_root)},
				delimiter=':'
			)
		]),
		extensions=[JinjaTimeExtension]
	)
	jinja.filters['fileify'] = jinja_filter_fileify
	jinja.filters['slugify'] = jinja_filter_slugify

	# TODO: use pathlib
	for root, dirs, files in os.walk(tpl_root):
		root = Path(root).resolve()
		for name in files:
			dirname  = os.path.relpath(root, start=tpl_root)
			dirname  = '' if dirname == '.' else dirname
			path_in  = os.path.join(dirname, name)
			path_out = path_in
			if path_in in project['files']:
				if type(project['files'][path_in]) is str:
					path_out = os.path.join(dirname, project['files'][path_in])
			#log_info(f'Working on {Style.BRIGHT}{path}{Style.RESET_ALL}')

			# Set some dynamic values
			variables['BOIL'] = dict(
				TPLNAME = template,
				RELDIR  = dirname if dirname != '.' else '',
				ABSDIR  = str((out / dirname).resolve()),
				OUTDIR  = str(out.resolve())
			)

			# TODO: Escape vars for safe filenames
			path_render = jinja.from_string(path_out).render(**variables)
			variables['BOIL']['FILENAME'] = os.path.basename(path_render)
			variables['BOIL']['FILEPATH'] = path_render

			# Render template
			tpl_render  = jinja.get_template(path_in).render(**variables)

			# TODO: How to mark files as "Keep even if empty"?
			if len(tpl_render) > 0:
				if not os.path.exists(out / dirname):
					os.makedirs(out / dirname)

				with open(out / path_render, 'w') as f:
					f.write(tpl_render)
				log_success(f'Created {Style.BRIGHT}{path_render}{Style.RESET_ALL}')
			else:
				log_warn(f'Skipped {Style.BRIGHT}{path_render}{Style.RESET_ALL} due to empty content')

	log_success(f'Generated project template "{Fore.CYAN}{template}{Style.RESET_ALL}" in {Style.BRIGHT}{out}{Style.RESET_ALL}')
