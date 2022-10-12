# -*- coding: utf-8 -*-

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
from parboil.fields import create_field
from parboil.renderer import ParboilRenderer

from .errors import ProjectError, ProjectExistsError, ProjectFileNotFoundError, TaskExecutionError, TaskFailedError
from .fields import Field
from .helpers import load_files, eval_bool
from .tasks import Task

PRJ_FILE = "parboil.json"
META_FILE = ".parboil"

logger = logging.getLogger(__name__)


@dataclass(init=False)
class Template(object):
    """
    Templates hold information about a template that can be used by parboil
    to generate a project with user answers. The compilation process is handled in
    a `Project` instance.
    """
    name: str

    repository: "Repository"
    _root: Path

    project_file: Path
    meta_file: Path
    templates_dir: Path
    includes_dir: Path

    meta: t.Dict[str, t.Any] = field(default_factory=dict)
    files: t.Dict[str, t.Dict[str, t.Any]] = field(default_factory=dict)
    templates: t.List[t.Union[str, Path, "Template"]] = field(default_factory=list)
    includes: t.List[Path] = field(default_factory=list)

    fields: t.List[Field] = field(default_factory=list)
    context: t.ChainMap[str, t.Any] = field(default_factory=ChainMap)

    tasks: t.Dict[str, t.List[Task]] = field(default_factory=dict)

    def __init__(self, name: str, repository: t.Union[str, Path, "Repository"], load: bool = False):
        self.name = name
        if isinstance(repository, Repository):
            self.repository = repository
        else:
            self.repository = Repository(repository)
        self._root = self.repository.root / name

        # setup config files and paths
        self.project_file = self.root / PRJ_FILE
        self.meta_file = self.root / META_FILE
        self.templates_dir = self.root / "template"
        self.includes_dir = self.root / "includes"

        self.meta = dict()
        self.files = dict()
        self.templates = list()
        self.includes = list()
        self.fields = list()
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

    def is_project(self) -> bool:
        return self.exists() and (self._root / PRJ_FILE).is_file()

    def load(self) -> None:
        """Loads the project file and some metadata"""
        ## Load files form template folder
        self.templates.extend(load_files(self.templates_dir))
        self.includes.extend(load_files(self.includes_dir))

        ## Load config
        config: t.Dict[str, t.Any] = dict()
        try:
            with open(self.project_file) as f:
                config = jsonc.load(f)
        except FileNotFoundError as e:
            raise ProjectFileNotFoundError() from e
        except json.JSONDecodeError as e:
            raise ProjectError("Malformed project file.") from e

        if "files" in config:
            for file, data in config["files"].items():
                if isinstance(data, str):
                    self.files[file] = dict(filename=data)
                else:
                    self.files[file] = data

        ## Parse config
        self._load_fields(config)
        self._load_tasks(config)

        if "context" in config:
            self.context.maps.append({**config["context"]})

        ## Load metafile
        if self.meta_file.is_file():
            with open(self.meta_file) as f:
                self.meta = {**self.meta, **json.load(f)}

    def _load_fields(self, config: t.Dict[str, t.Any]) -> None:
        """Parse `fields` key from `config` into `Field` objects and stores them in the `fields` attribute."""
        if "fields" in config:
            for k, v in config["fields"].items():
                self.fields.append(create_field(k, v))

    def _load_tasks(self, config: t.Dict[str, t.Any]) -> None:
        """Parse `tasks` key from `config` into `Task` objects and stores them in the `tasks` attribute."""
        if "tasks" in config:
            for hook in self.tasks.keys():
                if hook in config["tasks"]:
                    for task_def in config["tasks"][hook]:
                        if isinstance(task_def, str) or isinstance(task_def, list):
                            self.tasks[hook].append(Task(task_def))
                        elif isinstance(task_def, dict):
                            self.tasks[hook].append(Task(**task_def))

    def save(self) -> None:
        """Saves the current meta file to disk"""
        if self.meta_file:
            with open(self.meta_file, "w") as f:
                json.dump(self.meta, f)

    def update(self, hard: bool = False) -> None:
        """Update the template from its original source"""
        if not self.meta_file.exists():
            raise ProjectFileNotFoundError(
                "Template metafile does not exist. Can't read update information."
            )

        if self.meta["source_type"] == "github":
            git = subprocess.Popen(["git", "pull", "--rebase"], cwd=self.root)
            git.wait(30)
        elif self.meta["source_type"] == "local":
            if Path(self.meta["source"]).is_dir():
                shutil.rmtree(self.root)
                shutil.copytree(self.meta["source"], self.root)
            else:
                raise ProjectError("Original source directory no longer exists.")
        else:
            raise ProjectError("No source information found.")

        # Update meta file for later updates
        self.meta["updated"] = time.time()
        self.save()

        self.load()


class Repository(Mapping[str, Template]):
    def __init__(self, root: t.Union[str, Path]) -> None:
        self._root: Path = Path(root)
        self._templates: t.List[str] = list()
        self.load()

    @property
    def root(self) -> Path:
        return self._root

    def exists(self) -> bool:
        return self._root.is_dir()

    def load(self):
        logger.info("Loading repository from `%s`", self._root)
        ## Remove previously loaded templates
        self._templates = list()
        if self.exists():
            for child in self._root.iterdir():
                if child.is_dir():
                    project_file = child / PRJ_FILE
                    if project_file.is_file():
                        self._templates.append(child.name)
                        logger.debug("---> %s", child.name)

    def __len__(self) -> int:
        return len(self._templates)

    def __iter__(self) -> t.Generator[str, None, None]:
        yield from self._templates

    def __getitem__(self, name) -> Template:
        return self.get_template(name)

    def is_installed(self, template: str) -> bool:
        tpl_dir = self._root / template
        return tpl_dir.is_dir()

    def templates(self) -> t.Generator[Template, None, None]:
        yield from (self.get_template(name) for name in self)

    def get_template(self, template: str, load: bool = False) -> Template:
        tpl = Template(template, self)
        if load:
            tpl.load()
        return tpl

    def install_from_directory(
        self,
        template: str,
        source: t.Union[str, Path],
        hard: bool = False,
        is_repo: bool = False,
        symlink: bool = False,
        reload: bool = True
    ) -> t.List[Template]:
        """If source contains a valid project template it is installed
        into this local repository and the Project object is returned.
        """
        logger.info(f"Starting install from directory {source!s}", extra={"repository": self})

        if self.is_installed(template):
            if not hard:
                raise ProjectExistsError(
                    "The template already exists. Delete first or retry install with hard=True."
                )
            else:
                self._delete(template)
                logger.debug(f"Deleted existing template {template}")

        ## check source directory
        source = Path(source).resolve()
        if not source.is_dir():
            raise ProjectFileNotFoundError("Source does not exist.")

        if not is_repo:
            logger.debug("Attempting to install from source %s", source, extra={"repository": self})

            project_file = source / PRJ_FILE
            template_dir = source / "template"

            # FIXME: Remove this
            old_project_file = source / "project.json"
            if old_project_file.is_file():
                logger.debug("Renaming old project config for %s to %s", source.name, PRJ_FILE)
                old_project_file.rename(source / PRJ_FILE)

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
                shutil.copytree(source, self._root / template)

                # create meta file
                _template = self.get_template(template)
                _template.meta = {
                    "created": time.time(),
                    "source_type": "local",
                    "source": str(source),
                }
                _template.save()
            else:
                # create a symlink
                os.symlink(source, self._root / template, target_is_directory=True)
                _template = self.get_template(template)

            templates = [_template]
        else:
            templates = list()

            for child in source.iterdir():
                if child.is_dir():
                    logger.debug("Attempting to install from subfolder %s", child, extra={"repository": self})

                    # FIXME: Remove this
                    old_project_file = child / "project.json"
                    if old_project_file.is_file():
                        logger.debug("Renaming old project config for %s to %s", child.name, PRJ_FILE)
                        old_project_file.rename(child / PRJ_FILE)

                    project_file = child / PRJ_FILE
                    if project_file.is_file():
                        try:
                            _template = self.install_from_directory(
                                child.name, child, hard=hard, reload=False
                            )[0]
                            templates.append(_template)
                        except ProjectFileNotFoundError:
                            logger.warn("Subfolder %s is not a valid subfolder", child, extra={"repository": self})
                            pass

        if reload:
            self.load()
        return templates

    def install_from_github(
        self, template: str, url: str, hard: bool = False, is_repo: bool = False
    ) -> t.List[Template]:
        if not is_repo:
            # check target dir
            if self.is_installed(template):
                if not hard:
                    raise ProjectExistsError(
                        "The template already exists. Delete first or retry install with hard=True."
                    )
                else:
                    self._delete(template)

            project = self.get_template(template)

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
                    if child.name not in self._templates:
                        diff.append(child.name)
                        self._templates.append(child.name)
        self._templates.sort()
        return diff


@dataclass
class Project(object):
    """
    A Project compiles a `Template` into a `target_dir`.

    In this process the user may be is prompted for answers to the fields
    configured in the templates config file.
    """
    template: Template
    target_dir: Path

    prefilled: t.Dict[str, t.Any]
    context: t.ChainMap[str, t.Any] = field(default_factory=ChainMap)

    def fill(self) -> None:
        """
        Get field values either from the prefilled values or read user input.
        """
        for _field in self.template.fields:
            self.renderer.render_obj(_field, FIELD=_field)

            if not eval_bool(_field.condition or True):
                console.info(f'Skipped field "[field]{_field.name}[/]" due to failed condition')
                continue
            elif _field.name in self.prefilled:
                self.context[_field.name] = _field.value = self.renderer.render_string(self.prefilled[_field.name], FIELD=_field)
                console.info(f'Used prefilled value for "[field]{_field.name}[/]"')
            else:
                self.context[_field.name] = _field.prompt(self)

        for key, descr in self.template.context.items():
            self.context[key] = self.renderer.render_string(descr)

    def compile(self) -> t.Generator[t.Tuple[bool, str, str], None, None]:
        """
        Attempts to compile every file in self.templates with jinja and to save it to its final location in the output folder.

        Yields a tuple with three values for each template file:
            1. (bool) If an output file was generated
            2. (str) The original file
            3. (str) The output file after compilation (if any)
        """
        ## Create target directory
        self.target_dir.mkdir(parents=True, exist_ok=True)

        ## Execute pre-run tasks
        self.execute_tasks("pre-run")

        # TODO Error handling
        for _file in self.template.templates:
            if isinstance(_file, Template):
                # TODO refactor subproject inclusion (field and compilation to tighly coupled)
                subproject = Project(_file, self.target_dir, self.prefilled)
                yield from subproject.compile()
            else:
                file_in = Path(str(_file).removeprefix("includes:"))
                file_out = str(file_in)
                file_cfg: t.Dict[str, t.Any] = self.template.files.get(str(file_in), dict())
                file_out = file_cfg.get("filename", file_out)

                rel_path = file_in.parent
                abs_path = self.target_dir / rel_path

                # Set some dynamic values
                boil_vars = dict(
                    RELDIR="" if rel_path.name == "" else str(rel_path),
                    ABSDIR=str(abs_path),
                    OUTDIR=str(self.target_dir),
                    OUTNAME=str(self.target_dir.name)
                )
                path_render = self.renderer.render_string(file_out, BOIL=boil_vars)

                if Path(path_render).exists() and not file_cfg.get("overwrite", True):
                    yield (False, str(file_in), "")
                    continue

                boil_vars["FILENAME"] = Path(path_render).name
                boil_vars["FILEPATH"] = path_render

                if file_cfg.get("render", True):
                    # Render template
                    tpl_render = self.renderer.render_file(_file, BOIL=boil_vars)
                else:
                    tpl_render = self.template.templates_dir.joinpath(_file).read_text()

                generate_file = bool(tpl_render.strip())  # empty?
                generate_file = file_cfg.get("keep", generate_file)

                if generate_file:
                    path_render_abs = self.target_dir / path_render
                    path_render_abs.parent.mkdir(parents=True, exist_ok=True)
                    path_render_abs.write_text(tpl_render)

                    yield (True, str(_file), path_render)
                else:
                    yield (False, str(_file), path_render)

        # Execute post-run tasks
        self.execute_tasks("post-run")

    def execute_tasks(self, hook: str) -> None:
        if hook not in self.template.tasks:
            return

        total_tasks = len(self.template.tasks[hook])
        with self.cwd():
            for i, task in enumerate(self.template.tasks[hook]):
                self.renderer.render_obj(task, TASK=task)
                console.info(f"Running [keyword]{hook}[/] task {i+1} of {total_tasks}: [cmd]{task}[/]")
                try:
                    if not task.execute():
                        raise TaskFailedError(task)
                except Exception as e:
                    raise TaskExecutionError(task) from e

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
