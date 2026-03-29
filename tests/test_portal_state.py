"""Tests for PortalStateStore — persistence, rehydration, atomic writes."""

from __future__ import annotations

import json
from pathlib import Path

from opsportal.services.portal_state import PortalStateStore


class TestPortalStateStoreUnit:
    """Pure unit tests for the state store, no app or HTTP involved."""

    def test_defaults_when_no_file(self, tmp_path: Path) -> None:
        """GIVEN no state file on disk."""

        """WHEN creating a new PortalStateStore."""
        store = PortalStateStore(tmp_path / "portal_state.json")

        """THEN default values are applied and loaded_from_disk is False."""
        assert store.get("ops_overview_enabled") is False
        assert store.loaded_from_disk is False

    def test_set_and_persist(self, tmp_path: Path) -> None:
        """GIVEN a new PortalStateStore."""
        path = tmp_path / "portal_state.json"
        store = PortalStateStore(path)

        """WHEN setting ops_overview_enabled to True."""
        store.set("ops_overview_enabled", True)

        """THEN the value is persisted to disk with correct schema."""
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["state"]["ops_overview_enabled"] is True
        assert data["_schema_version"] == 1

    def test_load_from_existing_file(self, tmp_path: Path) -> None:
        """GIVEN a state file with ops_overview_enabled set to True."""
        path = tmp_path / "portal_state.json"
        path.write_text(
            json.dumps(
                {
                    "_schema_version": 1,
                    "state": {"ops_overview_enabled": True},
                }
            )
        )

        """WHEN creating a PortalStateStore from that file."""
        store = PortalStateStore(path)

        """THEN the persisted value is loaded."""
        assert store.get("ops_overview_enabled") is True
        assert store.loaded_from_disk is True

    def test_survives_simulated_restart(self, tmp_path: Path) -> None:
        """GIVEN a store that persisted ops_overview_enabled as True."""
        path = tmp_path / "portal_state.json"

        store1 = PortalStateStore(path)
        store1.set("ops_overview_enabled", True)
        del store1

        """WHEN creating a new store from the same file."""
        store2 = PortalStateStore(path)

        """THEN the value is restored from disk."""
        assert store2.get("ops_overview_enabled") is True
        assert store2.loaded_from_disk is True

    def test_set_many(self, tmp_path: Path) -> None:
        """GIVEN a new PortalStateStore."""
        path = tmp_path / "portal_state.json"
        store = PortalStateStore(path)

        """WHEN calling set_many with multiple keys."""
        store.set_many({"ops_overview_enabled": True, "custom_key": "hello"})

        """THEN all keys are persisted to disk."""
        data = json.loads(path.read_text())
        assert data["state"]["ops_overview_enabled"] is True
        assert data["state"]["custom_key"] == "hello"

    def test_reset_returns_to_defaults(self, tmp_path: Path) -> None:
        """GIVEN a store with ops_overview_enabled set to True."""
        path = tmp_path / "portal_state.json"
        store = PortalStateStore(path)
        store.set("ops_overview_enabled", True)

        """WHEN calling reset."""
        store.reset()

        """THEN all state reverts to defaults."""
        assert store.get("ops_overview_enabled") is False
        data = json.loads(path.read_text())
        assert data["state"]["ops_overview_enabled"] is False

    def test_corrupted_file_uses_defaults(self, tmp_path: Path) -> None:
        """GIVEN a corrupted JSON state file."""
        path = tmp_path / "portal_state.json"
        path.write_text("NOT VALID JSON {{{")

        """WHEN creating a PortalStateStore from that file."""
        store = PortalStateStore(path)

        """THEN defaults are used and loaded_from_disk is False."""
        assert store.get("ops_overview_enabled") is False
        assert store.loaded_from_disk is False

    def test_future_schema_version_uses_defaults(self, tmp_path: Path) -> None:
        """GIVEN a state file with a future schema version."""
        path = tmp_path / "portal_state.json"
        path.write_text(
            json.dumps(
                {
                    "_schema_version": 999,
                    "state": {"ops_overview_enabled": True},
                }
            )
        )

        """WHEN creating a PortalStateStore from that file."""
        store = PortalStateStore(path)

        """THEN defaults are used and loaded_from_disk is False."""
        assert store.get("ops_overview_enabled") is False
        assert store.loaded_from_disk is False

    def test_missing_keys_get_defaults(self, tmp_path: Path) -> None:
        """GIVEN a state file with an empty state dict."""
        path = tmp_path / "portal_state.json"
        path.write_text(
            json.dumps(
                {
                    "_schema_version": 1,
                    "state": {},
                }
            )
        )

        """WHEN creating a PortalStateStore from that file."""
        store = PortalStateStore(path)

        """THEN missing keys get default values."""
        assert store.get("ops_overview_enabled") is False
        assert store.loaded_from_disk is True

    def test_all_returns_copy(self, tmp_path: Path) -> None:
        """GIVEN a PortalStateStore with default values."""
        store = PortalStateStore(tmp_path / "portal_state.json")

        """WHEN calling all() and mutating the returned dict."""
        snapshot = store.all()
        snapshot["ops_overview_enabled"] = True

        """THEN the store's internal state is unaffected."""
        assert store.get("ops_overview_enabled") is False

    def test_atomic_write_creates_parent_dirs(self, tmp_path: Path) -> None:
        """GIVEN a deeply nested file path that does not exist."""
        path = tmp_path / "deep" / "nested" / "portal_state.json"

        """WHEN creating a store and setting a value."""
        store = PortalStateStore(path)
        store.set("ops_overview_enabled", True)

        """THEN the file and parent directories are created."""
        assert path.exists()


class TestPortalStatePersistenceEndToEnd:
    """Integration tests that simulate app restart with persistence."""

    def test_toggle_survives_app_restart(self, tmp_path: Path) -> None:
        """GIVEN a running app where ops_overview was toggled on."""
        from starlette.testclient import TestClient

        from opsportal.app.factory import create_app
        from opsportal.core.settings import PortalSettings

        manifest = tmp_path / "opsportal.yaml"
        manifest.write_text("tools: {}\n")
        work_dir = tmp_path / "work"

        settings1 = PortalSettings(
            host="127.0.0.1",
            port=9999,
            debug=False,
            log_level="warning",
            manifest_path=manifest,
            artifact_dir=tmp_path / "artifacts",
            work_dir=work_dir,
            tools_base_dir=tmp_path,
            ops_overview_enabled=False,
        )

        app1 = create_app(settings=settings1)
        with TestClient(app1) as client1:
            r = client1.get("/")
            csrf = r.cookies.get("opsportal_csrf", "")
            r = client1.put(
                "/api/config/ops-overview",
                json={"enabled": True},
                headers={"X-CSRF-Token": csrf},
            )
            assert r.json()["success"] is True
            assert r.json()["persisted"] is True

        state_file = work_dir / "portal_state.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text())
        assert data["state"]["ops_overview_enabled"] is True

        """WHEN restarting the app with default settings."""
        settings2 = PortalSettings(
            host="127.0.0.1",
            port=9999,
            debug=False,
            log_level="warning",
            manifest_path=manifest,
            artifact_dir=tmp_path / "artifacts",
            work_dir=work_dir,
            tools_base_dir=tmp_path,
            ops_overview_enabled=False,
        )

        app2 = create_app(settings=settings2)

        """THEN the toggled value is rehydrated from disk."""
        with TestClient(app2) as client2:
            # Settings were rehydrated from disk
            assert app2.state.settings.ops_overview_enabled is True

            r = client2.get("/api/config/ops-overview")
            assert r.json()["enabled"] is True

    def test_first_run_uses_env_defaults(self, tmp_path: Path) -> None:
        """GIVEN no state file and PortalSettings with ops_overview_enabled True."""
        from opsportal.app.factory import create_app
        from opsportal.core.settings import PortalSettings

        manifest = tmp_path / "opsportal.yaml"
        manifest.write_text("tools: {}\n")

        settings = PortalSettings(
            host="127.0.0.1",
            port=9999,
            debug=False,
            log_level="warning",
            manifest_path=manifest,
            artifact_dir=tmp_path / "artifacts",
            work_dir=tmp_path / "work",
            tools_base_dir=tmp_path,
            ops_overview_enabled=True,
        )

        """WHEN creating the app."""
        app = create_app(settings=settings)

        """THEN the env default is used and loaded_from_disk is False."""
        # Env says True, no disk override → True
        assert app.state.settings.ops_overview_enabled is True
        assert app.state.portal_state.loaded_from_disk is False
