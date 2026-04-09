from __future__ import annotations

from typing import Protocol

JsonValue = dict[str, object] | list[object] | str | int | float | bool | None
JsonPayload = dict[str, JsonValue]


class ModelProvider(Protocol):
    def run(
        self, model_name: str, system_prompt: str, input_payload: JsonPayload
    ) -> JsonPayload:
        ...


class StubProvider:
    """Deterministic provider used until a real model backend is registered."""

    def run(
        self, model_name: str, system_prompt: str, input_payload: JsonPayload
    ) -> JsonPayload:
        return {
            "proposed_action": {
                "type": "wait",
                "piece_id": None,
                "target": None,
            },
            "message": f"Stub response from {model_name}.",
            "confidence": 0.0,
        }


_providers: dict[str, ModelProvider] = {
    "stub": StubProvider(),
}


def register_provider(name: str, provider: ModelProvider) -> None:
    if not name:
        raise ValueError("provider name cannot be empty")
    _providers[name] = provider


def run_agent(
    model_name: str, system_prompt: str, input_payload: JsonPayload
) -> JsonPayload:
    """Run an agent model through the configured provider.

    Use model names like "stub:default", "openai:gpt-5.4", or
    "local:my-model". The prefix selects the provider.
    """
    provider_name = _provider_name(model_name)
    provider = _providers.get(provider_name)
    if provider is None:
        raise ValueError(f"No provider registered for model: {provider_name}")

    return provider.run(model_name, system_prompt, input_payload)


def _provider_name(model_name: str) -> str:
    if ":" not in model_name:
        return "stub"
    return model_name.split(":", maxsplit=1)[0]
