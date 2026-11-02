"""Tests du gateway : chaîne de secours, sorties structurées, embeddings, profils."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from llm_gateway import FakeProvider, Gateway, GatewaySettings, LLMError, StructuredOutputError
from llm_gateway.profiles import HardwareInfo, choose_profile_name, load_profile
from llm_gateway.providers.anthropic_provider import AnthropicProvider
from llm_gateway.providers.openai_compat import OpenAICompatProvider
from llm_gateway.schema_utils import example_from_schema, extract_json, strict_schema
from pydantic import BaseModel


class Composant(BaseModel):
    reference: str
    categorie: str
    tension_v: float | None = None


def test_fake_rule_and_schema_fallback():
    fake = FakeProvider({"dht22": {"reference": "DHT22", "categorie": "capteur"}})
    gw = Gateway.fake(fake)
    c = gw.structured("Identifie le DHT22", schema=Composant)
    assert c.reference == "DHT22"
    # Sans règle : instance générée depuis le schéma
    c2 = gw.structured("autre chose", schema=Composant)
    assert isinstance(c2, Composant)


def test_fallback_to_next_provider_and_stats():
    gw = Gateway([FakeProvider(fail=True), FakeProvider(default_text="ok")], load_profile("cpu"))
    result = gw.complete("bonjour")
    assert result.text == "ok"
    assert result.fallback_from == ["fake"]
    assert gw.stats["fallback"] == 1
    assert gw.stats["failure:fake"] == 1


def test_all_providers_fail():
    gw = Gateway([FakeProvider(fail=True)], load_profile("cpu"))
    with pytest.raises(LLMError):
        gw.chat("x")


def test_structured_retry_then_error():
    fake = FakeProvider(responder=lambda req: "pas du json")
    gw = Gateway.fake(fake)
    with pytest.raises(StructuredOutputError):
        gw.structured("x", schema=Composant, retries=1)
    assert len(fake.calls) == 2
    assert gw.stats["structured_retry"] == 2


def test_vision_role_and_media_type():
    fake = FakeProvider(default_text="Un ESP32")
    gw = Gateway.fake(fake)
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 10
    assert gw.vision("Que vois-tu ?", images=[png]) == "Un ESP32"
    assert fake.calls[0].role == "vision"
    assert fake.calls[0].images[0].media_type == "image/png"


def test_embeddings_deterministic_and_similar():
    gw = Gateway.fake()
    a, b, c = gw.embed(["capteur de température", "capteur de température", "moteur pas à pas"])
    assert a == b
    dot_ab = sum(x * y for x, y in zip(a, b, strict=True))
    dot_ac = sum(x * y for x, y in zip(a, c, strict=True))
    assert dot_ab > dot_ac


def test_schema_utils():
    s = strict_schema(Composant.model_json_schema())
    assert s["additionalProperties"] is False
    assert set(s["required"]) == {"reference", "categorie", "tension_v"}
    assert "title" not in s
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('<think>hmm</think> voilà {"a": 2} fin') == {"a": 2}
    with pytest.raises(ValueError):
        extract_json("rien")
    ex = example_from_schema({"type": "array", "items": {"enum": ["x", "y"]}, "minItems": 2})
    assert ex == ["x", "x"]


@pytest.mark.parametrize(
    ("hw", "expected"),
    [
        (HardwareInfo("Darwin", "arm64", 16.0), "mac-m4-16"),
        (HardwareInfo("Windows", "amd64", 128.0, "RTX 4060", 8.0), "gpu-8gb"),
        (HardwareInfo("Windows", "amd64", 12.0, "RTX 3060 Laptop", 6.0), "gpu-6gb"),
        (HardwareInfo("Linux", "x86_64", 8.0), "cpu"),
    ],
)
def test_profile_choice(hw, expected):
    assert choose_profile_name(hw) == expected
    profile = load_profile(expected)
    assert profile.model_for("ollama", "vision")
    assert profile.model_for("anthropic", "text") == "claude-opus-5-5"


def test_unknown_profile():
    with pytest.raises(ValueError):
        load_profile("inexistant")


def test_openai_compat_payload_and_fallback_on_http_error():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen["body"] = body
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"reference":"BME280","categorie":"capteur","tension_v":3.3}'
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatProvider("ollama", "http://x/v1", client=client)
    gw = Gateway([provider], load_profile("gpu-8gb"))
    c = gw.structured("photo", schema=Composant, images=[b"\xff\xd8\xff" + b"0" * 5])
    assert c.reference == "BME280"
    body = seen["body"]
    assert body["model"] == "qwen3-vl:8b"
    assert body["response_format"]["type"] == "json_schema"
    assert body["messages"][1]["content"][1]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,"
    )
    assert gw.embed(["a"]) == [[0.1, 0.2]]

    down = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503, text="down")))
    gw2 = Gateway(
        [
            OpenAICompatProvider("ollama", "http://x/v1", client=down),
            FakeProvider(default_text="secours"),
        ],
        load_profile("cpu"),
    )
    assert gw2.chat("x") == "secours"


def test_anthropic_provider_with_stub_client():
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            stop_reason="end_turn",
            model=kwargs["model"],
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(
                    type="text", text='{"reference":"SG90","categorie":"servo","tension_v":5}'
                ),
            ],
            usage=SimpleNamespace(input_tokens=12, output_tokens=7),
        )

    stub = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    provider = AnthropicProvider(api_key=None, client=stub)
    assert provider.is_configured()
    gw = Gateway([provider], load_profile("cpu"))
    c = gw.structured("servo ?", schema=Composant, images=[b"\x89PNG\r\n\x1a\nxx"])
    assert c.reference == "SG90"
    assert captured["model"] == "claude-opus-5-5"
    assert captured["fallbacks"] == "default"
    assert captured["output_config"]["format"]["type"] == "json_schema"
    assert captured["messages"][0]["content"][0]["type"] == "image"


def test_anthropic_refusal_falls_through():
    def create(**kwargs):
        return SimpleNamespace(
            stop_reason="refusal", stop_details=SimpleNamespace(category="cyber"), content=[]
        )

    stub = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    gw = Gateway(
        [AnthropicProvider(None, client=stub), FakeProvider(default_text="ok")], load_profile("cpu")
    )
    assert gw.chat("x") == "ok"


def test_from_settings_skips_unconfigured(monkeypatch):
    settings = GatewaySettings(LLM_CHAIN="gemini,anthropic,inconnu,fake", LLM_PROFILE="cpu")
    gw = Gateway.from_settings(settings)
    assert [p.name for p in gw.providers] == ["fake"]


def test_cli_doctor(capsys, monkeypatch):
    from llm_gateway.cli import main

    monkeypatch.setenv("LLM_CHAIN", "fake")
    monkeypatch.setenv("LLM_PROFILE", "cpu")
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "Profil" in out and "fake" in out
    assert main(["ask", "bonjour"]) == 0
