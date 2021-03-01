# -*- coding: utf-8 -*-


"""setup.py: setuptools control."""


from setuptools import setup, find_packages
from distutils.util import convert_path

main_ns = {}
ver_path = convert_path('parboil/version.py')
with open(ver_path) as ver_file:
	exec(ver_file.read(), main_ns)


with open("README.md", "rb") as f:
    long_descr = f.read().decode("utf-8")


setup(
    name = "parboil",
    packages = ["parboil"],
    install_requires=[
        'click',
        'colorama',
        'jinja2'
    ],
    entry_points = {
        "console_scripts": ['boil = parboil.parboil:boil']
        },
    version=main_ns['__version__'],
    description = "Parboil lets you generate boilerplate projects from template files.",
    long_description = long_descr,
    long_description_content_type = 'text/markdown',
    author = "Jonas Neugebauer",
    author_email = "github@neugebauer.cc",
    url = "http://github.com/jneug/parboil",
    )
