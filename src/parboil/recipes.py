# -*- coding: utf-8 -*-
"""Handling of recipes.

Classes for handling recipes (boilerplate templates), repositories
(directories with installed templates) and boilers (projects that compile
templates into a specific target directory).
"""


import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import typing as t
from collections import ChainMap
from collections.abc import Mapping, MutableMapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import click
import jsonc
from rich import inspect

import parboil.console as console

from .errors import (
    ProjectError,
    ProjectExistsError,
    ProjectFileNotFoundError,
    RecipeNotInstalledError,
    TaskExecutionError,
    TaskFailedError,
)
from .helpers import eval_bool, load_files
from .ingredients import Ingredient, get_ingredient
from .renderer import ParboilRenderer
from .settings import META_FILE, PRJ_FILE
from .tasks import Task

logger = logging.getLogger(__name__)

RESERVED_KEYS = ("_tasks", "_files", "_context", "_settings")


@dataclass(init=False)
class Recipe:
    """Container for recipe information.

    Recipes hold information about a template that can be used by parboil
    to generate a project with user answers. The compilation process is handled in
    a [parboil.recipes.Boiler][] instance.

    Raises:
        ProjectFileNotFoundError: In case some mandatory recipe files are missing.
        ProjectError: Any error related to project initialization.
    """

    name: str

    repository: "Repository"
    _root: Path

    recipe_file: Path
    meta_file: Path
    templates_dir: Path
    includes_dir: Path

    meta: t.Dict[str, t.Any] = field(default_factory=dict)
    files: t.Dict[str, t.Dict[str, t.Any]] = field(default_factory=dict)
    templates: t.List[t.Union[str, Path, "Recipe"]] = field(default_factory=list)
    includes: t.List[Path] = field(default_factory=list)

    ingredients: t.List[Ingredient] = field(default_factory=list)
    context: t.ChainMap[str, t.Any] = field(default_factory=ChainMap)

    tasks: t.Dict[str, t.List[Task]] = field(default_factory=dict)

    def __init__(
        self,
        name: str,
        repository: t.Union[str, Path, "Repository"],
        load: bool = False,
    ):
        self.name = name
        if isinstance(repository, Repository):
            self.repository = repository
        else:
            self.repository = Repository(repository)
        self._root = self.repository.root / name

        # setup config files and paths
        self.recipe_file = self.root / PRJ_FILE
        self.meta_file = self.root / META_FILE
        self.templates_dir = self.root / "template"
        self.includes_dir = self.root / "includes"

        self.meta = dict()
        self.files = dict()
        self.templates = list()
        self.includes = list()
        self.ingredients = list()
        self.context = ChainMap()
        self.tasks = {"pre-run": [], "post-run": []}

        if load:
            self.load()

    @property
    def root(self) -> Path:
        if self.is_symlinked():
            return self._root.resolve()
        else:
            return self._root

    def is_symlinked(self) -> bool:
        return self._root.is_symlink()

    def exists(self) -> bool:
        return self._root.is_dir()

    def is_valid(self) -> bool:
        return self.exists() and self.recipe_file.is_file()

    def load(self) -> None:
        """Loads the project file and some metadata."""
        # Load files form template folder
        self.templates.extend(load_files(self.templates_dir))
        self.includes.extend(load_files(self.includes_dir))

        # Load config
        config: t.Dict[str, t.Any] = dict()
        try:
            with open(self.recipe_file) as f:
                config = jsonc.load(f)
        except FileNotFoundError as e:
            raise ProjectFileNotFoundError() from e
        except json.JSONDecodeError as e:
            raise ProjectError("Malformed project file.") from e

        if "_files" in config:
            for file, data in config["_files"].items():
                if isinstance(data, str):
                    self.files[file] = dict(filename=data)
                else:
                    self.files[file] = data

        # Parse config
        self._load_ingredients(config)
        self._load_tasks(config)

        if "_context" in config:
            self.context.maps.append({**config["_context"]})

        # Load metafile
        if self.meta_file.is_file():
            with open(self.meta_file) as f:
                self.meta = {**self.meta, **json.load(f)}

    def _load_ingredients(self, config: t.Dict[str, t.Any]) -> None:
        """
        Parse `fields` key from `config` into `Ingredient` objects
        and stores them in the `ingredients` attribute.
        """
        for k, v in config.items():
            if k not in RESERVED_KEYS:
                self.ingredients.append(get_ingredient(k, v))

    def _load_tasks(self, config: t.Dict[str, t.Any]) -> None:
        """Parse ``tasks`` key from ``config`` into :class:`Task` objects and stores them in the ``tasks`` attribute."""
        if "_tasks" in config:
            for hook in self.tasks.keys():
                if hook in config["_tasks"]:
                    for task_def in config["_tasks"][hook]:
                        if isinstance(task_def, str) or isinstance(task_def, list):
                            self.tasks[hook].append(Task(task_def))
                        elif isinstance(task_def, dict):
                            self.tasks[hook].append(Task(**task_def))

    def save(self) -> None:
        """Saves the current meta file to disk."""
        if self.meta_file:
            with open(self.meta_file, "w") as f:
                json.dump(self.meta, f)


class Repository(Mapping[str, Recipe]):
    def __init__(self, root: t.Union[str, Path]) -> None:
        self._root: Path = Path(root)
        self._recipes: t.List[str] = list()
        self.load()

    @property
    def root(self) -> Path:
        return self._root

    def exists(self) -> bool:
        return self._root.is_dir()

    def load(self):
        logger.info("Loading repository from `%s`", self._root)
        ## Remove previously loaded templates
        self._recipes = list()
        if self.exists():
            for child in self._root.iterdir():
                if child.is_dir():
                    project_file = child / PRJ_FILE
                    if project_file.is_file():
                        self._recipes.append(child.name)
                        logger.debug("---> %s", child.name)

    def __len__(self) -> int:
        return len(self._recipes)

    def __iter__(self) -> t.Generator[str, None, None]:
        yield from self._recipes

    def __getitem__(self, name) -> Recipe:
        return self.get_recipe(name)

    def is_installed(self, recipe: str) -> bool:
        # TODO is thos enough?
        recipe_dir = self._root / recipe
        return recipe_dir.is_dir()

    def recipes(self) -> t.Generator[Recipe, None, None]:
        yield from (self.get_recipe(name) for name in self)

    def get_recipe(self, recipe: str, load: bool = False) -> Recipe:
        r = Recipe(recipe, self)
        if load:
            r.load()
        return r

    def install_from_directory(
        self,
        recipe: str,
        source: t.Union[str, Path],
        hard: bool = False,
        is_repo: bool = False,
        symlink: bool = False,
        reload: bool = True,
    ) -> t.List[Recipe]:
        """
        If source contains a valid recipe it is installed
        into this local repository and a `Recipe` object is returned.
        """
        logger.info(
            f"Starting install from directory {source!s}", extra={"repository": self}
        )

        if self.is_installed(recipe):
            if not hard:
                raise ProjectExistsError(
                    "The template already exists. Delete first or retry install with hard=True."
                )
            else:
                self._delete(recipe)
                logger.debug(f"Deleted existing template {recipe}")

        ## check source directory
        source = Path(source).resolve()
        if not source.is_dir():
            raise ProjectFileNotFoundError("Source does not exist.")

        if not is_repo:
            logger.debug(
                "Attempting to install from source %s",
                source,
                extra={"repository": self},
            )

            project_file = source / PRJ_FILE
            template_dir = source / "template"

            if not project_file.is_file():
                raise ProjectFileNotFoundError(
                    f"The source does not contain a {PRJ_FILE} file."
                )

            if not template_dir.is_dir():
                raise ProjectFileNotFoundError(
                    "The source does not contain a template directory."
                )

            # install template
            if not symlink:
                # copy full template tree
                shutil.copytree(source, self._root / recipe)

                # create meta file
                _template = self.get_recipe(recipe)
                _template.meta = {
                    "created": time.time(),
                    "source_type": "local",
                    "source": str(source),
                }
                _template.save()
            else:
                # create a symlink
                os.symlink(source, self._root / recipe, target_is_directory=True)
                _template = self.get_recipe(recipe)

            templates = [_template]
        else:
            templates = list()

            for child in source.iterdir():
                if child.is_dir():
                    logger.debug(
                        "Attempting to install from subfolder %s",
                        child,
                        extra={"repository": self},
                    )

                    project_file = child / PRJ_FILE
                    if project_file.is_file():
                        try:
                            _template = self.install_from_directory(
                                child.name, child, hard=hard, reload=False
                            )[0]
                            templates.append(_template)
                        except ProjectFileNotFoundError:
                            logger.warn(
                                "Subfolder %s is not a valid subfolder",
                                child,
                                extra={"repository": self},
                            )
                            pass

        if reload:
            self.load()
        return templates

    def install_from_github(
        self, template: str, url: str, hard: bool = False, is_repo: bool = False
    ) -> t.List[Recipe]:
        if not is_repo:
            # check target dir
            if self.is_installed(template):
                if not hard:
                    raise ProjectExistsError(
                        "The template already exists. Delete first or retry install with hard=True."
                    )
                else:
                    self._delete(template)

            project = self.get_recipe(template)

            # do git clone
            # TODO: Does this work on windows?
            git = subprocess.Popen(["git", "clone", url, str(project.root)])
            git.wait(30)

            # create meta file
            project.meta = {
                "created": time.time(),
                "source_type": "github",
                "source": url,
            }
            project.save()

            self.load()
            return [project]
        else:
            projects = list()  # return list of installed projects

            # do git clone into temp folder
            with tempfile.TemporaryDirectory() as temp_repo:
                git = subprocess.Popen(["git", "clone", url, temp_repo])
                git.wait(30)

                for child in Path(temp_repo).iterdir():
                    if child.is_dir():
                        project_file = child / PRJ_FILE
                        if project_file.is_file():
                            try:
                                project = self.install_from_directory(
                                    child.name, child, hard=hard
                                )[0]
                                # remove source data
                                del project.meta["source_type"]
                                del project.meta["source"]
                                project.save()

                                projects.append(project)
                            except ProjectFileNotFoundError:
                                pass
                            except ProjectExistsError:
                                pass

            self.load()
            return projects

    def uninstall(self, template: str) -> None:
        self._delete(template)

    def update(self, recipe: t.Union[str, Recipe], hard: bool = False) -> None:
        """
        Update an template from its original source.

        Does not work for symlinked templates.
        """
        if isinstance(recipe, str):
            if not self.is_installed(recipe):
                raise RecipeNotInstalledError(recipe, self)
                return
            recipe = self.get_recipe(recipe)

        if not recipe.meta_file.exists():
            raise ProjectFileNotFoundError(
                "Template metafile does not exist. Can't read update information."
            )

        if recipe.meta["source_type"] == "github":
            git = subprocess.Popen(["git", "pull", "--rebase"], cwd=recipe.root)
            git.wait(30)
        elif recipe.meta["source_type"] == "local":
            if Path(recipe.meta["source"]).is_dir():
                shutil.rmtree(recipe.root)
                shutil.copytree(recipe.meta["source"], recipe.root)
            else:
                raise ProjectError("Original source directory no longer exists.")
        else:
            raise ProjectError("No source information found.")

        # Update meta file for later updates
        recipe.meta["updated"] = time.time()
        recipe.save()

        recipe.load()

    def _delete(self, template: str) -> None:
        """Delete a project template from this repository."""
        tpl_dir = self._root / template
        if tpl_dir.is_dir():
            if tpl_dir.is_symlink():
                tpl_dir.unlink()
            else:
                shutil.rmtree(tpl_dir)

    def _reload(self) -> t.List[str]:
        diff = list()
        for child in self._root.iterdir():
            if child.is_dir():
                project_file = child / PRJ_FILE
                if project_file.is_file():
                    if child.name not in self._recipes:
                        diff.append(child.name)
                        self._recipes.append(child.name)
        self._recipes.sort()
        return diff


@dataclass
class Boiler:
    """A `Boiler` renders a [Recipe][parboil.recipes.Recipe] into a `target_dir`.

    In this process the user may be is prompted for answers to the fields
    configured in the recipes config file.

    Raises:
        TaskFailedError: If a task exited with a returncode other than zero.
        TaskExecutionError: If a task fails execution.

    Attributes:
        recipe:
            The recipe this `Boiler` will render.
        target_dir:
            Directory the recipe is renderered into.
        prefilled:
            A dicttionary with already defined variable values.
        context:
            A dictionary with context variables to use for template rendering.
    """

    recipe: Recipe
    target_dir: Path

    prefilled: t.Dict[str, t.Any]
    context: t.ChainMap[str, t.Any] = field(default_factory=ChainMap)

    def fill(self) -> None:
        """
        Get field values either from the prefilled values or read user input.
        """
        for _field in self.recipe.ingredients:
            self.renderer.render_obj(_field, INGREDIENT=_field)

            if not eval_bool(_field.condition or True):
                console.info(
                    f'Skipped field "[ingredient]{_field.name}[/]" due to failed condition'
                )
                continue
            elif _field.name in self.prefilled:
                self.context[_field.name] = _field.value = self.renderer.render_string(
                    self.prefilled[_field.name], INGREDIENT=_field
                )
                console.info(f'Used prefilled value for "[ingredient]{_field.name}[/]"')
            else:
                self.context[_field.name] = _field.prompt(self)

        for key, descr in self.recipe.context.items():
            self.context[key] = self.renderer.render_string(descr)

    def compile(self) -> t.Generator[t.Tuple[bool, Path, t.Optional[Path]], None, None]:
        """Compile the recipe into the target directory.

        Attempts to compile every file in `self.templates` with [jinja2](#) and to save it to its final location in the target directory.

        Yields a tuple with three values for each template file:



        Yields:
            (bool, str, str): A tuple holding

                1. `True`, if an output file was generated, `False` otherwise,
                2. the original file.
                3. The output file after compilation or `None`, if no file was rendered.
        """
        ## Create target directory
        self.target_dir.mkdir(parents=True, exist_ok=True)

        ## Execute pre-run tasks
        self.execute_tasks("pre-run")

        # TODO Error handling
        for _file in self.recipe.templates:
            if isinstance(_file, Recipe):
                # TODO refactor subproject inclusion (field and compilation to tighly coupled)
                subproject = Boiler(_file, self.target_dir, self.prefilled)
                yield from subproject.compile()
            else:
                logger.debug("  Working on file [path]%s[/]", _file)
                _file = Path(_file)
                file_in = Path(str(_file).removeprefix("includes:"))
                file_out = str(file_in)
                file_cfg: t.Dict[str, t.Any] = self.recipe.files.get(
                    str(file_in), dict()
                )
                file_out = file_cfg.get("filename", file_out)

                rel_path = file_in.parent
                abs_path = self.target_dir / rel_path

                # Set some dynamic values
                boil_vars = dict(
                    RELDIR="" if rel_path.name == "" else str(rel_path),
                    ABSDIR=str(abs_path),
                    OUTDIR=str(self.target_dir),
                    OUTNAME=str(self.target_dir.name),
                )
                path_render = self.renderer.render_string(file_out, BOIL=boil_vars)
                logger.debug("    Filename rendererd to [path]%s[/] ✓", path_render)

                # Is file excluded?
                if file_cfg.get("exclude", False):
                    logger.debug(
                        "    [path]%s[/] is excluded from rendering", path_render
                    )
                    yield (False, file_in, None)
                    continue

                # Should existsing file be overwritten?
                if Path(path_render).exists() and not file_cfg.get("overwrite", True):
                    logger.debug(
                        "    [path]%s[/] exists and will not be overwritten",
                        path_render,
                    )
                    yield (False, file_in, None)
                    continue

                boil_vars["FILENAME"] = Path(path_render).name
                boil_vars["FILEPATH"] = path_render

                if file_cfg.get("render", True):
                    # Render template
                    tpl_render = self.renderer.render_file(_file, BOIL=boil_vars)
                else:
                    tpl_render = self.recipe.templates_dir.joinpath(_file).read_text()

                generate_file = bool(tpl_render.strip())  # empty?
                generate_file = file_cfg.get("keep", generate_file)

                if generate_file:
                    path_render_abs = self.target_dir / path_render
                    path_render_abs.parent.mkdir(parents=True, exist_ok=True)
                    path_render_abs.write_text(tpl_render)

                    yield (True, _file, Path(path_render))
                else:
                    yield (False, _file, Path(path_render))

        # Execute post-run tasks
        self.execute_tasks("post-run")

    def execute_tasks(self, hook: str) -> None:
        if hook not in self.recipe.tasks:
            return

        logger.debug("  Executing %s hook..", hook)
        total_tasks = len(self.recipe.tasks[hook])
        with self.cwd():
            for i, task in enumerate(self.recipe.tasks[hook]):
                self.renderer.render_obj(task, TASK=task)
                console.info(
                    f"Running [keyword]{hook}[/] task {i+1} of {total_tasks}: [cmd]{task}[/]"
                )
                try:
                    if not task.execute():
                        raise TaskFailedError(task)
                except Exception as e:
                    raise TaskExecutionError(task) from e
        logger.debug("    done  ✓")

    @cached_property
    def renderer(self) -> ParboilRenderer:
        return ParboilRenderer(self)

    @contextmanager
    def cwd(self) -> t.Iterator[Path]:
        """Change working dir to `self.target_dir` for task execution."""
        _current = Path.cwd()
        os.chdir(self.target_dir)
        yield self.target_dir
        os.chdir(_current)
