# Parboil - Project Boilerplate Generator

![GitHub](https://img.shields.io/github/license/jneug/parboil)

> With _Parboil_ you can create reusable boilerplate templates to kickstart your next project.

<small>_Parboil_ is a Python rewrite of [boilr](https://github.com/tmrts/boilr) by [Tamer Tas](https://github.com/tmrts)</small>

----

## Installation

Install **Python 3** and then _Parboil_ with **pip**:

```
pip install parboil
```

_Parboil_ will install a `boil` command on your system. Run `boil --version` to see, if it worked.

## Getting started

Use `boil --help` to see the list of available commands and `boil <command> --help` to see usage information for any command.

### Installing your first template

_Parboil_ maintains a local repository of project templates. To use _Parboil_ you first need to install a template. You can install templates from a local directory or download them from GitHub.

For your first template install `jneug/parboil-template` from GitHub - a project template to create parboil project templates.

```
boil install -d jneug/parboil-template pbt
```

This will install the template from [`jneug/parboil-template`](https://github.com/jneug/parboil-template) and makes it available under the name `pbt`. (The `-d` flag tells parboil, that you want to download from GitHub and not from a local directory.)

Verify the install with `boil list`.

### Using a template

To use your new template run

```
boil use pbt new_template
```

This will create the boilerplate project in the `new_template` directory. (Omitting the directory will add the template to the current working dir.) _Parboil_ asks you to input some data and then writes the project files.

### Creating your first template

The parboil-template is a good startign point to create your own template. _Parboil_ uses [Jinja2](https://jinja.palletsprojects.com) to parse the template files and dynamically insert the user information into the template files.

For more information read the wiki page on template creation.
