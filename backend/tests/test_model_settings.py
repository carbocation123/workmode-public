from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch


class ModelSettingsApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.saved_env = {
            name: os.environ.get(name)
            for name in (
                "WORKMODE_ENV_FILE",
                "WORKMODE_MODEL_BASE_URL",
                "WORKMODE_MODEL_API_KEY",
                "WORKMODE_MODEL_NAME",
            )
        }
        os.environ["WORKMODE_ENV_FILE"] = os.path.join(self.tmp.name, ".env")
        os.environ.pop("WORKMODE_MODEL_BASE_URL", None)
        os.environ.pop("WORKMODE_MODEL_API_KEY", None)
        os.environ.pop("WORKMODE_MODEL_NAME", None)

        from app import config
        from app.main import app
        from fastapi.testclient import TestClient

        config.reload_settings()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        from app import config

        for name, value in self.saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        config.reload_settings()
        self.tmp.cleanup()

    def test_model_connection_test_uses_unsaved_draft_without_persisting_it(self) -> None:
        probe = AsyncMock(
            return_value={
                "ok": True,
                "message": "模型连接成功",
                "model": "research-model",
                "latency_ms": 42,
            }
        )
        with patch("app.routes.probe_openai_compatible", probe):
            response = self.client.post(
                "/api/settings/model/test",
                json={
                    "model_base_url": "https://example.invalid/v1/",
                    "model_api_key": "draft-secret",
                    "model_name": "research-model",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["latency_ms"], 42)
        probe.assert_awaited_once_with(
            base_url="https://example.invalid/v1",
            api_key="draft-secret",
            model_name="research-model",
            timeout_seconds=120.0,
        )
        self.assertFalse(os.path.exists(os.environ["WORKMODE_ENV_FILE"]))

    def test_model_connection_test_rejects_missing_api_key(self) -> None:
        response = self.client.post(
            "/api/settings/model/test",
            json={
                "model_base_url": "https://example.invalid/v1",
                "model_name": "research-model",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("API Key", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
