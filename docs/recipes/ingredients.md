# Ingredients

The most important part of a parboil recipes are the *ingredients*. Ingredients is just a fancy term for "variables" that are input by the user on using a recipe.

Ingredients are key-value pairs in a recipes `parboil.json` configuration file.

!!! info

	There are currently four reserved keys that can't be used as ingredients: `_tasks`, `_files`, `_settings` and `_context`. Future version might add to this list. To avoid conflicts recipe authors should avoid using keys starting with an underscore `_`.

## Basic ingredients

Basic ingredients are simple key-value pairs. The key is the name of the variable passed to jinja. If the value is a simple datatype (string, boolean or number) it is used as a default value for the variable. If the value is a list, it is used as items in a [choice][] ingredient.
	
```json title="parboil.json"
{
	"Name": "String",
	"Toggle": false,
	"Number": 4,
	"Choice": [
		"Item 1",
		"Item 2",
		"Item 3"
	]
}
```

```shell
❯ boil use docs
[?] Enter a value for "Name"
    Name (String): My Name
[?] Do you want do enable "Toggle" [y/n] (n): y
[?] Enter a value for "Number"
    Number: 4
[?] Chose a value for "{{INGREDIENT.name}}"
    1 - Item 1
    2 - Item 2
    3 - Item 3
    Select from 1..3: 2
```

## choice
