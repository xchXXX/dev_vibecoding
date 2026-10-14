import json
import os
from pathlib import Path
import platform

from .errors import HarnessError
from .paths import checked

FIELDS = {"codex_home": "CODEX_HOME", "skills_dir": "CODEX_SKILLS_DIR",
          "environment": "HARNESS_ENVIRONMENT"}


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise HarnessError("CONFIG_INVALID", "Duplicate configuration field: " + key)
        result[key] = value
    return result


def current_environment():
    if os.name == "nt":
        return "windows"
    return "wsl" if "microsoft" in platform.release().lower() else "linux"


def resolve_config(cli: dict, config_path: Path | None = None, environ=None) -> dict:
    environ = os.environ if environ is None else environ
    try:
        config_path = Path(config_path).absolute() if config_path is not None else None
        data = json.loads(config_path.read_text(encoding="utf-8-sig"),
                          object_pairs_hook=_unique_fields) if config_path else {}
    except (OSError, ValueError, TypeError) as error:
        raise HarnessError("CONFIG_INVALID", "Cannot read configuration JSON: " + type(error).__name__) from error
    for source in (cli, data):
        if not isinstance(source, dict) or set(source) - set(FIELDS):
            raise HarnessError("CONFIG_INVALID", "Only codex_home, skills_dir and environment are accepted")
        for key, value in source.items():
            if not isinstance(value, (str, Path)) or not str(value).strip():
                raise HarnessError("CONFIG_INVALID", "Nonempty path/string required for " + key)
    result, sources = {}, {}
    for key, variable in FIELDS.items():
        if key in cli:
            value, origin = cli[key], "cli"
        elif key in data:
            value, origin = data[key], "config"
        elif variable in environ:
            value, origin = environ[variable], "env"
        else:
            value, origin = None, "default"
        if key == "environment":
            value = "auto" if value is None else value
            if value not in {"auto", "windows", "linux", "wsl"}:
                raise HarnessError("CONFIG_INVALID", "environment must be auto/windows/linux/wsl")
            result[key] = current_environment() if value == "auto" else value
        else:
            if value is None:
                if key == "codex_home":
                    raise HarnessError("CONFIG_INVALID", "Set --codex-home or CODEX_HOME explicitly")
                value = result["codex_home"] / "skills"
            if not isinstance(value, (str, Path)) or not str(value).strip():
                raise HarnessError("CONFIG_INVALID", "Nonempty path required for " + key)
            value = Path(value)
            if not value.is_absolute() and origin == "config":
                value = config_path.parent / value
            result[key] = checked(value)
        sources[key] = origin
    result["sources"] = sources
    return result
