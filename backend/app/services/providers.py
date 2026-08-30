from abc import ABC, abstractmethod

from pydantic import BaseModel


class ProviderResponse(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int
    model_tier: str


class ModelProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, prompt: str, *, model_tier: str = "small") -> ProviderResponse:
        ...


class MockProvider(ModelProvider):
    """Deterministic stand-in for a real LLM call. Round 2 explicitly allows
    simulated data, and a deterministic provider keeps the demo
    reproducible across runs and independent of any paid API key."""

    name = "mock"

    def generate(self, prompt: str, *, model_tier: str = "small") -> ProviderResponse:
        text = f"[mock-{model_tier}] response to: {prompt[:60]}"
        return ProviderResponse(
            text=text,
            input_tokens=max(len(prompt.split()), 1) * 2,
            output_tokens=40,
            model_tier=model_tier,
        )


class UnavailableProvider(ModelProvider):
    """Used when a real provider (OpenAI/Anthropic/Gemini) is configured but
    no API key is present. Fails loudly rather than silently falling back,
    so failures are visible for the fail-open/fail-closed policy to handle."""

    name = "unavailable"

    def generate(self, prompt: str, *, model_tier: str = "small") -> ProviderResponse:
        raise RuntimeError(f"Provider '{self.name}' has no credentials configured")


def get_provider(name: str = "mock") -> ModelProvider:
    if name == "mock":
        return MockProvider()
    return UnavailableProvider()
