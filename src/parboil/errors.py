"""Collection of common errors."""


class ParboilError(Exception):
    pass


class RecipeError(ParboilError):
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


class RepositoryError(ParboilError):
    def __init__(self, msg, repository):
        self.repository = repository


class RecipeNotInstalledError(RepositoryError):
    def __init__(self, template, repository):
        self.repository = repository
        super().__init__(f"Project {template} not installed.")


class BoilerError(ParboilError):
    pass


class TaskExecutionError(ParboilError):
    def __init__(self, task, msg: str = None):
        self.task = task

        if not msg:
            msg = f"Error executing task: <{task.quoted()}>"
        super().__init__(msg)


class TaskFailedError(ParboilError):
    def __init__(self, task, msg: str = None):
        self.task = task

        if not msg:
            msg = f"Task exited with error code {task.returncode}: <{task.quoted()}>"
        super().__init__(msg)
