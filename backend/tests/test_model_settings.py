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
                "WORKMODE_MINERU_API_KEY",
                "WORKMODE_MINERU_MODEL_VERSION",
                "WORKMODE_MINERU_LANGUAGE",
                "WORKMODE_MINERU_TIMEOUT_SECONDS",
                "WORKMODE_DASHSCOPE_API_KEY",
                "DASHSCOPE_API_KEY",
            )
        }
        os.environ["WORKMODE_ENV_FILE"] = os.path.join(self.tmp.name, ".env")
        os.environ.pop("WORKMODE_MODEL_BASE_URL", None)
        os.environ.pop("WORKMODE_MODEL_API_KEY", None)
        os.environ.pop("WORKMODE_MODEL_NAME", None)
        os.environ.pop("WORKMODE_MINERU_API_KEY", None)
        os.environ.pop("WORKMODE_MINERU_MODEL_VERSION", None)
        os.environ.pop("WORKMODE_MINERU_LANGUAGE", None)
        os.environ.pop("WORKMODE_MINERU_TIMEOUT_SECONDS", None)
        os.environ.pop("WORKMODE_DASHSCOPE_API_KEY", None)
        os.environ.pop("DASHSCOPE_API_KEY", None)

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

    def test_mineru_settings_are_persisted_without_echoing_the_secret(self) -> None:
        response = self.client.put(
            "/api/settings/mineru",
            json={
                "mineru_api_key": "mineru-secret",
                "mineru_model_version": "vlm",
                "mineru_language": "en",
                "mineru_timeout_seconds": 240,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        settings = response.json()["settings"]
        self.assertTrue(settings["mineru_api_key_set"])
        self.assertNotIn("mineru_api_key", settings)
        self.assertEqual(settings["mineru_model_version"], "vlm")
        self.assertEqual(settings["mineru_language"], "en")
        self.assertEqual(settings["mineru_timeout_seconds"], 240)
        with open(os.environ["WORKMODE_ENV_FILE"], encoding="utf-8") as handle:
            env_text = handle.read()
        self.assertIn("WORKMODE_MINERU_API_KEY=mineru-secret", env_text)
        self.assertIn("WORKMODE_MINERU_MODEL_VERSION=vlm", env_text)

    def test_mineru_settings_reject_unsupported_pdf_model(self) -> None:
        response = self.client.put(
            "/api/settings/mineru",
            json={"mineru_model_version": "MinerU-HTML"},
        )

        self.assertEqual(response.status_code, 422)

    def test_dashscope_settings_are_persisted_without_echoing_the_secret(self) -> None:
        response = self.client.put(
            "/api/settings/dashscope",
            json={"dashscope_api_key": "dashscope-secret"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        settings = response.json()["settings"]
        self.assertTrue(settings["dashscope_api_key_set"])
        self.assertNotIn("dashscope_api_key", settings)
        with open(os.environ["WORKMODE_ENV_FILE"], encoding="utf-8") as handle:
            env_text = handle.read()
        self.assertIn("WORKMODE_DASHSCOPE_API_KEY=dashscope-secret", env_text)

    def test_invalid_manual_mineru_environment_falls_back_to_safe_defaults(self) -> None:
        from app import config

        os.environ["WORKMODE_MINERU_MODEL_VERSION"] = "unknown"
        os.environ["WORKMODE_MINERU_LANGUAGE"] = "unknown"
        os.environ["WORKMODE_MINERU_TIMEOUT_SECONDS"] = "not-a-number"

        current = config.reload_settings()

        self.assertEqual(current.mineru_model_version, "pipeline")
        self.assertEqual(current.mineru_language, "en")
        self.assertEqual(current.mineru_timeout_seconds, 180)


if __name__ == "__main__":
    unittest.main()
