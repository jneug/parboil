# -*- coding: utf-8 -*-


"""
Parboil lets you generate boilerplate projects from template files.

Run boil --help for more info.
"""

import jsonc as json
import os
import re
import shutil
import subprocess
import time
import logging
import platform
import typing as t
from pathlib import Path

import click
from colorama import Back, Fore, Style
import rich
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.syntax import Syntax
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
from parboil.logger import configure_logging
from parboil.project import (
    Template,
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
def boil(
    ctx: click.Context,
    config: t.TextIO,
    tpldir: t.Union[str, Path],
    debug: bool = False,
) -> None:
    ctx.ensure_object(dict)

    # Setup logging
    if debug:
        configure_logging(logging.DEBUG)
    else:
        configure_logging(logging.WARNING)
    logger = logging.getLogger("parboil")

    # console.clear()
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
        try:
            user_cfg = json.load(config)
            ctx.obj = {**ctx.obj, **user_cfg}
            logger.info("Merged in config from `%s`", config)
        except json.JSONDecodeError:
            logger.debug("Error loading config from `%s`", config)
    else:
        cfg_file = cfg_dir / CFG_FILE
        if cfg_file.exists():
            with open(cfg_file) as f:
                try:
                    cmd_cfg = json.load(f)
                    ctx.obj = {**ctx.obj, **cmd_cfg}
                    logger.info("Merged in config from `%s`", str(cfg_file))
                except json.JSONDecodeError:
                    logger.debug("Error loading config from `%s`", str(cfg_file))

    if tpldir:
        ctx.obj["TPLDIR"] = tpldir
    ctx.obj["TPLDIR"] = Path(ctx.obj["TPLDIR"])
    logger.info("Working with template repository `%s`\n", str(ctx.obj["TPLDIR"]))


@boil.command(short_help="List installed templates")
@click.option("-p", "--plain", is_flag=True)
@pass_tpldir
def list(TPLDIR: Path, plain: bool) -> None:
    """
    Lists all templates in the current local repository.
    """
    repo = Repository(TPLDIR)
    if repo.exists():
        if len(repo) > 0:
            if plain:
                for project_name in repo:
                    console.out.print(project_name)
            else:
                table = Table(title=f"Templates installed in [path]{TPLDIR}[/path]", expand=True)

                table.add_column("Name", style="keyword")
                table.add_column("Created / Updated / Path")

                for _template in sorted(repo.templates(), key=lambda t: t.name):
                    _template.load()

                    name = _template.name
                    created = "[white on red]unknown[/]"
                    updated = "[bright_black]never[/]"
                    if _template.is_symlinked():
                        name = f'[cyan]{_template.name}*[/]'
                        data = f"[path]{_template.root}[/]"
                    else:
                        if "updated" in _template.meta:
                            updated = time.ctime(int(_template.meta["updated"]))
                        if "created" in _template.meta:
                            created = time.ctime(int(_template.meta["created"]))
                        data = f"[purple]{created}[/] / [purple]{updated}[/]"

                    table.add_row(name, data)

                console.out.print(table)
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
def install(
    ctx: click.Context,
    source: str,
    template: str,
    force: bool,
    download: bool,
    is_repo: bool,
    symlink: bool,
) -> None:
    """
    Install a project template named TEMPLATE from SOURCE to the local template repository.

    SOURCE may be a local directory or the url of a GitHub repository. You may also pass in
    the name of a repository in the form user/repo, but need to set the -d flag to indicate
    it isn't a local directory.

    -r indicates that SOURCE is a folder with multiple templates that should be installed.

    Use -s to create symlinks instead of copying the files. (Useful for template development.)
    """
    # logger = logging.getLogger("parboil")

    # TODO: validate templates!
    TPLDIR = ctx.obj["TPLDIR"]
    repo = Repository(TPLDIR)

    # is source a github url? Then assume -d
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
        if not console.confirm(
            f"Overwrite existing template named [project]{template}[/]?"
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
            f"Could not install template [project]{template}[/]"
        )
    else:
        if not projects:
            console.success("No templates where installed.")
            return

        for project in projects:
            console.success(
                f"Installed template [project]{project.name}[/]"
            )
        if len(projects) == 1:
            console.printd(
                f"\nUse with [cmd]boil use {projects[0].name}[/]"
            )
        else:
            console.printd(
                "\nUse with [cmd]boil use <template_name>[/]"
            )


@boil.command(short_help="Uninstall an existing template")
@click.option("-f", "--force", is_flag=True)
@click.argument("template")
@pass_tpldir
def uninstall(TPLDIR: Path, force: bool, template: str) -> None:
    repo = Repository(TPLDIR)

    if repo.is_installed(template):
        rm = force
        if not force:
            rm = console.confirm(
                f"Do you really want to uninstall template [project]{template}[/]"
            )
        if rm:
            try:
                repo.uninstall(template)
                console.success(
                    f"Removed template [project]{template}[/]"
                )
            except OSError:
                console.error(
                    f"Error while uninstalling template [project]{template}[/]"
                )
                console.indent(
                    "You might need to manually delete the template directory at"
                )
                console.indent(f"[path]{repo.root}[/]")
    else:
        console.warn(f"Template [project]{template}[/] does not exist")


@boil.command(short_help="Update an existing template")
@click.argument("template")
@click.pass_context
def update(ctx: click.Context, template: str) -> None:
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

    _template = repo.get_template(template, load=True)
    try:
        _template.update()
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
        if _template.meta["source_type"] == "github":
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
def use(
    ctx: click.Context,
    template: str,
    out: t.Union[str, Path],
    hard: bool,
    value: t.List[t.Tuple[str, str]],
    dev: bool = False,
) -> None:
    """
    Generate a new project from TEMPLATE.

    If OUT is given and a directory, the template is created there.
    Otherwise the cwd is used.
    """
    cfg = ctx.obj

    # Check teamplate and read configuration
    # project = Project(template, cfg["TPLDIR"])
    repo = Repository(cfg["TPLDIR"])
    _template = repo.get_template(template)

    try:
        _template.load()
    except FileNotFoundError:
        console.warn(
            f"No valid template found for key {Fore.CYAN}{_template}{Style.RESET_ALL}"
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
            console.success(f"Cleared [path]{out}[/]")
    elif not out.exists():
        out.mkdir(parents=True)
        console.success(f"Created [path]{out}[/]")

    ## Prepare project and read user answers
    project = Project(_template, out, cfg["prefilled"] if "prefilled" in cfg else dict())
    project.fill()

    for success, file_in, file_out in project.compile():
        if success:
            console.success(f"Created [path]{file_out}[/]")
        else:
            console.warn(
                f"Skipped [path]{file_out}[/] due to empty content"
            )

    console.success(
        f'Generated project template "[project]{_template.name}[/]" in [path]{out}[/]'
    )


@boil.command(short_help="Show information about an installed template")
@click.option(
    "--config",
    is_flag=True,
    help="Print the full project file.",
)
@click.option(
    "--tree",
    is_flag=True,
    help="Print the full template tree.",
)
@click.argument("template")
@click.pass_context
def info(
    ctx: click.Context,
    template: str,
    config: bool,
    tree: bool
) -> None:
    cfg = ctx.obj

    repo = Repository(cfg["TPLDIR"])
    _template = repo.get_template(template)

    if tree:
        _tree = Tree(_template.name)
        _walk_directory(_template.root, _tree)
        _tree_panel = Panel(_tree, title=f"Contents of {_template.root}")
        console.out.print(_tree_panel)
    else:
        _tree = Tree(_template.name)
        _walk_directory(_template.templates_dir, _tree)
        _tree_panel = Panel(_tree, title=f"{template}/{_template.templates_dir.name}")
        console.out.print(_tree_panel)

    if config:
        with open(_template.project_file, 'rt') as cf:
            _syntax = Syntax(cf.read(), lexer='json')
            _syntax_panel = Panel(_syntax, title=str(_template.project_file))
            console.out.print(_syntax_panel)


def _walk_directory(directory: Path, tree: Tree) -> None:
    """Recursively build a Tree with directory contents."""
    from rich.filesize import decimal
    from rich.markup import escape

    # Sort dirs first then by filename
    paths = sorted(
        Path(directory).iterdir(),
        key=lambda path: (path.is_file(), path.name.lower()),
    )

    for path in paths:
        # Remove hidden files
        if path.name.startswith("."):
            continue
        if path.is_dir():
            style = "dim" if path.name.startswith("__") else ""
            branch = tree.add(
                f"[bold magenta]:open_file_folder: [link file://{path}]{escape(path.name)}",
                style=style,
                guide_style=style,
            )
            _walk_directory(path, branch)
        else:
            text_filename = rich.text.Text(path.name, "green")
            text_filename.highlight_regex(r"\..*$", "bold red")
            text_filename.stylize(f"link file://{path}")
            file_size = path.stat().st_size
            text_filename.append(f" ({decimal(file_size)})", "blue")
            icon = "🐍 " if path.suffix == ".py" else "📄 "
            tree.add(rich.text.Text(icon) + text_filename)
