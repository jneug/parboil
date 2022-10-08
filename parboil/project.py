# -*- coding: utf-8 -*-

import json
import logging
import os
import re
import sys
import shutil
import subprocess
import tempfile
import time
import typing as t
from pathlib import Path
from contextlib import contextmanager

import click
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PrefixLoader

import parboil.fields as fields
from .tasks import Task
import parboil.console as console

from .ext import (
    JinjaTimeExtension,
    jinja_filter_fileify,
    jinja_filter_roman,
    jinja_filter_slugify,
    jinja_filter_time,
)

PRJ_FILE = "project.json"
META_FILE = ".parboil"

logger = logging.getLogger(__name__)


class Project(object):
    def __init__(self, name: str, repository: t.Union[str, Path, "Repository"]):
        self._name = name
        if isinstance(repository, Repository):
            self._repo = repository  # type: t.Optional[Repository]
            self._root_dir = repository.root / self._name
        else:
            self._repo = None
            self._root_dir = Path(repository) / self._name
        # Cache for jinja environment
        self._jinja = None  # type: t.Optional[Environment]

    @property
    def name(self) -> str:
        return self._name

    @property
    def root(self) -> Path:
        return self._root_dir

    def is_symlinked(self) -> bool:
        return self._root_dir.is_symlink()

    def exists(self) -> bool:
        return self._root_dir.is_dir()

    def is_project(self) -> bool:
        return self.exists() and (self._root_dir / PRJ_FILE).is_file()

    def setup(self, load_project: bool = False) -> None:
        # Resolve root dir, may be a symlink
        _root = self._root_dir.resolve()

        # setup config files and paths
        self.project_file = _root / PRJ_FILE
        self.meta_file = _root / META_FILE
        self.templates_dir = _root / "template"
        self.includes_dir = _root / "includes"

        self.meta: t.Dict[str, t.Any] = dict()
        self.files: t.Dict[str, t.Dict[str, t.Any]] = dict()
        self.fields: t.Dict[str, t.Any] = dict()
        self.context: t.Dict[str, t.Any] = dict()
        self.variables: t.Dict[str, t.Any] = dict()
        self.templates: t.List[t.Union[str, Path, Project]] = list()
        self.includes: t.List[Path] = list()
        self.tasks: t.Dict[str, t.List[Task]] = {
            "pre-run": [],
            "post-run": []
        }

        self.templates = list()
        for root, dirs, files in os.walk(self.templates_dir):
            root_path = Path(root).resolve()
            for name in files:
                dirname = root_path.relative_to(self.templates_dir)
                self.templates.append(dirname / name)

        self.includes = list()
        for root, dirs, files in os.walk(self.includes_dir):
            root_path = Path(root).resolve()
            for name in files:
                dirname = root_path.relative_to(self.includes_dir)
                self.includes.append(dirname / name)

        if load_project:
            self.load()

    def load(self) -> None:
        """Loads the project file and some metadata"""

        if not self.project_file:
            self.setup()

        ## project file
        config = dict()
        if self.project_file.exists():
            with open(self.project_file) as f:
                config = json.load(f)
                if "files" not in config:
                    config["files"] = dict()

                self.files = dict()
                for file, data in config["files"].items():
                    if type(data) is str:
                        self.files[file] = dict(filename=data)
                    else:
                        self.files[file] = data
        else:
            raise ProjectFileNotFoundError("Project file not found.")

        if "fields" in config:
            for k, v in config["fields"].items():
                if type(v) is not dict:
                    self.fields[k] = dict(type="default", default=v)
                else:
                    if "type" not in v:
                        v["type"] = "dict"
                    self.fields[k] = v

        if "context" in config:
            self.context = config["context"].copy()

        if 'tasks' in config:
            for hook in self.tasks.keys():
                if hook in config['tasks']:
                    for task_def in config['tasks'][hook]:
                        if isinstance(task_def, str) or isinstance(task_def, list):
                            self.tasks[hook].append(Task(task_def))
                        elif isinstance(task_def, dict):
                            self.tasks[hook].append(Task(**task_def))

        ## metafile
        if self.meta_file.is_file():
            with open(self.meta_file) as f:
                self.meta = {**self.meta, **json.load(f)}

    def fill(
        self,
        prefilled: t.Dict[str, str] = dict(),
        jinja: t.Optional[Environment] = None,
    ) -> None:
        """
        Get field values either from the prefilled values or read user input.
        """
        if not jinja:
            jinja = self._create_jinja()

        for key, descr in self.fields.items():
            value = None
            if key in prefilled:
                value = jinja.from_string(prefilled[key]).render(
                    **self.variables, BOIL=dict(TPLNAME=self._name), ENV=os.environ
                )

            if isinstance(descr, dict) and "type" in descr:
                if descr["type"] == "project":
                    subproject = Project(descr["name"], self.root.parent)
                    if subproject.is_project():
                        subproject.setup(load_project=True)
                        subproject.fill({**prefilled, **self.variables})
                        self.templates.append(subproject)
                else:
                    field_callable = f'field_{descr["type"]}'
                    del descr["type"]

                    if hasattr(fields, field_callable):
                        # If there is a default value, compile it with jinja
                        # to replace existing jinja tags.
                        if "default" in descr and isinstance(descr["default"], str):
                            descr["default"] = jinja.from_string(
                                descr["default"]
                            ).render(
                                **self.variables,
                                BOIL=dict(TPLNAME=self._name),
                                ENV=os.environ,
                            )

                        # Ask for user input
                        self.variables[key] = getattr(fields, field_callable)(
                            key=key, **descr, value=value, project=self
                        )

        for key, descr in self.context.items():
            self.variables[key] = jinja.from_string(descr).render(
                **self.variables,
                BOIL=dict(TPLNAME=self._name),
                ENV=os.environ,
            )

    def compile(
        self, target_dir, jinja=None
    ) -> t.Generator[t.Tuple[bool, str, str], None, None]:
        """
        Attempts to compile every file in self.templates with jinja and to save it to its final location in the output folder.

        Yields a tuple with three values for each template file:
            1. (bool) If an output file was generated
            2. (str) The original file
            3. (str) The output file after compilation (if any)
        """
        if not jinja:
            jinja = self._create_jinja()

        ## Create target directory
        target_dir = Path(target_dir).resolve()
        if not target_dir.exists():
            target_dir.match(parents=True)

        ## temporary context manager to change cwd to target dir
        @contextmanager
        def cwd():
            _current = Path.cwd()
            os.chdir(target_dir)
            yield target_dir
            os.chdir(_current)

        ## Execute pre-run tasks
        with cwd():
            self.execute_tasks('pre-run')

        # result = (list(), list())
        for _file in self.templates:
            if isinstance(_file, Project):
                for result in _file.compile(target_dir):
                    yield result
            else:
                file_in = Path(str(_file).removeprefix("includes:"))
                file_out = str(file_in)
                file_cfg: t.Dict[str, t.Any] = self.files.get(str(file_in), dict())
                file_out = file_cfg.get("filename", file_out)

                rel_path = file_in.parent
                abs_path = target_dir / rel_path

                # Set some dynamic values
                boil_vars = dict(
                    TPLNAME=self._name,
                    RELDIR="" if rel_path.name == "" else str(rel_path),
                    ABSDIR=str(abs_path),
                    OUTDIR=str(target_dir),
                    OUTNAME=str(target_dir.name),
                    RUNTIME=sys.executable
                )

                path_render = jinja.from_string(file_out).render(
                    **self.variables, BOIL=boil_vars, ENV=os.environ
                )

                if Path(path_render).exists() and not file_cfg.get("overwrite", True):
                    yield (False, str(file_in), "")
                    continue

                boil_vars["FILENAME"] = Path(path_render).name
                boil_vars["FILEPATH"] = path_render

                if file_cfg.get("compile", True):
                    # Render template
                    tpl_render = jinja.get_template(str(_file)).render(
                        **self.variables, BOIL=boil_vars, ENV=os.environ
                    )
                else:
                    tpl_render = self.templates_dir.joinpath(_file).read_text()

                generate_file = bool(tpl_render.strip())  # empty?
                generate_file = file_cfg.get("keep", generate_file)

                if generate_file:
                    path_render_abs = target_dir / path_render
                    if not path_render_abs.parent.exists():
                        path_render_abs.parent.mkdir(parents=True)

                    with open(path_render_abs, "w") as f:
                        f.write(tpl_render)

                    yield (True, str(_file), path_render)
                else:
                    yield (False, str(_file), path_render)

        with cwd():
            self.execute_tasks('post-run')

    def execute_tasks(self, hook: str) -> bool:
        success = True
        total_tasks = len(self.tasks[hook])
        for i, task in enumerate(self.tasks[hook]):
            task.render(self._create_jinja(), dict(
                **self.variables,
                BOIL=dict(
                    TPLNAME=self._name,
                    RUNTIME=sys.executable
                ),
                ENV=os.environ
            ))
            console.info(f'Running {hook} task {i+1} of {total_tasks}: {task.cmd_safe}')
            success = success and task.execute()
        return success

    def _create_jinja(self) -> Environment:
        """Creates a jinja Environment for this project and caches it"""
        if not self._jinja:
            self._jinja = Environment(
                loader=ChoiceLoader(
                    [
                        FileSystemLoader(self.templates_dir),
                        PrefixLoader(
                            {"includes": FileSystemLoader(self.includes_dir)},
                            delimiter=":",
                        ),
                    ]
                ),
                extensions=[JinjaTimeExtension],
            )
            self._jinja.filters["fileify"] = jinja_filter_fileify
            self._jinja.filters["slugify"] = jinja_filter_slugify
            self._jinja.filters["roman"] = jinja_filter_roman
            self._jinja.filters["time"] = jinja_filter_time

        return self._jinja

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
            git = subprocess.Popen(["git", "pull", "--rebase"], cwd=self._root_dir)
            git.wait(30)
        elif self.meta["source_type"] == "local":
            if Path(self.meta["source"]).is_dir():
                shutil.rmtree(self._root_dir)
                shutil.copytree(self.meta["source"], self._root_dir)
            else:
                raise ProjectError("Original source directory no longer exists.")
        else:
            raise ProjectError("No source information found.")

        # Update meta file for later updates
        self.meta["updated"] = time.time()
        self.save()

        self.setup(load_project=True)


class Repository(object):
    def __init__(self, root: t.Union[str, Path]) -> None:
        self._root = Path(root)
        self.load()

    @property
    def root(self) -> Path:
        return self._root

    def exists(self) -> bool:
        return self._root.is_dir()

    def load(self):
        logger.info("Loading repository from `%s`", self._root)
        self._projects = list()
        if self.exists():
            for child in self._root.iterdir():
                if child.is_dir():
                    project_file = child / PRJ_FILE
                    if project_file.is_file():
                        self._projects.append(child.name)
                        logger.info("---> %s", child.name)

    def __len__(self) -> int:
        return len(self._projects)

    def __iter__(self) -> t.Generator[str, None, None]:
        yield from self._projects

    def is_installed(self, template: str) -> bool:
        tpl_dir = self._root / template
        return tpl_dir.is_dir()
        # return Project(template, self).exists()

    def projects(self) -> t.Generator[Project, None, None]:
        for prj in self._projects:
            yield self.get_project(prj)

    def get_project(self, template: str) -> Project:
        return Project(template, self)

    def install_from_directory(
        self,
        template: str,
        source: t.Union[str, Path],
        hard: bool = False,
        is_repo: bool = False,
        symlink: bool = False,
    ) -> t.List[Project]:
        """If source contains a valid project template it is installed
        into this local repository and the Project object is returned.
        """
        if self.is_installed(template):
            if not hard:
                raise ProjectExistsError(
                    "The template already exists. Delete first or retry install with hard=True."
                )
            else:
                self._delete(template)

        # check source directory
        source = Path(source).resolve()
        if not source.is_dir():
            raise ProjectFileNotFoundError("Source does not exist.")

        if not is_repo:
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

            project = self.get_project(template)

            # install template
            if not symlink:
                # copy full template tree
                shutil.copytree(source, project.root)

                # create meta file
                project.setup()
                project.meta = {
                    "created": time.time(),
                    "source_type": "local",
                    "source": str(source),
                }
                project.save()
            else:
                # create a symlink
                os.symlink(source, project.root, target_is_directory=True)

            self.load()
            return [project]
        else:
            projects = list()

            for child in source.iterdir():
                if child.is_dir():
                    project_file = child / PRJ_FILE
                    if project_file.is_file():
                        try:
                            project = self.install_from_directory(
                                child.name, child, hard=hard
                            )[0]
                            projects.append(project)
                        except ProjectFileNotFoundError:
                            pass

            self.load()
            return projects

    def install_from_github(
        self, template: str, url: str, hard: bool = False, is_repo: bool = False
    ) -> t.List[Project]:
        if not is_repo:
            # check target dir
            if self.is_installed(template):
                if not hard:
                    raise ProjectExistsError(
                        "The template already exists. Delete first or retry install with hard=True."
                    )
                else:
                    self._delete(template)

            project = self.get_project(template)

            # do git clone
            # TODO: Does this work on windows?
            git = subprocess.Popen(["git", "clone", url, str(project.root)])
            git.wait(30)

            # create meta file
            project.setup()
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
                    if child.name not in self._projects:
                        diff.append(child.name)
                        self._projects.append(child.name)
        self._projects.sort()
        return diff


class ProjectError(Exception):
    pass


class ProjectFileNotFoundError(FileNotFoundError):
    pass


class ProjectExistsError(FileExistsError):
    pass
