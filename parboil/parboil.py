# -*- coding: utf-8 -*-


"""
Parboil lets you generate boilerplate projects from template files.

Run boil --help for more info.
"""

import os
import json
import shutil
from pathlib import Path

import click
from colorama import Fore, Back, Style
from jinja2 import Environment, FileSystemLoader

from .version import __version__
from .ext import TimeExtension



# Load global config
BOIL_CONFIG = dict(
	TPL_DIR = str(Path.home() / '.config' / 'pylr' / 'templates'),
	trim_content = True,
	keep_empty_files = False,
	sort_prompts = False
)

# Load config
# TODO: use click.get_app_dir to be plattform independent
cfg_file = Path.home() /  '.config' / 'pylr' / 'config.json'
if cfg_file.exists():
	with open(cfg_file) as f:
		config_from_file = json.load(f)
		BOIL_CONFIG = {**BOIL_CONFIG, **config_from_file}


TPL_DIR = Path(BOIL_CONFIG['TPL_DIR'])



# Some helper
def log( msg, echo=True, decor='' ):
	if echo:
		click.echo(f'{decor} {msg}')
	else:
		return f'{decor} {msg}'

def log_info( msg, echo=True ):
	return log(msg, echo=echo, decor=f'[{Fore.BLUE}{Style.BRIGHT}i{Style.RESET_ALL}]')

def log_warn( msg, echo=True ):
	return log(msg, echo=echo, decor=f'[{Fore.YELLOW}{Style.BRIGHT}!{Style.RESET_ALL}]')

def log_error( msg, echo=True ):
	return log(msg, echo=echo, decor=f'[{Fore.RED}{Style.BRIGHT}X{Style.RESET_ALL}]')

def log_success( msg, echo=True ):
	return log(msg, echo=echo, decor=f'[{Fore.GREEN}{Style.BRIGHT}✓{Style.RESET_ALL}]')

def log_line( msg, echo=True ):
	return log(msg, echo=echo, decor='    ')

def log_question( msg, echo=False ):
	return log(msg, echo=echo, decor=f'[{Fore.BLUE}{Style.BRIGHT}?{Style.RESET_ALL}]')


# TODO: Options for debug/verbosity and colors
@click.group()
@click.version_option(version=__version__, prog_name='parboil')
def boil():
	pass



@boil.command()
def list():
	if TPL_DIR.exists():
		folders = [str(p) for p in TPL_DIR.iterdir()]
		if len(folders) > 0:
			for child in sorted(folders):
				tpl_name = os.path.basename(child)
				click.echo(f'    {Fore.CYAN}{tpl_name}{Style.RESET_ALL}')
		else:
			click.echo(f'[{Fore.YELLOW}!{Style.RESET_ALL}] No templates installed yet.')
	else:
		click.echo(f'[{Fore.YELLOW}!{Style.RESET_ALL}] Template folder does not exist.')



@boil.command()
@click.option('-f', '--force', is_flag=True)
@click.argument('source')
@click.argument('template')
@click.pass_context
def install(ctx, source, template, force):
	# TODO: validate templates!
	# TODO: handle both github urls and local directories
	source_dir = Path(source).resolve()
	project_file = source_dir / 'project.json'
	template_dir = source_dir / 'template'
	tpl_dir = TPL_DIR  / template

	if not source_dir.is_dir():
		ctx.fail(f'[{Fore.RED}!{Style.RESET_ALL}] Source does not exist')

	if not project_file.is_file():
		ctx.fail(f'[{Fore.RED}!{Style.RESET_ALL}] The source directory does not contain a project.json file')

	if not template_dir.is_dir():
		ctx.fail(f'[{Fore.RED}!{Style.RESET_ALL}] The source directory does not contain a template directory')

	if tpl_dir.is_dir():
		rm = force
		if not force:
			rm = click.confirm(f'[{Fore.YELLOW}!{Style.RESET_ALL}] Overwrite existing template named {Fore.CYAN}{template}{Style.RESET_ALL}')
		if rm:
			try:
				shutil.rmtree(str(tpl_dir))
			except:
				click.echo(f'[{Fore.RED}!{Style.RESET_ALL}] Error while removing template {Fore.CYAN}{template}{Style.RESET_ALL}')
				click.echo(f'    You might need to manually delete the template directory at')
				click.echo(f'    {Style.BRIGHT}{tpl_dir}{Style.RESET_ALL}')
				ctx.exit(1)
		else:
			ctx.exit(1)

	try:
		shutil.copytree(source_dir, tpl_dir)
		click.echo(f'[{Fore.GREEN}✓{Style.RESET_ALL}] Installed template {Style.BRIGHT}{template}{Style.RESET_ALL}')
		click.echo(f'    Use with {Fore.MAGENTA}boil use {template}{Style.RESET_ALL}')
	except:
		ctx.fail(f'[{Fore.RED}!{Style.RESET_ALL}] Could not install template {Fore.CYAN}{template}{Style.RESET_ALL}')



@boil.command()
@click.option('-f', '--force', is_flag=True)
@click.argument('template')
def uninstall(force, template):
	tpl_dir = TPL_DIR  / template
	if tpl_dir.is_dir():
		rm = force
		if not force:
			rm = click.confirm(f'[{Fore.YELLOW}!{Style.RESET_ALL}] Do you really want to uninstall template {Fore.CYAN}{template}{Style.RESET_ALL}')
		if rm:
			try:
				shutil.rmtree(str(tpl_dir))
				click.echo(f'[{Fore.GREEN}✓{Style.RESET_ALL}] Removed template {Style.BRIGHT}{template}{Style.RESET_ALL}')
			except:
				click.echo(f'[{Fore.RED}!{Style.RESET_ALL}] Error while uninstalling template {Fore.CYAN}{template}{Style.RESET_ALL}')
				click.echo(f'    You might need to manually delete the template directory at')
				click.echo(f'    {Style.BRIGHT}{tpl_dir}{Style.RESET_ALL}')
	else:
		click.echo(f'[{Fore.YELLOW}!{Style.RESET_ALL}] Template {Fore.CYAN}{template}{Style.RESET_ALL} does not exist')



@boil.command()
@click.option('-o', '--out', help='The output directory.',
		default='.', show_default=True,
		type=click.Path(file_okay=False, dir_okay=True, writable=True))
@click.argument('template')
@click.pass_context
def use(ctx, out, template):
	"""
	Generate a new project from TEMPLATE.
	"""

	# copy global config for this run
	# TODO: Setup before as context?
	local_cfg = {**BOIL_CONFIG}

	# Check teamplate and read configuration
	project = None

	project_file = TPL_DIR  / template / 'project.json'
	if project_file.exists():
		with open(project_file) as f:
			project = json.load(f)
			if '__pylr' in project:
				# Update config with template specific settings
				if 'tpl_dir' in project['__pylr']:
					del project['__pylr']['tpl_dir']
				local_cfg = {**local_cfg, **project['__pylr']}
				del project['__pylr']

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
		log_warn(f'The output directory exists and is not empty.')
		answ = click.prompt(f'Do you want to [{Style.BRIGHT}O{Style.RESET_ALL}]verwrite, [{Style.BRIGHT}M{Style.RESET_ALL}]erge or [{Style.BRIGHT}A{Style.RESET_ALL}]bort [o/m/a]')
		if answ.lower() == 'o':
			shutil.rmtree(out)
			out.mkdir(parents=True, exist_ok=True)
			log_success(f'Cleared {Style.BRIGHT}{out}{Style.RESET_ALL}')
		elif answ.lower() == 'a':
			ctx.abort()
			return
	elif not out.exists():
		out.mkdir(parents=True, exist_ok=True)
		log_success(f'Created {Style.BRIGHT}{out}{Style.RESET_ALL}')


	# Prepare store for variables
	variables = dict()

	# Read user input (if necessary)
	if len(project) > 0:
		prefilled = BOIL_CONFIG['prefilled'] if 'prefilled' in BOIL_CONFIG else dict()
		for key, val in project.items():
			if key in prefilled:
				variables[key] = prefilled[key]
				log_info(f'Used prefilled value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
			else:
				if type(val) == dict:
					# Handle complex field types
					if 'type' in val:
						# File-Select type
						if val['type'] == 'file-select':
							pass
				elif type(val) == type([]): # TODO: Seems wrong as a test for lists?
					if len(val) > 1:
						log_question(f'Chose a value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"', echo=True)
						for n,choice in enumerate(val):
							log_line(f'{Style.BRIGHT}{n+1}{Style.RESET_ALL} -  "{choice}"')
						n = click.prompt(f'    Select from 1..{len(val)}', default=1)
						if n > len(val):
							log_warn(f'{n} is not a valid choice. Using default.')
							n = 1
					else:
						n = 1
					variables[key] = val[n-1]
					variables[f'{key}_index'] = n-1
				elif type(val) is bool:
					if val:
						variables[key] = not click.confirm(log_question(f'Do you want do disable "{Fore.MAGENTA}{key}{Style.RESET_ALL}"'))
					else:
						variables[key] = click.confirm(log_question(f'Do you want do enable "{Fore.MAGENTA}{key}{Style.RESET_ALL}"'))
				else:
					variables[key] = click.prompt(log_question(f'Enter a value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"'), default=val)


	# Setup Jinja2 and render templates
	tpl_root = TPL_DIR / template / 'template'

	jinja = Environment(
		loader=FileSystemLoader(tpl_root),
		extensions=[TimeExtension]
	)

	# TODO: use pathlib
	for root, dirs, files in os.walk(tpl_root):
		root = Path(root).resolve()
		for name in files:
			dirname = os.path.relpath(root, start=tpl_root)
			path = os.path.join(dirname, name)
			#print(f'[{Fore.GREEN}-{Style.RESET_ALL}] Working on {Style.BRIGHT}{path}{Style.RESET_ALL}')

			# Set some dynamic values
			variables['BOIL'] = dict(
				TPLNAME = template,
				RELDIR  = dirname if dirname != '.' else '',
				ABSDIR  = str((out / dirname).resolve()),
				OUTDIR  = str(out.resolve())
			)

			# TODO: Escape vars for safe filenames
			path_render = jinja.from_string(path).render(**variables)
			variables['BOIL']['FILENAME'] = os.path.basename(path_render)

			# Render template
			tpl_render  = jinja.get_template(path).render(**variables)

			if local_cfg['trim_content']:
				tpl_render = tpl_render.strip()

			if local_cfg['keep_empty_files'] or len(tpl_render) > 0:
				if not os.path.exists(out / dirname):
					os.makedirs(out / dirname)

				with open(out / path_render, 'w') as f:
					f.write(tpl_render)
				click.echo(f'[{Fore.GREEN}✓{Style.RESET_ALL}] Created {Style.BRIGHT}{path_render}{Style.RESET_ALL}')
			else:
				click.echo(f'[{Fore.YELLOW}!{Style.RESET_ALL}] Skipped {Style.BRIGHT}{path_render}{Style.RESET_ALL} due to empty content')

	click.echo(f'[{Fore.GREEN}✓{Style.RESET_ALL}] Generated project template "{Fore.CYAN}{template}{Style.RESET_ALL}" in {Style.BRIGHT}{out}{Style.RESET_ALL}')


def handle_file_select( key, descr ):
	"""
	Helper method to handle advanced value type "file-select".
	"""
	# Get field description
	values   = descr.get('value', [])
	default  = descr.get('default', 1)
	filename = descr.get('default', None)

	if values:
		log_question(f'Select a file to include for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"', echo=True)
		for n,choice in enumerate(values):
			log_line(f'{Style.BRIGHT}{n+1}{Style.RESET_ALL} -  "{choice}"')
		n = click.prompt(f'    Select from 1..{len(values)}', default=default)
		return values[n-1]
	else:
		return None
