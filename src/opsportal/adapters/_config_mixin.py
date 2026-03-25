"""Shared config mixin for adapters that use JSON Schema-backed config files.

Handles: loading schema, reading/writing JSON, validating via the app's own
validator, and masking sensitive fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from opsportal.adapters.base import ActionResult, ConfigValidationResult
from opsportal.core.errors import get_logger

logger = get_logger("adapters._config_mixin")

# Keys whose values should be masked when returned to the frontend
_SENSITIVE_KEYS = frozenset(
    {
        "auth_token",
        "token",
        "secret",
        "password",
        "api_key",
        "auth_email",
    }
)

_MASK = "••••••••"


def _mask_sensitive(data: Any, *, depth: int = 0) -> Any:
    """Recursively mask values of sensitive keys in a dict tree."""
    if depth > 20:
        return data
    if isinstance(data, dict):
        return {
            k: (
                _MASK
                if k in _SENSITIVE_KEYS and isinstance(v, str) and v
                else _mask_sensitive(v, depth=depth + 1)
            )
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_mask_sensitive(item, depth=depth + 1) for item in data]
    return data


def _unmask_merge(new_data: Any, original: Any, *, depth: int = 0) -> Any:
    """Replace masked placeholder values with the original values."""
    if depth > 20:
        return new_data
    if isinstance(new_data, dict) and isinstance(original, dict):
        merged = {}
        for k, v in new_data.items():
            if v == _MASK and k in original:
                merged[k] = original[k]
            else:
                merged[k] = _unmask_merge(v, original.get(k), depth=depth + 1)
        return merged
    if isinstance(new_data, list) and isinstance(original, list):
        return [
            _unmask_merge(n, o, depth=depth + 1) for n, o in zip(new_data, original, strict=False)
        ] + new_data[len(original) :]
    return new_data


class JsonSchemaConfigMixin:
    """Mixin providing JSON Schema-driven config read/write/validate.

    Subclasses must set:
      _config_file: str
      _schema_paths: list[Path]  (candidate locations for the JSON Schema file)
      _validate_fn: callable(data: dict) -> list[str] | raises
                    OR set to None to use raw jsonschema validation

    And should have either:
      _repo_path: Path | None
      _work_dir: Path | None

    Optionally override:
      _builtin_default_config: dict | None — hardcoded fallback when no schema exists
    """

    _repo_path: Path | None
    _work_dir: Path | None
    _config_file: str
    _schema_paths: list[Path]
    _validate_fn: Any  # callable or None
    _builtin_default_config: dict[str, Any] | None = None

    def _resolve_config_path(self) -> Path:
        """Resolve config file: repo_path → work_dir → CWD."""
        if self._repo_path:
            return self._repo_path / self._config_file
        if self._work_dir:
            return self._work_dir / self._config_file
        return Path.cwd() / self._config_file

    def _find_schema_file(self) -> Path | None:
        for p in self._schema_paths:
            if p.exists():
                return p
        return None

    def config_file_path(self) -> Path | None:
        p = self._resolve_config_path()
        return p if p.exists() else None

    def scaffold_default_config(self) -> bool:
        """Create a default config from schema defaults or built-in template.

        Returns True if a file was created, False otherwise.

        Strategy:
        1. Try schema-derived defaults (best: schema-validated)
        2. Fall back to built-in default config (always available)
        """
        if self.config_file_path() is not None:
            return False

        defaults = self._derive_defaults_from_schema()
        if not defaults:
            defaults = self._builtin_default_config

        if not defaults:
            return False

        return self._write_config_file(defaults)

    def _derive_defaults_from_schema(self) -> dict[str, Any] | None:
        """Extract defaults from JSON Schema, if schema exists and covers required fields."""
        schema = self.config_schema()
        if not schema:
            return None

        required = set(schema.get("required", []))
        props = schema.get("properties", {})
        defaults: dict[str, Any] = {}
        for key, prop in props.items():
            if "default" in prop:
                defaults[key] = prop["default"]

        if not defaults:
            return None

        missing_required = required - set(defaults.keys())
        if missing_required:
            logger.debug(
                "Schema defaults incomplete: required fields %s have no defaults",
                missing_required,
            )
            return None

        return defaults

    def _write_config_file(self, data: dict[str, Any]) -> bool:
        """Write config data to the resolved config path."""
        config_path = self._resolve_config_path()
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            logger.info(
                "Scaffolded default config at %s (%d fields)",
                config_path.name,
                len(data),
            )
            return True
        except Exception:
            logger.exception("Failed to scaffold default config")
            return False

    def config_schema(self) -> dict[str, Any] | None:
        schema_path = self._find_schema_file()
        if not schema_path:
            return None
        try:
            return json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to load schema from %s", schema_path)
            return None

    def get_config(self) -> dict[str, Any]:
        config_path = self._resolve_config_path()
        if not config_path.exists():
            return {}
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            return _mask_sensitive(data)
        except Exception:
            logger.exception("Failed to read config from %s", config_path)
            return {}

    def _read_raw_config(self) -> dict[str, Any]:
        """Read config without masking (for internal use)."""
        config_path = self._resolve_config_path()
        if not config_path.exists():
            return {}
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def validate_config(self, data: dict[str, Any]) -> ConfigValidationResult:
        # Merge masked values with originals before validation
        original = self._read_raw_config()
        merged = _unmask_merge(data, original)

        if self._validate_fn is not None:
            try:
                result = self._validate_fn(merged)
                # Some validators return a list of errors/warnings
                if isinstance(result, list):
                    error_strings = [str(getattr(w, "message", w)) for w in result]
                    if error_strings:
                        return ConfigValidationResult(valid=False, errors=error_strings)
                    return ConfigValidationResult(valid=True)
                # Some validators return None on success
                return ConfigValidationResult(valid=True)
            except Exception as exc:
                errors = getattr(exc, "errors", None) or [str(exc)]
                return ConfigValidationResult(valid=False, errors=list(errors))

        # Fallback: raw jsonschema validation
        schema = self.config_schema()
        if schema:
            import jsonschema

            validator = jsonschema.Draft7Validator(schema)
            errors = []
            for err in sorted(validator.iter_errors(merged), key=lambda e: list(e.path)):
                path = ".".join(str(p) for p in err.absolute_path) or "(root)"
                errors.append(f"{path}: {err.message}")
            if errors:
                return ConfigValidationResult(valid=False, errors=errors)
        return ConfigValidationResult(valid=True)

    def save_config(self, data: dict[str, Any]) -> ActionResult:
        config_path = self._resolve_config_path()

        # Merge masked values with originals
        original = self._read_raw_config()
        merged = _unmask_merge(data, original)

        # Validate first
        vr = self.validate_config(merged)
        if not vr.valid:
            return ActionResult(
                success=False,
                error=f"Validation failed: {'; '.join(vr.errors[:5])}",
            )

        # Write atomically
        try:
            tmp = config_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            tmp.replace(config_path)
            logger.info("Config saved to %s", config_path)
            return ActionResult(success=True, output=f"Configuration saved to {config_path.name}")
        except Exception as exc:
            logger.exception("Failed to save config to %s", config_path)
            return ActionResult(success=False, error=str(exc))
