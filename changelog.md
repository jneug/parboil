## Version 0.9.3

- Updated dependencies

### Version 0.7.7

- Moved to Poetry for project management

### Version 0.7.6

- Added `time` filter for strings to allow usage in conditionals (e.g. `{% if '%m'|time|int < 8 %}`).
- Added `roman` filter to convert integer into roman numeral (e.g. `{{ 5|roman }}`).
- Jinja compilation of user, prefilled and default values.
- Environment variables available in templates with the `ENV` variable.

### Version 0.7.5

- Fixed file renaming via project.json.
- Added short help for commands.
