# -*- coding: utf-8 -*-


"""
Parboil lets you generate boilerplate projects from recipe files.

Run boil --help for more info.
"""

import json
import logging.config
import os
import platform
import re
import shutil
import subprocess
import time
import typing as t
from pathlib import Path

import click
import jsonc
import rich
from colorama import Back, Fore, Style
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree
from rich import inspect

import parboil.console as console
from parboil import __version__

from .errors import ProjectError, ProjectExistsError, ProjectFileNotFoundError
from .ext import pass_tpldir
from .recipes import Boiler, Recipe, Repository
from .settings import CFG_DIR, CFG_FILE, LOGGING_CONFIG, TPL_DIR, DEFAULT_CONFIG

logger = logging.getLogger("parboil")

USE_MARKUP = dict(markup=True)
USE_MARKUP_NO_HIGHLIGHT = dict(markup=True, highlight=False)


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
    "--repo",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    envvar="BOIL_REPO",
    help="Location of the local recipe repository.",
)
@click.option("--debug", is_flag=True)
@click.pass_context
def boil(
    ctx: click.Context,
    config: t.TextIO,
    repo: Path,
    debug: bool = False,
) -> None:
    ctx.ensure_object(dict)

    # Setup logging
    logging.config.dictConfig(LOGGING_CONFIG)
    if debug:
        logger.setLevel(logging.DEBUG)

    logger.info(
        "Starting up [b]parboil[/] :rice:, version [bright_cyan bold]%s[/] (Python [bright_cyan bold]%s[/])",
        __version__,
        platform.python_version(),
        extra=USE_MARKUP,
    )

    # Load config file
    ctx.obj = {**ctx.obj, **DEFAULT_CONFIG}

    if config:
        try:
            user_cfg = jsonc.load(config)
            ctx.obj = {**ctx.obj, **user_cfg}
            logger.info("Merged in config from %s", config)
        except json.JSONDecodeError:
            logger.warn("Error loading config from %s", config)
    else:
        if CFG_FILE.exists():
            with open(CFG_FILE) as f:
                try:
                    cmd_cfg = json.load(f)
                    ctx.obj = {**ctx.obj, **cmd_cfg}
                    logger.info("Merged in config from %s", str(CFG_FILE))
                except json.JSONDecodeError:
                    logger.warn("Error loading config from %s", str(CFG_FILE))

    ctx.obj["TPLDIR"] = repo or TPL_DIR
    logger.info("Working with recipe repository %s", str(ctx.obj["TPLDIR"]))


@boil.command(short_help="List installed recipes")
@click.option("-p", "--plain", is_flag=True)
@pass_tpldir
def list(TPLDIR: Path, plain: bool) -> None:
    """
    Lists all recipes in the active local repository.
    """
    repo = Repository(TPLDIR)
    if repo.exists():
        if len(repo) > 0:
            if plain:
                for project_name in repo:
                    console.out.print(project_name)
            else:
                table = Table(
                    title=f"Recipes installed in [path]{TPLDIR}[/path]",
                    # expand=True,
                    box=rich.box.MINIMAL_DOUBLE_HEAD,
                    # show_lines=True,
                )

                table.add_column("Name", style="keyword")
                table.add_column(
                    "[purple]Created[/] / [purple]Updated[/] [bright_black]or[/] [path]Realpath[/]"
                )

                for recipe in sorted(repo.recipes(), key=lambda t: t.name):
                    recipe.load()

                    name = recipe.name
                    created = "[white on red]unknown[/]"
                    updated = "[bright_black]never[/]"
                    if recipe.is_symlinked():
                        name = f"[cyan]{recipe.name}*[/]"
                        data = f"[path]{recipe.root}[/]"
                    else:
                        if "updated" in recipe.meta:
                            updated = time.ctime(int(recipe.meta["updated"]))
                        if "created" in recipe.meta:
                            created = time.ctime(int(recipe.meta["created"]))
                        data = f"[purple]{created}[/] / [purple]{updated}[/]"

                    table.add_row(name, data)

                console.out.print(table)
        else:
            console.info("No recipes installed yet.")
    else:
        console.warn("Repository directory does not exist.")


@boil.command(short_help="Install a new project recipe")
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Set this flag to overwrite existing recipes named RECIPE without prompting.",
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
@click.argument("recipe", required=False)
@click.pass_context
def install(
    ctx: click.Context,
    source: str,
    recipe: str,
    force: bool,
    download: bool,
    is_repo: bool,
    symlink: bool,
) -> None:
    """
    Install a recipe named RECIPE from SOURCE to the local recipe repository.

    SOURCE may be a local directory or the url of a GitHub repository. You may also pass in the name of a repository in the form user/repo, but need to set the -d flag to indicate it isn't a local directory.

    -r indicates that SOURCE is a folder with multiple recipes that should be installed.

    Use -s to create symlinks instead of copying the files. (Useful for recipe development.)
    """
    # logger = logging.getLogger("parboil")

    # TODO: validate recipes!
    TPLDIR = ctx.obj["TPLDIR"]
    repo = Repository(TPLDIR)

    # is source a github url? Then assume -d
    if re.match(r"https?://(www\.)?github\.com", source):
        download = True
    # set missing arguments
    if download:
        if re.match("[A-Za-z_-]+/[A-Za-z_-]+", source):
            source = f"https://github.com/{source}"
        if not recipe:
            recipe = source.split("/")[-1]
    else:
        if not recipe:
            recipe = Path(source).name

    if not is_repo and not force and repo.is_installed(recipe):
        if not console.confirm(f"Overwrite existing recipe named [recipe]{recipe}[/]?"):
            ctx.abort()

    try:
        if download:
            projects = repo.install_from_github(
                recipe, source, hard=True, is_repo=is_repo
            )
        else:
            projects = repo.install_from_directory(
                recipe, source, hard=True, is_repo=is_repo, symlink=symlink
            )
    except ProjectError as fnfe:
        console.error(str(fnfe))
    except FileExistsError as fee:
        console.error(str(fee))
    except shutil.Error:
        console.error(f"Could not install recipe [recipe]{recipe}[/]")
    else:
        if not projects:
            console.success("No recipes where installed.")
            return

        for project in projects:
            console.success(f"Installed recipe [recipe]{project.name}[/]")
        if len(projects) == 1:
            console.printd(f"\nUse with [cmd]boil use {projects[0].name}[/]")
        else:
            console.printd("\nUse with [cmd]boil use <recipe_name>[/]")


@boil.command(short_help="Uninstall an existing recipe")
@click.option("-f", "--force", is_flag=True)
@click.argument("recipe")
@pass_tpldir
def uninstall(TPLDIR: Path, force: bool, recipe: str) -> None:
    repo = Repository(TPLDIR)

    if repo.is_installed(recipe):
        rm = force
        if not force:
            rm = console.confirm(
                f"Do you really want to uninstall recipe [recipe]{recipe}[/]"
            )
        if rm:
            try:
                repo.uninstall(recipe)
                console.success(f"Removed recipe [recipe]{recipe}[/]")
            except OSError:
                console.error(
                    [
                        f"Error while uninstalling recipe [recipe]{recipe}[/]",
                        "You might need to manually delete the recipe directory at",
                        f"[path]{repo.root}[/]",
                    ]
                )
    else:
        console.warn(f"Recipe [recipe]{recipe}[/] does not exist")


@boil.command(short_help="Update an existing recipe")
@click.argument("recipe")
@click.pass_context
def update(ctx: click.Context, recipe: str) -> None:
    """
    Update RECIPE from the source it was first installed from.
    """
    cfg = ctx.obj

    repo = Repository(cfg["TPLDIR"])

    if not repo.is_installed(recipe):
        console.error(f"Recipe [recipe]{recipe}[/] does not exist.")
        ctx.exit(2)

    _recipe = repo.get_recipe(recipe, load=True)
    try:
        repo.update(_recipe)
    except ProjectFileNotFoundError as pe:
        console.error(
            [
                str(pe),
                "To update templates make sure to install with [cmd]boil install[/].",
            ]
        )
        ctx.abort()
    except ProjectError as pe:
        console.error(str(pe))
        ctx.abort()
    else:
        if _recipe.meta["source_type"] == "github":
            console.success(f"Updated template [recipe]{recipe}[/] from GitHub.")
        else:
            console.success(
                f"Updated template [recipe]{recipe}[/] from local filesystem."
            )


@boil.command(short_help="Use an existing recipe")
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
    help="Sets a prefilled value for the recipe.",
)
@click.option("--dev", is_flag=True)
@click.argument("recipe")
@click.argument(
    "out", default=".", type=click.Path(file_okay=False, dir_okay=True, writable=True)
)
@click.pass_context
def use(
    ctx: click.Context,
    recipe: str,
    out: t.Union[str, Path],
    hard: bool,
    value: t.List[t.Tuple[str, str]],
    dev: bool = False,
) -> None:
    """
    Generate a new project from RECIPE.

    If OUT is given and a directory, the recipe is created there.
    Otherwise the cwd is used.
    """
    cfg = ctx.obj
    logger.debug("Using recipe [recipe]%s[/]..", recipe)

    # Check template and read configuration
    repo = Repository(cfg["TPLDIR"])
    _recipe = repo.get_recipe(recipe)

    try:
        _recipe.load()
        logger.debug("  Recipe loaded  ✓")
    except FileNotFoundError:
        console.warn(f"No valid recipe found for name [recipe]{recipe}[/]")
        ctx.exit(1)

    # Prepare output directory
    # if out == ".":
    #     out = Path.cwd()
    # else:
    #     out = Path(out)
    out = Path(out).resolve()

    if out.exists() and len(os.listdir(out)) > 0:
        if hard:
            shutil.rmtree(out)
            out.mkdir(parents=True)
            console.success(f"Cleared [path]{out}[/]")
    elif not out.exists():
        out.mkdir(parents=True)
        console.success(f"Created [path]{out}[/]")

    ## Prepare prefilled values
    prefilled = cfg["prefilled"] if "prefilled" in cfg else dict()
    for key, val in value:
        prefilled[key] = val

    ## Prepare project and read user answers
    project = Boiler(_recipe, out, prefilled)
    project.fill()
    logger.debug("  All ingredients filled  ✓")

    ## Set excludes
    logger.debug("  Setting excludes")
    patterns = cfg["exclude"] if "exclude" in cfg else list()
    for pattern in patterns:
        logger.debug("    Glob pattern %s", pattern)
        files = _recipe.templates_dir.glob(pattern)
        for filepath in files:
            filename = str(filepath.relative_to(_recipe.templates_dir))
            _recipe.files[filename] = {
                "exclude": True,
                **_recipe.files.get(filename, dict()),
            }
            logger.debug("    Added [path]%s[/] to excludes", filename)

    for success, file_in, file_out in project.compile():
        logger.info("%s -> %s (%s)", file_in, file_out, success)
        if success:
            console.success(f"Created [path]{file_out}[/]")
        else:
            console.warn(f"Skipped [path]{file_out}[/] due to empty content")

    console.success(
        f'Generated project for recipe "[recipe]{_recipe.name}[/]" in [path]{out}[/]'
    )


@boil.command(short_help="Show information about an installed recipe")
@click.option(
    "--conf",
    is_flag=True,
    help="Print the full project file.",
)
@click.option(
    "--tree",
    is_flag=True,
    help="Print the full recipe tree.",
)
@click.argument("recipe")
@click.pass_context
def info(ctx: click.Context, recipe: str, conf: bool, tree: bool) -> None:
    cfg = ctx.obj

    repo = Repository(cfg["TPLDIR"])
    if not repo.is_installed(recipe):
        console.warn(f"No recipe [recipe]{recipe}[/] installed.")
        return

    _recipe = repo.get_recipe(recipe)

    info_table = Table(
        title=f"Information for recipe [recipe]{_recipe.name}[/]",
        highlight=True,
        box=rich.box.MINIMAL_DOUBLE_HEAD,
        # show_lines=True,
    )

    info_table.add_column("Property", style="keyword")
    info_table.add_column("Value")

    info_table.add_row("path", str(_recipe.root))
    info_table.add_row("is symlinked", str(_recipe.is_symlinked()))

    console.out.print(info_table)

    if tree:
        _tree = Tree(_recipe.name)
        _walk_directory(_recipe.root, _tree)
        _tree_panel = Panel(_tree, title=f"Contents of {_recipe.root}")
        console.out.print(_tree_panel)

    if conf:
        with open(_recipe.recipe_file, "rt") as cf:
            _syntax = Syntax(cf.read(), lexer="json")
            _syntax_panel = Panel(_syntax, title=str(_recipe.recipe_file))
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
