"""Translation proxy — single-file JSON translation preserving structure.

Delegates actual translation to LocaleSync's library classes (already
pip-installed as a dependency).  Accepts a single JSON object, flattens
it, translates string values, then reconstructs the original nesting.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import Any

from opsportal.core.errors import get_logger

logger = get_logger("services.translation_proxy")

# Supported target languages (subset matching LocaleSync / Google Translate)
SUPPORTED_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("pl", "Polski"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("pt", "Português"),
    ("nl", "Nederlands"),
    ("uk", "Українська"),
    ("cs", "Čeština"),
    ("ja", "日本語"),
    ("ko", "한국어"),
    ("zh-cn", "简体中文"),
    ("ru", "Русский"),
    ("ar", "العربية"),
    ("sv", "Svenska"),
    ("da", "Dansk"),
    ("fi", "Suomi"),
    ("nb", "Norsk Bokmål"),
    ("ro", "Română"),
    ("hu", "Magyar"),
    ("tr", "Türkçe"),
)


class TranslationProgress:
    """Thread-safe progress tracker for translation jobs."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.done = 0
        self.keys_translated = 0
        self.keys_skipped = 0
        self._lock = threading.Lock()

    def advance(self, *, translated: bool = True) -> None:
        with self._lock:
            self.done += 1
            if translated:
                self.keys_translated += 1
            else:
                self.keys_skipped += 1

    @property
    def percent(self) -> int:
        if self.total == 0:
            return 100
        return min(100, int(self.done / self.total * 100))


class TranslationProxy:
    """Translates a single JSON file preserving its structure.

    Uses LocaleSync's ``PlaceholderAwareTranslator`` wrapping
    ``GoogleTranslator`` to handle placeholder protection, retries,
    and language normalization — zero business logic duplication.
    """

    async def translate_json(
        self,
        json_data: dict[str, Any],
        target_language: str,
        source_language: str = "en",
    ) -> dict[str, Any]:
        """Translate all string values in *json_data*."""
        return await asyncio.to_thread(
            self._translate_sync, json_data, target_language, source_language
        )

    async def translate_json_with_progress(
        self,
        json_data: dict[str, Any],
        target_language: str,
        source_language: str = "en",
        on_progress: Callable[[TranslationProgress], Any] | None = None,
    ) -> dict[str, Any]:
        """Translate with progress callbacks from a background thread."""
        return await asyncio.to_thread(
            self._translate_sync, json_data, target_language, source_language, on_progress
        )

    @staticmethod
    def _translate_sync(
        json_data: dict[str, Any],
        target_language: str,
        source_language: str,
        on_progress: Callable[[TranslationProgress], Any] | None = None,
    ) -> dict[str, Any]:
        try:
            from locale_sync.domain.placeholder import PlaceholderManager
            from locale_sync.infrastructure.translators.google import GoogleTranslator
            from locale_sync.infrastructure.translators.placeholder_aware import (
                PlaceholderAwareTranslator,
            )
        except ImportError:
            return {
                "success": False,
                "error": "LocaleSync is not installed — translation unavailable",
                "translated_json": None,
                "keys_translated": 0,
                "keys_skipped": 0,
            }

        translator = PlaceholderAwareTranslator(GoogleTranslator(), PlaceholderManager())

        flat = _flatten_json(json_data)
        translated_flat: dict[str, Any] = {}

        progress = TranslationProgress(total=len(flat))

        for key, value in flat.items():
            if not isinstance(value, str) or not value.strip():
                translated_flat[key] = value
                progress.advance(translated=False)
            else:
                try:
                    translated_flat[key] = translator.translate(
                        value, source_language, target_language
                    )
                    progress.advance(translated=True)
                except Exception as exc:
                    logger.warning("Translation failed for key '%s': %s", key, exc)
                    translated_flat[key] = value
                    progress.advance(translated=False)

            if on_progress:
                on_progress(progress)

        result_json = _unflatten_json(translated_flat)

        return {
            "success": True,
            "translated_json": result_json,
            "keys_translated": progress.keys_translated,
            "keys_skipped": progress.keys_skipped,
            "error": "",
        }

    @staticmethod
    def count_translatable_keys(json_data: dict[str, Any]) -> int:
        """Count the total number of leaf keys (for progress estimation)."""
        return len(_flatten_json(json_data))

    @staticmethod
    def supported_languages() -> list[dict[str, str]]:
        return [{"code": code, "label": label} for code, label in SUPPORTED_LANGUAGES]


def _flatten_json(data: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested JSON to a dotted-key map, preserving non-dict leaves."""
    items: dict[str, Any] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            new_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                items.update(_flatten_json(value, new_key))
            else:
                items[new_key] = value
    return items


def _unflatten_json(flat: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct nested JSON from dotted-key flat map."""
    result: dict[str, Any] = {}
    for dotted_key, value in flat.items():
        parts = dotted_key.split(".")
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result
