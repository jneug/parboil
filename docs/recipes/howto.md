## A first example

Project templates are folders with a simple structure:

```
blog-article
├──template
│  └──{% time '%Y-%m-%d' %}_{{ Title|sluggify }}.md
└──project.json
```

This defines a template named `blog-article` that creates a file named with the current date and the sluggified title for the blog post (`2021-03-03_how-to-write-a-template.md`). The content of `{% time '%Y-%m-%d' %}_{{ Title|sluggify }}.md` might look like this:

```
---
title:{{ Title|title }}
date:{% time '%c' %}
---

# {{ Title|title }}


```

`{{ Title }}` and `{% time %}` are special tags that get replaced with other values when the template is used.

`project.json`might look like this:

```
{
    "fields": {
        "Title": ""
    }
}
```

This lets **parboil** know, that the user should enter a title when the template is used. The value entered by the user is then parsed into the `.md` file above.

## project.json

The `project.json` file is required to let **parboil** know, that the folder is a project template. Even, if it contains no other information. An empty `project.json` file is still valid.

For most templates the project file defines the fields, that the user needs to input to generate the template files. But it can also define more complex actions like renaming files.

The basic structure of a project file is

```
{
    "fields": {
        // Field descriptions
    }
}
```

The `fields` key is a dict of field keys, that should dynamically be replaced in all template files and filenames. The values are the defaults to suggest to the user.

### Meta values

Parboil provides some metadata to templates about the project in the `BOIL` dict:

- `BOIL.TPLNAME` Name of the current template.
- `BOIL.RELDIR` Relative path to the directory of the current template file.
- `BOIL.ABSDIR` Absolute path to the current files directory.
- `BOIL.OUTDIR` Absolute path to the output directory.
- `BOIL.OUTNAME` Name of the output directory (last part of `BOIL.OUTDIR`).
- `BOIL.FILEPATH` Absolute path to the current file (after parsing).
- `BOIL.FILENAME` Name of the current template file (after parsing).

### Best practices

## Template files

### Renaming files

### Keeping empty files

Parboil will by default not generate empty files. This creates cleaner project boilerplates and allows for the conditional creation of different project versions. For example consider a boolean field `Version` that is entered by the user and two template files:

File `version-a.py`
```
{% if Version %}
My content for version A
{% endif %}
```

File `version-b.py`
```
{% if Version %}
My content for version B
{% endif %}
```

Depending on the value of `Version` either the file `version-a.py` or `version-b.py` is empty and will not be generated. You end up with a boilerplate of one file in either version a or b.

Sometimes this is not the desired behavior. For example your project template might look like this:

```
.
├──template
│  ├──test
│  │  └──.gitkeep
│  └──package.py
└──project.json
```

`.gitkeep` is an empty file by design, but Parboil will skip it anyway. To keep the file in the final boilerplate output, add the following to `project.json`:

```
{
  "files": {
    "test/.gitkeep": {
      "keep": true
    }
  }
}
```

## Includes

Next to the `template` folder you can create an `includes` folder. Files placed in there are not included by default, but can be included from other template files. This is useful for [template inheritance](https://jinja.palletsprojects.com/en/2.11.x/templates/#template-inheritance) or [template inclusion](https://jinja.palletsprojects.com/en/2.11.x/templates/#include). Just prefix the filename with `includes:` and Parboil will look for it in the `includes` folder.

```
.
├──includes
│  └──base.html
├──template
│  ├──page_1.html
│  └──page_2.html
└──project.json
```

`template/page_1.html`

```
{% extends "includes:base.html" %}

Some content
```

### Extending a base template

## Advanced usage

### File selection

### Including additional templates