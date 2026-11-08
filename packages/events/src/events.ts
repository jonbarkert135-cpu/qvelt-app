import { Type, type Static, type TProperties } from "@sinclair/typebox";
import { Value } from "@sinclair/typebox/value";

// One source for TS types, browser validation, and exported Python JSON Schema.
const id = Type.String({ minLength: 1 });
const count = Type.Integer({ minimum: 0, maximum: Number.MAX_SAFE_INTEGER });
const sequence = Type.Integer({ minimum: 1, maximum: Number.MAX_SAFE_INTEGER });
const artifactKind = Type.Union([
  Type.Literal("html"), Type.Literal("react"), Type.Literal("markdown"), Type.Literal("svg"),
  Type.Literal("mermaid"), Type.Literal("code"), Type.Literal("diff"), Type.Literal("file"),
]);
const stopReason = Type.Union([
  Type.Literal("end_turn"), Type.Literal("max_tokens"), Type.Literal("cancelled"), Type.Literal("tool_limit"),
]);
const usage = Type.Object({
  input_tokens: count, output_tokens: count, reasoning_tokens: Type.Optional(count),
  reported: Type.Optional(Type.Boolean()),
}, { additionalProperties: false });

function event<T extends string, P extends TProperties>(type: T, properties: P) {
  return Type.Object({ type: Type.Literal(type), seq: sequence, ...properties }, { additionalProperties: false });
}

export const StreamEventSchema = Type.Union([
  event("message_start", { message_id: id, chat_id: id, model: id }),
  event("text_delta", { part_id: id, text: Type.String() }),
  event("status", { part_id: id, summary: Type.String() }),
  event("tool_call", { part_id: id, tool_use_id: id, name: id, input: Type.Unknown() }),
  event("tool_progress", {
    tool_use_id: id, stream: Type.Union([Type.Literal("stdout"), Type.Literal("stderr"), Type.Literal("info")]),
    chunk: Type.String(),
  }),
  event("tool_result", {
    tool_use_id: id, ok: Type.Boolean(), output_preview: Type.String(), output_ref: Type.Optional(id),
    duration_ms: Type.Number({ minimum: 0, maximum: Number.MAX_SAFE_INTEGER }),
  }),
  event("artifact_created", { artifact_id: id, version: sequence, kind: artifactKind, title: Type.String() }),
  event("message_complete", { message_id: id, stop_reason: stopReason, usage }),
  event("error", { code: id, message: Type.String(), retryable: Type.Boolean() }),
], {
  $schema: "http://json-schema.org/draft-07/schema#",
  $id: "https://qvelt.invalid/schemas/stream-event.json",
});

export type ArtifactKind = Static<typeof artifactKind>;
export type StopReason = Static<typeof stopReason>;
export type Usage = Static<typeof usage>;
export type StreamEvent = Static<typeof StreamEventSchema>;

/** Parse wire JSON without eval, coercion, or including payload text in errors. */
export function parseEvent(data: string): StreamEvent {
  try {
    const value: unknown = JSON.parse(data, (_key, item: unknown) => {
      if (typeof item === "number" && !Number.isFinite(item)) throw new TypeError();
      return item;
    });
    if (Value.Check(StreamEventSchema, value)) return value;
  } catch { /* Use the same sanitized error for malformed JSON and invalid fields. */ }
  throw new TypeError("Invalid stream event");
}
