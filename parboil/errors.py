# -*- coding: utf-8 -*-
"""Collection of common errors."""

from .tasks import Task


class ParboilError(Exception):
    pass


class ProjectError(ParboilError):
    pass


class ProjectFileNotFoundError(ProjectError):
    def __init__(self, msg="Project file not found."):
        super().__init__(msg)


class ProjectExistsError(ProjectError):
    def __init__(self, msg="Project file already exists."):
        super().__init__(msg)


class ProjectConfigError(ProjectError):
    pass


class TaskExecutionError(ParboilError):
    task: Task

    def __init__(self, task: Task, msg: str = None):
        self.task = task

        if not msg:
            msg = f"Error executing task: <{task.quoted()}>"
        super().__init__(msg)


class TaskFailedError(ParboilError):
    task: Task

    def __init__(self, task: Task, msg: str = None):
        self.task = task

        if not msg:
            msg = f"Task exited with error code {task.returncode}: <{task.quoted()}>"
        super().__init__(msg)
