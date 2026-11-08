# Capabilities rule (already reflected in AGENTS.md principle 6)

Model limits and features are runtime configuration, never constants. Each provider exposes a capabilities object
(max_input_tokens, max_output_tokens, tools, reasoning/effort, structured_outputs, image_input), read from the provider's
models endpoint when available, otherwise from config. The context assembler, UI (attach/image buttons, effort selector)
and agent loop adapt to these values. Today's QVELT server is small (about 2K context, 256 output tokens, no tools); the
app must work with it and with a 1M-context model without code changes.
