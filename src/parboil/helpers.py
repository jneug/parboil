import os
import typing as t
from pathlib import Path


def load_files(dir: Path) -> t.Generator[Path, None, None]:
    for root, dirs, files in os.walk(dir):
        root_path = Path(root)
        for name in files:
            yield root_path.relative_to(dir) / name


def eval_bool(
    value: t.Any, true_values: t.Sequence[str] = ("yes", "true", "y", "1", "ja", "on")
) -> bool:
    return str(value).lower() in true_values
