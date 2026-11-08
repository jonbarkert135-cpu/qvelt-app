"""Vendor-independent text stream contract; real adapters arrive in Phase 1.4."""
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ModelMessage:
    role: Literal["user", "assistant"]
    text: str


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int


class ModelProvider(Protocol):
    name: str

    def stream(self, messages: Sequence[ModelMessage]) -> AsyncGenerator[str | ModelUsage, None]: ...


class FakeProvider:
    """Deterministic echo with explicitly fake whitespace-token usage, never billing."""
    name = "fake"

    async def stream(self, messages: Sequence[ModelMessage]) -> AsyncGenerator[str | ModelUsage, None]:
        reply = "Echo (FakeProvider): " + messages[-1].text
        for offset in range(0, len(reply), 64):
            yield reply[offset:offset + 64]
        yield ModelUsage(sum(len(message.text.split()) for message in messages), len(reply.split()))
