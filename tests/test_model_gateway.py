import json
import os
import unittest
from unittest.mock import patch

from auris.model_gateway import (
    generate_reply,
    load_embedding_config,
    load_fast_model_config,
    load_model_config,
)


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps({"choices": [{"message": {"content": "Ready, Devansh."}}]}).encode()


class _OllamaResponse(_Response):
    def read(self):
        return json.dumps({"message": {"content": "Ready, Devansh."}}).encode()


class ModelGatewayTests(unittest.TestCase):
    def test_unconfigured_gateway_is_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(load_model_config().configured)

    def test_openai_compatible_gateway_extracts_reply(self):
        environment = {
            "AURIS_MODEL_PROVIDER": "openai_compatible",
            "AURIS_MODEL_ENDPOINT": "https://models.example.test/v1/chat/completions",
            "AURIS_MODEL_NAME": "reasoning-model",
            "AURIS_MODEL_API_KEY": "secret",
        }
        with patch.dict(os.environ, environment, clear=True), patch(
            "urllib.request.urlopen", return_value=_Response()
        ):
            reply = generate_reply(
                [{"role": "user", "content": "Are you online?"}],
                mode="command",
                project_name="AURIS One",
                project_instructions="Run tests.",
                memories=["Devansh prefers concise replies."],
            )

        self.assertEqual(reply.text, "Ready, Devansh.")
        self.assertEqual(reply.provider, "openai_compatible")

    def test_embeddings_are_restricted_to_loopback_ollama(self):
        with patch.dict(
            os.environ,
            {
                "AURIS_EMBEDDING_PROVIDER": "ollama",
                "AURIS_EMBEDDING_ENDPOINT": "https://models.example.test",
                "AURIS_EMBEDDING_MODEL": "nomic-embed-text",
            },
            clear=True,
        ):
            self.assertFalse(load_embedding_config().configured)

        with patch.dict(
            os.environ,
            {
                "AURIS_EMBEDDING_PROVIDER": "ollama",
                "AURIS_EMBEDDING_ENDPOINT": "http://127.0.0.1:11434",
                "AURIS_EMBEDDING_MODEL": "nomic-embed-text",
            },
            clear=True,
        ):
            self.assertTrue(load_embedding_config().configured)

    def test_ollama_command_profile_is_resident_and_bounded(self):
        environment = {
            "AURIS_MODEL_PROVIDER": "ollama",
            "AURIS_MODEL_ENDPOINT": "http://127.0.0.1:11434",
            "AURIS_MODEL_NAME": "gemma3:4b",
        }
        with patch.dict(os.environ, environment, clear=True), patch(
            "urllib.request.urlopen", return_value=_OllamaResponse()
        ) as urlopen:
            reply = generate_reply(
                [{"role": "user", "content": "Give me a concise update."}],
                mode="command",
                project_name="AURIS One",
                project_instructions="",
                memories=[],
            )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(reply.text, "Ready, Devansh.")
        self.assertEqual(payload["keep_alive"], "2h")
        self.assertEqual(payload["options"]["num_predict"], 96)
        self.assertEqual(payload["options"]["num_ctx"], 4096)

    def test_fast_route_is_explicit_local_and_uses_smaller_context(self):
        environment = {
            "AURIS_MODEL_PROVIDER": "ollama",
            "AURIS_MODEL_ENDPOINT": "http://127.0.0.1:11434",
            "AURIS_MODEL_NAME": "gemma3:4b",
            "AURIS_FAST_MODEL_NAME": "qwen2.5:1.5b",
        }
        with patch.dict(os.environ, environment, clear=True), patch(
            "urllib.request.urlopen", return_value=_OllamaResponse()
        ) as urlopen:
            self.assertTrue(load_fast_model_config().configured)
            reply = generate_reply(
                [{"role": "user", "content": "Tell me a joke."}],
                mode="command",
                project_name="AURIS One",
                project_instructions="",
                memories=[],
                latency_tier="fast",
            )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(reply.model, "qwen2.5:1.5b")
        self.assertEqual(reply.route, "fast")
        self.assertEqual(payload["model"], "qwen2.5:1.5b")
        self.assertEqual(payload["options"]["num_ctx"], 2048)

    def test_remote_fast_model_is_not_implicitly_trusted(self):
        with patch.dict(
            os.environ,
            {
                "AURIS_MODEL_PROVIDER": "ollama",
                "AURIS_MODEL_ENDPOINT": "http://127.0.0.1:11434",
                "AURIS_MODEL_NAME": "gemma3:4b",
                "AURIS_FAST_MODEL_ENDPOINT": "https://models.example.test",
                "AURIS_FAST_MODEL_NAME": "small-model",
            },
            clear=True,
        ):
            self.assertFalse(load_fast_model_config().configured)


if __name__ == "__main__":
    unittest.main()
