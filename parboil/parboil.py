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

from .version import __version__
from .project import (
    Project,
    Repository,
    ProjectError,
    ProjectFileNotFoundError,
    ProjectExistsError,
)
from .ext import (
    pass_tpldir,
    JinjaTimeExtension,
    jinja_filter_fileify,
    jinja_filter_slugify,
    jinja_filter_roman,
    jinja_filter_time
)


# set global defaults
CFG_FILE = "config.json"

# TODO: use click.get_app_dir to be plattform independent
CFG_DIR = Path.home() / ".config" / "parboil"


# TODO: Options for debug/verbosity and colors
@click.group()
@click.version_option(version=__version__, prog_name="parboil")
@click.option(
    "-c",
    "--config",
    type=click.File(),
    envvar="BOIL_CONFIG",
    help="Provides a different json config file for this run. Read from stdin with -.",
)
@click.option(
    "--tpldir",
    type=click.Path(file_okay=False, dir_okay=True),
    envvar="BOIL_TPLDIR",
    help="Location of the local template repository.",
)
@click.pass_context
def boil(ctx, config, tpldir):
    ctx.ensure_object(dict)

    # Set default values
    ctx.obj["TPLDIR"] = CFG_DIR / "templates"

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
        ctx.obj["TPLDIR"] = tpldir
    ctx.obj["TPLDIR"] = Path(ctx.obj["TPLDIR"])

@boil.command(short_help="List installed templates")
@click.option("-p", "--plain", is_flag=True)
@pass_tpldir
def list(TPLDIR, plain):
    """
    Lists all templates in the current local repository.
    """
    repo = Repository(TPLDIR)
    if repo.exists():
        if len(repo) > 0:
            if plain:
                for project in repo:
                    click.echo(project)
            else:
                console.info(
                    f"Listing templates in {Style.BRIGHT}{TPLDIR}{Style.RESET_ALL}."
                )
                print()
                console.indent(f'⎪ {"name":^12} ⎪ {"created":^24} ⎪ {"updated":^24} ⎪')
                console.indent(f'|{"-"*14}⎪{"-"*26}⎪{"-"*26}|')
                for project in repo.projects():
                    project.setup(load_project=True)

                    meta = dict()
                    if "updated" not in project.meta:
                        meta["updated"] = "never"
                    else:
                        meta["updated"] = time.ctime(int(project.meta["updated"]))
                    if "created" not in project.meta:
                        meta["created"] = "unknown"
                    else:
                        meta["created"] = time.ctime(int(project.meta["created"]))

                    console.indent(
                        f'| {Fore.CYAN}{project.name:<12}{Style.RESET_ALL} | {meta["created"]:>24} | {meta["updated"]:>24} |'
                    )
                print()
        else:
            console.info("No templates installed yet.")
    else:
        console.warn("Template folder does not exist.")
        exit(1)


@boil.command(short_help="Install a new project template")
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Set this flag to overwrite existing templates named TEMPLATE without prompting.",
)
@click.option(
    "-d",
    "--download",
    is_flag=True,
    help="Set this flag if SOURCE is a github repository to download instead of a local directory.",
)
@click.option("-r", "--repo", "is_repo", is_flag=True)
@click.argument("source")
@click.argument("template", required=False)
@click.pass_context
def install(ctx, source, template, force, download, is_repo):
    """
    Install a project template named TEMPLATE from SOURCE to the local template repository.

    SOURCE may be a local directory or the url of a GitHub repository. You may also pass in
    the name of a repository in the form user/repo, but need to set the -d flag to indicate
    it isn't a local directory.
    """
    # TODO: validate templates!
    TPLDIR = ctx.obj["TPLDIR"]
    repo = Repository(TPLDIR)

    # is github url? Than assume -d
    if re.match(r"https?://(www\.)?github\.com", source):
        download = True
    # set missing arguments
    if download:
        if re.match("[A-Za-z_-]+/[A-Za-z_-]+", source):
            source = f"https://github.com/{source}"
        if not template:
            template = source.split("/")[-1]
    else:
        if not template:
            template = Path(source).name

    if not is_repo and not force and repo.is_installed(template):
        if not console.question(
            f"Overwrite existing template named {Fore.CYAN}{template}{Style.RESET_ALL}",
            color=Fore.YELLOW,
            echo=click.confirm,
        ):
            ctx.abort()

    try:
        if download:
            projects = repo.install_from_github(
                template, source, hard=True, is_repo=is_repo
            )
        else:
            projects = repo.install_from_directory(
                template, source, hard=True, is_repo=is_repo
            )
    except ProjectError as fnfe:
        console.error(str(fnfe))
    except FileExistsError as fee:
        console.error(str(fee))
    except shutil.Error:
        console.error(
            f"Could not install template {Fore.CYAN}{template}{Style.RESET_ALL}",
            echo=ctx.fail,
        )
    else:
        if type(projects) is type([]):
            for project in projects:
                console.success(
                    f"Installed template {Style.BRIGHT}{project.name}{Style.RESET_ALL}"
                )
            console.indent(
                f"Use with {Fore.MAGENTA}boil use <template_name>{Style.RESET_ALL}"
            )
        else:
            console.success(
                f"Installed template {Style.BRIGHT}{projects.name}{Style.RESET_ALL}"
            )
            console.indent(
                f"Use with {Fore.MAGENTA}boil use {projects.name}{Style.RESET_ALL}"
            )


@boil.command(short_help="Uninstall an existing template")
@click.option("-f", "--force", is_flag=True)
@click.argument("template")
@pass_tpldir
def uninstall(TPLDIR, force, template):
    repo = Repository(TPLDIR)

    if repo.is_installed(template):
        rm = force
        if not force:
            rm = console.question(
                f"Do you really want to uninstall template {Fore.CYAN}{template}{Style.RESET_ALL}",
                color=Fore.YELLOW,
                echo=click.confirm,
            )
        if rm:
            try:
                repo.uninstall(template)
                console.success(
                    f"Removed template {Style.BRIGHT}{template}{Style.RESET_ALL}"
                )
            except:
                console.error(
                    f"Error while uninstalling template {Fore.CYAN}{template}{Style.RESET_ALL}"
                )
                console.line(
                    f"You might need to manually delete the template directory at"
                )
                console.line(f"{Style.BRIGHT}{repo.root}{Style.RESET_ALL}")
    else:
        console.warn(f"Template {Fore.CYAN}{template}{Style.RESET_ALL} does not exist")


@boil.command(short_help="Update an existing template")
@click.argument("template")
@click.pass_context
def update(ctx, template):
    """
    Update TEMPLATE from the source it was first installed from.
    """
    cfg = ctx.obj

    repo = Repository(cfg["TPLDIR"])

    if not repo.is_installed(template):
        console.error(
            f"Template {Fore.CYAN}{template}{Style.RESET_ALL} does not exist."
        )
        ctx.exit(2)

    project = repo.get_project(template)
    project.setup(load_project=True)
    try:
        project.update()
    except ProjectFileNotFoundError as pe:
        console.error(str(pe))
        console.indent(
            f"To update templates make sure to install with {Fore.MAGENTA}boil install{Style.RESET_ALL}."
        )
        ctx.abort()
    except ProjectError as pe:
        console.error(str(pe))
        ctx.abort()
    else:
        if project.meta["source_type"] == "github":
            console.success(
                f"Updated template {Fore.CYAN}{template}{Style.RESET_ALL} from GitHub."
            )
        else:
            console.success(
                f"Updated template {Fore.CYAN}{template}{Style.RESET_ALL} from local filesystem."
            )


@boil.command(short_help="Use an existing template")
@click.option(
    "--hard",
    is_flag=True,
    help="Force overwrite of existing output directory. If the directory OUT exists and is not empty, it will be deleted and newly created.",
)
@click.option(
    "-v",
    "--value",
    multiple=True,
    nargs=2,
    help="Sets a prefilled value for the template.",
)
@click.argument("template")
@click.argument(
    "out", default=".", type=click.Path(file_okay=False, dir_okay=True, writable=True)
)
@click.pass_context
def use(ctx, template, out, hard, value):
    """
    Generate a new project from TEMPLATE.

    If OUT is given and a directory, the template is created there.
    Otherwise the cwd is used.
    """
    cfg = ctx.obj

    # Check teamplate and read configuration
    project = Project(template, cfg["TPLDIR"])
    try:
        project.setup(load_project=True)
    except FileNotFoundError:
        console.warn(
            f"No valid template found for key {Fore.CYAN}{template}{Style.RESET_ALL}"
        )
        ctx.exit(1)

    # Prepare output directory
    if out == ".":
        out = Path.cwd()
    else:
        out = Path(out)

    if out.exists() and len(os.listdir(out)) > 0:
        # log_warn(f'The output directory exists and is not empty.')
        # answ = log_question(f'Do you want to [{Style.BRIGHT}O{Style.RESET_ALL}]verwrite, [{Style.BRIGHT}M{Style.RESET_ALL}]erge or [{Style.BRIGHT}A{Style.RESET_ALL}]bort [o/m/a]')
        if hard:
            shutil.rmtree(out)
            out.mkdir(parents=True)
            console.success(f"Cleared {Style.BRIGHT}{out}{Style.RESET_ALL}")
    elif not out.exists():
        out.mkdir(parents=True)
        console.success(f"Created {Style.BRIGHT}{out}{Style.RESET_ALL}")

    # Read user input (if necessary)
    if project.fields:
        # Prepare dict for prefilled values
        prefilled = cfg["prefilled"] if "prefilled" in cfg else dict()
        if value:
            for k, v in value:
                prefilled[k] = v

        project.fill(prefilled)

    for success, file_in, file_out in project.compile(out):
        if success:
            console.success(f"Created {Style.BRIGHT}{file_out}{Style.RESET_ALL}")
        else:
            console.warn(
                f"Skipped {Style.BRIGHT}{file_in}{Style.RESET_ALL} due to empty content"
            )

    console.success(
        f'Generated project template "{Fore.CYAN}{template}{Style.RESET_ALL}" in {Style.BRIGHT}{out}{Style.RESET_ALL}'
    )
