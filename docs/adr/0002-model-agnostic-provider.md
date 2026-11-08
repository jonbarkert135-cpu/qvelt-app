# ADR-0002: Model-agnostic provider interface
Status: accepted

## Context
The product must work with external models today and with QVELT models later, without rewriting domain logic.

## Decision
All inference goes through a `ModelProvider` interface with a stable internal message format
(text, tool_use, tool_result blocks) and a capabilities object
(max_input_tokens, max_output_tokens, tools, reasoning/effort levels, structured outputs, image input).
Providers: `FakeProvider` (deterministic, for tests and UI work), `OpenAICompatibleProvider`
(vLLM and any /v1/chat/completions server). Provider-specific quirks stay inside adapters.

## Consequences
UI and orchestrator adapt to capabilities at runtime. Provider limits are never hard-coded.
A QVELT-specific provider must send only fields its server supports (the current server rejects unknown fields)
and must not return model reasoning inside `content` when replaying history.
