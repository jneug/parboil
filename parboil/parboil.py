# -*- coding: utf-8 -*-


"""
Parboil lets you generate boilerplate projects from template files.

Run boil --help for more info.
"""

import json
import os
import re
import shutil
import subprocess
import time
import logging
import platform
from pathlib import Path

import click
from colorama import Back, Fore, Style
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader

import parboil.console as console
from parboil.ext import (
    JinjaTimeExtension,
    jinja_filter_fileify,
    jinja_filter_roman,
    jinja_filter_slugify,
    jinja_filter_time,
    pass_tpldir,
)
from parboil.logging import configure_logging
from parboil.project import (
    Project,
    ProjectError,
    ProjectExistsError,
    ProjectFileNotFoundError,
    Repository,
)
from parboil.version import __version__

# set global defaults
CFG_FILE = "config.json"

CFG_DIR = "~/.config/parboil"


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
@click.option("--debug", is_flag=True)
@click.pass_context
def boil(ctx, config, tpldir, debug):
    ctx.ensure_object(dict)

    # Setup logging
    if debug:
        configure_logging(logging.DEBUG)
    else:
        configure_logging(logging.WARNING)
    logger = logging.getLogger("parboil")

    logger.info(
        "Starting up parboil, version %s (Python %s)",
        __version__,
        platform.python_version(),
    )


    # Set default values
    cfg_dir = Path(CFG_DIR).expanduser()
    ctx.obj["TPLDIR"] = cfg_dir / "templates"

    # Load config file
    if config:
        logger.info("Loading config from %s ...", config)
        user_cfg = json.load(config)
        ctx.obj = {**ctx.obj, **user_cfg}
        logger.info("    config loaded.")
    else:
        cfg_file = cfg_dir / CFG_FILE
        logger.info("Loading user config from %s ...", str(cfg_file))
        if cfg_file.exists():
            with open(cfg_file) as f:
                cmd_cfg = json.load(f)
                ctx.obj = {**ctx.obj, **cmd_cfg}
            logger.info("    config loaded.")

    if tpldir:
        ctx.obj["TPLDIR"] = tpldir
    ctx.obj["TPLDIR"] = Path(ctx.obj["TPLDIR"])
    logger.info("Working with template repository %s", str(ctx.obj["TPLDIR"]))


@boil.command(short_help="List installed templates")
@click.option("-p", "--plain", is_flag=True)
@pass_tpldir
def list(TPLDIR, plain):
    """
    Lists all templates in the current local repository.
    """
    logger = logging.getLogger("parboil")

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

                    name = project.name
                    created = "unknown"
                    updated = "never"
                    if project.is_symlinked():
                        name = project.name + "*"
                        created = "-"
                        updated = "-"
                    else:
                        if "updated" in project.meta:
                            updated = time.ctime(int(project.meta["updated"]))
                        if "created" in project.meta:
                            created = time.ctime(int(project.meta["created"]))

                    console.indent(
                        f"| {Fore.CYAN}{name:<12}{Style.RESET_ALL} | {created:>24} | {updated:>24} |"
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
@click.option("-s", "--symlink", "symlink", is_flag=True)
@click.argument("source")
@click.argument("template", required=False)
@click.pass_context
def install(ctx, source, template, force, download, is_repo, symlink):
    """
    Install a project template named TEMPLATE from SOURCE to the local template repository.

    SOURCE may be a local directory or the url of a GitHub repository. You may also pass in
    the name of a repository in the form user/repo, but need to set the -d flag to indicate
    it isn't a local directory.

    -r indicates that SOURCE is a folder with multiple templates that should be installed.

    Use -s to create symlinks instead of copying the files. (Useful for template development.)
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
                template, source, hard=True, is_repo=is_repo, symlink=symlink
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
        if isinstance(projects, type([])):
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
            except OSError:
                console.error(
                    f"Error while uninstalling template {Fore.CYAN}{template}{Style.RESET_ALL}"
                )
                console.line(
                    "You might need to manually delete the template directory at"
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
@click.option("--dev", is_flag=True)
@click.argument("template")
@click.argument(
    "out", default=".", type=click.Path(file_okay=False, dir_okay=True, writable=True)
)
@click.pass_context
def use(ctx, template, out, hard, value, dev):
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
                f"Skipped {Style.BRIGHT}{file_out}{Style.RESET_ALL} due to empty content"
            )

    console.success(
        f'Generated project template "{Fore.CYAN}{template}{Style.RESET_ALL}" in {Style.BRIGHT}{out}{Style.RESET_ALL}'
    )
