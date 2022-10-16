# Parboil - Project Boilerplate Generator

!!! note

	**parboil** was created after I switched to a new MacBook Pro with M1 chip and [boilr](https://github.com/tmrts/boilr) stopped working for me. Since I wanted to learn how to publish on PYPI anyways, I decided to rewrite `boilr` in Python.

## Commands

Use `boil --help` to show all available commands. Or view help for a specific command with `boil <command> --help`. `boil --version` shows version information.

## General options

The following options can always be passed to the `boil` command to change the configuration file or the path to the local repository.

- `-c` / `--config <filepath>` - Passes a config file to use for this run instead of the default (`~/.config/parboil/config.json`).
- `--tpldir <dirpath>` - Sets the local repository path to load project templates from.

## install

To use a template you need to install it to the local repository first.

``` console
boil install <source> [templatename]
```

Options:
- `-f` / `--force` - Omits the confirmation prompt to overwrite an existing template by the same name.
- `-d` / `--download` - Treats `source` as the name of a GitHub repository instead of a local directory.
- `-r` / `--repo` - Installs a directory of project templates. Each directory inside `source` is installed to the local repository. For now this implies `-f`. Is `source` a GitHub repository, the templates can't be updated via `boil update`.

``` console
~$ boil install local/path/to/template tpl
[✓] Installed template tpl
    Use with boil use tpl
```

Templates can be installed from a local directory or an GitHub repository. You can install from GitHub with the repository name (for example `jneug/parboil-template`) by using the `-d` flag. (Otherwise **parboil** will assume `jneug/parboil-template` is a local directory.) If you provide a full repository url (`https://github.com/jneug/parboil`) the `-d` flag is not necessary.

```
~$ boil install -d jneug/parboil-template pbt
[✓] Installed template pbt
    Use with boil use pbt
```

An installed template is available to the `use` command as `[templatename]`. If no templatename is given, the templates directory name is used as a name.

```
~$ boil use pbt
```

If you want to install a bunch of project templates at once, you can use the `-r` flag on the top-level folder, to indicate to **parboil**, that all subfolders (with a valid `project.json` file) should be installed.

```
~$ boil install -r ~/parboil-templates
[✓] Installed flask-project to local repository
[✓] Installed click-project to local repository
[✓] Installed pychram-module to local repository
    Use with boil use <templatename>
```

This also works with GitHub:

```
~$ boil install -d -r jneug/parboil-templates
[✓] Installed ab to local repository
[✓] Installed cu to local repository
[✓] Installed kl to local repository
    Use with boil use <templatename>
```


## uninstall

To delete a package from the local repository use the `uninstall` command. This will simply remove the template directory and its content from the repository.

```bash
boil uninstall <templatename>
```

## use

```bash
boil use <templatename> [outdir]
```

Options:
- `-v <key> <value>` - Use `<value>` for the field `<key>` without prompting the user for input.
- `--hard` - Delete the `[outdir]` before generating the template files.

`use` is the heart of **parboil**. It requests values for each field from the user and compiles the template files into the output directory. If `[outdir]` is omitted, the current working directory is used.

Templates are used in two steps: 
1. First the required fields are read from `project.json` and parsed. For each field a [prefilled value](#prefilled-values) is looked up and if not given, the user is prompted for a value.
2. Each file in the `template` directory is renamed properly and compiled with Jinja into the output directory.

### Prefilled values

To speed up template creation for commonly used templates, you can provide values for specific keys beforehand, so that **parboil** does not need to ask for input every time. There are two ways to do this:
1. In your **parboil** config file (usually `~/.config/parboil/config.json`) add a `prefilled` key with a dictionary of key/value pairs.
2. Pass the key/value pairs to `boil use` with the `-v` option.

```json
{
        "prefilled": {
                "Autor": "J. Neugebauer",
                "Kuerzel": "Ngb"
        }
}
```

## list
The `list` command will show all available project templates in the local repository.

```bash
~$ boil list
[i] Listing templates in ~/.config/parboil/templates.

    ⎪     name     ⎪         created          ⎪         updated          ⎪
    |--------------⎪--------------------------⎪--------------------------|
    | pbt          | Sun Mar  7 16:25:00 2021 | Tue Mar  9 08:36:10 2021 |
    | python       | Wed Mar 10 14:33:42 2021 |                    never |
```

Add the `-p` flag to just list the templates one per line.

```bash
~$ boil list -p
pbt
python
```

## update

The `update` command attempts to update the template from its original source. 

*This will only work for templates installed with `boil install`, not for templates copied manually to the local repository.*

```bash
boil update <templatename>
```

Templates downloaded from GitHub will be updated by resetting and pulling the repository.

**Updating will overwrite any local changes!** If you want to keep those, you should create your own custom copy.

On install Parboil places a `.parboil` file inside the template directory that holds some meta information about the template. 

## How to write templates

