# -*- coding: utf-8 -*-


"""setup.py: setuptools control."""


from setuptools import setup

setup(
    install_requires=["click", "colorama", "jinja2"],
    entry_points={"console_scripts": ["boil = parboil.parboil:boil"]},
)
