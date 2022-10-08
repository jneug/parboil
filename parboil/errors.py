# -*- coding: utf-8 -*-
"""Collection of common errors."""


class ProjectError(Exception):
    pass


class ProjectFileNotFoundError(FileNotFoundError):
    pass


class ProjectExistsError(FileExistsError):
    pass
