# -*- coding: utf-8 -*-

import os
import re
import subprocess
import json
import shutil
import time
import tempfile
from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, PrefixLoader

import parboil.fields as fields
from .ext import JinjaTimeExtension, jinja_filter_fileify, jinja_filter_slugify, jinja_filter_roman, jinja_filter_time


PRJ_FILE = "project.json"
META_FILE = ".parboil"


class Project(object):
    def __init__(self, name, repository):
        self._name = name
        if type(repository) is Repository:
            self._repo = repository
            self._root_dir = (repository.root / self._name).resolve()
        else:
            self._repo = None
            self._root_dir = (Path(repository) / self._name).resolve()
        # Cache for jinja environment
        self._jinja = None

    @property
    def name(self):
        return self._name

    @property
    def root(self):
        return self._root_dir

    def exists(self):
        return self._root_dir.is_dir()

    def is_project(self):
        return self.exists() and (self._root_dir / PRJ_FILE).is_file()

    def setup(self, load_project=False):
        # setup config files and paths
        self.project_file = self._root_dir / PRJ_FILE
        self.meta_file = self._root_dir / META_FILE
        self.templates_dir = self._root_dir / "template"
        self.includes_dir = self._root_dir / "includes"

        self.meta = dict()
        self.files = dict()
        self.fields = dict()
        self.variables = dict()
        self.templates = list()
        self.includes = list()

        self.templates = list()
        for root, dirs, files in os.walk(self.templates_dir):
            root = Path(root).resolve()
            for name in files:
                dirname = root.relative_to(self.templates_dir)
                self.templates.append(dirname / name)

        self.includes = list()
        for root, dirs, files in os.walk(self.includes_dir):
            root = Path(root).resolve()
            for name in files:
                dirname = root.relative_to(self.includes_dir)
                self.includes.append(dirname / name)

        if load_project:
            self.load()

    def load(self):
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
                    self.fields[k] = v

        ## metafile
        if self.meta_file.is_file():
            with open(self.meta_file) as f:
                self.meta = {**self.meta, **json.load(f)}

    def fill(self, prefilled=dict(), jinja=None):
        """Read user input (if necessary)"""

        if not jinja:
            jinja = self._create_jinja()

        for key, descr in self.fields.items():
            value = None
            if key in prefilled:
                value = jinja.from_string(prefilled[key]).render(
                    **self.variables, BOIL=dict(TPLNAME=self._name),
                    ENV=os.environ
                )

            if type(descr) is dict and "type" in descr:
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
                        if 'default' in descr:
                            descr['default'] = jinja.from_string(descr['default']).render(
                                **self.variables, BOIL=dict(TPLNAME=self._name),
                                ENV=os.environ
                            )

                        # Ask for user input
                        self.variables[key] = getattr(fields, field_callable)(
                            key=key, **descr, value=value, project=self
                        )

                        # Send the variable through another jinja pass, if
                        # the user put some tags into the value.
                        self.variables[key] = jinja.from_string(self.variables[key]).render(
                            **self.variables, BOIL=dict(TPLNAME=self._name),
                            ENV=os.environ
                        )

    def compile(self, target_dir, jinja=None):
        if not jinja:
            jinja = self._create_jinja()

        target_dir = Path(target_dir).resolve()

        result = (list(), list())
        for file in self.templates:
            if type(file) is Project:
                for result in file.compile(target_dir):
                    yield result
            else:
                file_in = Path(str(file).removeprefix('includes:'))
                file_out = file_in
                if str(file_in) in self.files:
                    if 'filename' in self.files[str(file_in)]:
                        file_out = self.files[str(file_in)]['filename']

                rel_path = file_in.parent
                abs_path = target_dir / rel_path

                # Set some dynamic values
                boil_vars = dict(
                    TPLNAME=self._name,
                    RELDIR="" if rel_path.name == "" else str(rel_path),
                    ABSDIR=str(abs_path),
                    OUTDIR=str(target_dir),
                    OUTNAME=str(target_dir.name)
                )

                path_render = jinja.from_string(str(file_out)).render(
                    **self.variables, BOIL=boil_vars, ENV=os.environ
                )

                boil_vars["FILENAME"] = Path(path_render).name
                boil_vars["FILEPATH"] = path_render

                # Render template
                tpl_render = jinja.get_template(str(file)).render(
                    **self.variables, BOIL=boil_vars, ENV=os.environ
                )

                generate_file = bool(tpl_render.strip())  # empty?
                generate_file = self.files.get(str(file_in), dict()).get(
                    "keep", generate_file
                )

                if generate_file:
                    path_render_abs = target_dir / path_render
                    if not path_render_abs.parent.exists():
                        path_render_abs.parent.mkdir(parents=True)

                    with open(path_render_abs, "w") as f:
                        f.write(tpl_render)

                    yield (True, str(file), path_render)
                else:
                    yield (False, str(file), "")

    def _create_jinja(self):
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
            self._jinja.filters["roman"]   = jinja_filter_roman
            self._jinja.filters["time"]    = jinja_filter_time

        return self._jinja

    def save(self):
        """Saves the current meta file to disk"""
        if self.meta_file:
            with open(self.meta_file, "w") as f:
                json.dump(self.meta, f)

    def update(self, hard=False):
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
    def __init__(self, root):
        self._root = Path(root)
        self.load()

    @property
    def root(self):
        return self._root

    def exists(self):
        return self._root.is_dir()

    def load(self):
        self._projects = list()
        if self.exists():
            for child in self._root.iterdir():
                if child.is_dir():
                    project_file = child / PRJ_FILE
                    if project_file.is_file():
                        self._projects.append(child.name)

    def __len__(self):
        return len(self._projects)

    def __iter__(self):
        yield from self._projects

    def is_installed(self, template):
        tpl_dir = self._root / template
        return tpl_dir.is_dir()
        # return Project(template, self).exists()

    def projects(self):
        for prj in self._projects:
            yield self.get_project(prj)

    def get_project(self, template):
        return Project(template, self)

    def install_from_directory(self, template, source, hard=False, is_repo=False):
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

            # copy files
            shutil.copytree(source, project.root)

            # create meta file
            project.setup()
            project.meta = {
                "created": time.time(),
                "source_type": "local",
                "source": str(source),
            }
            project.save()

            self.load()
            return project
        else:
            projects = list()

            for child in source.iterdir():
                if child.is_dir():
                    project_file = child / PRJ_FILE
                    if project_file.is_file():
                        try:
                            project = self.install_from_directory(
                                child.name, child, hard=hard
                            )
                            projects.append(project)
                        except:
                            pass

            self.load()
            return projects

    def install_from_github(self, template, url, hard=False, is_repo=False):
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
            return project
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
                                )
                                # remove source data
                                del project.meta["source_type"]
                                del project.meta["source"]
                                project.save()

                                projects.append(project)
                            except:
                                pass

            self.load()
            return projects

    def uninstall(self, template):
        self._delete(template)

    def _delete(self, template):
        """Delete a project template from this repository."""
        tpl_dir = self._root / template
        if tpl_dir.is_dir():
            if tpl_dir.is_symlink():
                tpl_dir.unlink()
            else:
                shutil.rmtree(tpl_dir)

    def _reload(self):
        diff = list()
        for child in self._root.iterdir():
            if child.is_dir():
                project_file = child / PRJ_FILE
                if project_file.is_file():
                    if not child.name in self._projects:
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
