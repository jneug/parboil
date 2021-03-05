# -*- coding: utf-8 -*-

import parboil.console as console

import click
from colorama import Fore, Back, Style

def field_default(key, default, project, value=None):
	if value:
		console.info(f'Used prefilled value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
		return value
	else:
		if type(default) == list:
			return field_choice(key, 1, project, value=value, choices=default)
		elif type(default) is bool:
			if default:
				return not console.question(f'Do you want do disable "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
			else:
				return console.question(f'Do you want do enable "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
		else:
			return console.question(f'Enter a value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"', default=default)

def field_choice(key, default, project, value=None, choices=list()):
	if value:
		console.info(f'Used prefilled value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"')
		return choices[value]
	else:
		if len(choices) > 1:
			console.question(f'Chose a value for "{Fore.MAGENTA}{key}{Style.RESET_ALL}"', echo=click.echo)
			for n,choice in enumerate(choices):
				console.indent(f'{Style.BRIGHT}{n+1}{Style.RESET_ALL} -  "{choice}"')
			n = click.prompt(console.indent(f'Select from 1..{len(choices)}', echo=None), default=default)
			if n > len(choices):
				console.warn(f'{n} is not a valid choice. Using default.')
				n = default
		else:
			n = 1
		project.variables[f'{key}_index'] = n-1
		return choices[n-1]
