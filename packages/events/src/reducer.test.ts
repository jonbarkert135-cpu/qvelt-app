import { describe, expect, it } from "vitest";
import { initialState, reduce } from "./reducer";
import type { StreamEvent } from "./events";

const run = (events: StreamEvent[]) => events.reduce(reduce, initialState());

describe("reduce", () => {
  it("detects a gap without consuming the cursor, then resumes from the last event", () => {
    const first = reduce(initialState(), { type: "text_delta", seq: 1, part_id: "p", text: "A" });
    const third: StreamEvent = { type: "text_delta", seq: 3, part_id: "p", text: "C" };
    expect(() => reduce(first, third)).toThrow("Sequence gap");
    expect(first.lastSeq).toBe(1);
    const second = reduce(first, { type: "text_delta", seq: 2, part_id: "p", text: "B" });
    const resumed = reduce(reduce(second, third), third);
    expect(resumed.parts).toEqual([{ id: "p", type: "text", text: "ABC" }]);
  });

  it.each([0, -1, 1.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1])("rejects invalid seq %s", seq => {
    expect(() => reduce(initialState(), { type: "text_delta", seq, part_id: "p", text: "A" })).toThrow();
  });

  it("updates a status in place without changing the order or mutating earlier state", () => {
    const before = run([
      { type: "status", seq: 1, part_id: "s", summary: "Reading" },
      { type: "text_delta", seq: 2, part_id: "p", text: "Text" },
    ]);
    const after = reduce(before, { type: "status", seq: 3, part_id: "s", summary: "Done" });
    expect(after.parts.map(part => part.id)).toEqual(["s", "p"]);
    expect(before.parts[0]).toMatchObject({ summary: "Reading" });
  });

  it("keeps terminal cancellation absorbing and settles running tools", () => {
    const before = reduce(initialState("m"), {
      type: "tool_call", seq: 1, part_id: "t", tool_use_id: "u", name: "exec", input: {},
    });
    const usage = { input_tokens: 3, output_tokens: 2 };
    const cancelled = reduce(before, { type: "message_complete", seq: 2, message_id: "m", stop_reason: "cancelled", usage });
    expect(cancelled).toMatchObject({ status: "cancelled", stopReason: "cancelled", usage });
    expect(cancelled.parts[0]).toMatchObject({ state: "cancelled" });
    expect(before.parts[0]).toMatchObject({ state: "running" });
    expect(reduce(cancelled, { type: "text_delta", seq: 99, part_id: "p", text: "Late" })).toBe(cancelled);
  });

  it("settles tools on failure and keeps errors terminal", () => {
    const before = reduce(initialState(), { type: "tool_call", seq: 1, part_id: "t", tool_use_id: "u", name: "exec", input: {} });
    const failed = reduce(before, { type: "error", seq: 2, code: "failed", message: "Unavailable", retryable: true });
    expect(failed.parts[0]).toMatchObject({ state: "error" });
    expect(reduce(failed, { type: "text_delta", seq: 3, part_id: "p", text: "Late" })).toBe(failed);
  });

  it("rejects message identity changes and premature success", () => {
    const started = reduce(initialState(), { type: "message_start", seq: 1, message_id: "m", chat_id: "c", model: "fake" });
    expect(() => reduce(started, { type: "message_start", seq: 2, message_id: "other", chat_id: "c", model: "fake" })).toThrow();
    expect(() => reduce(started, { type: "message_complete", seq: 2, message_id: "other", stop_reason: "end_turn", usage: { input_tokens: 0, output_tokens: 0 } })).toThrow();
    const tool = reduce(started, { type: "tool_call", seq: 2, part_id: "t", tool_use_id: "u", name: "exec", input: {} });
    expect(() => reduce(tool, { type: "message_complete", seq: 3, message_id: "m", stop_reason: "end_turn", usage: { input_tokens: 0, output_tokens: 0 } })).toThrow();
  });

  it("rejects collisions and tool results/progress without an active call", () => {
    const text = reduce(initialState(), { type: "text_delta", seq: 1, part_id: "p", text: "A" });
    expect(() => reduce(text, { type: "status", seq: 2, part_id: "p", summary: "Wrong type" })).toThrow();
    expect(() => reduce(text, { type: "tool_progress", seq: 2, tool_use_id: "missing", stream: "stdout", chunk: "x" })).toThrow();
    const tool = reduce(initialState(), { type: "tool_call", seq: 1, part_id: "t", tool_use_id: "u", name: "exec", input: {} });
    expect(() => reduce(tool, { type: "text_delta", seq: 2, part_id: "t", text: "Wrong type" })).toThrow();
    expect(() => reduce(tool, { type: "tool_call", seq: 2, part_id: "other", tool_use_id: "u", name: "exec", input: {} })).toThrow();
    const done = reduce(tool, { type: "tool_result", seq: 2, tool_use_id: "u", ok: true, output_preview: "ok", duration_ms: 0 });
    expect(() => reduce(done, { type: "tool_progress", seq: 3, tool_use_id: "u", stream: "stdout", chunk: "late" })).toThrow();
  });

  it("does not duplicate an artifact version on semantic replay", () => {
    const artifact: StreamEvent = { type: "artifact_created", seq: 1, artifact_id: "a", version: 1, kind: "code", title: "Example" };
    const replayed = reduce(reduce(initialState(), artifact), { ...artifact, seq: 2 });
    expect(replayed.parts).toHaveLength(1);
    expect(replayed.lastSeq).toBe(2);
    expect(reduce(replayed, { ...artifact, seq: 3, version: 2 }).parts).toHaveLength(2);
  });

  it("accumulates text deltas into one part", () => {
    const s = run([
      { type: "message_start", seq: 1, message_id: "m1", chat_id: "c1", model: "fake" },
      { type: "text_delta", seq: 2, part_id: "p1", text: "Hel" },
      { type: "text_delta", seq: 3, part_id: "p1", text: "lo" },
    ]);
    expect(s.parts).toEqual([{ id: "p1", type: "text", text: "Hello" }]);
    expect(s.id).toBe("m1");
  });

  it("ignores duplicate and out-of-order seq (reconnect safety)", () => {
    const s = run([
      { type: "text_delta", seq: 1, part_id: "p1", text: "A" },
      { type: "text_delta", seq: 2, part_id: "p1", text: "B" },
      { type: "text_delta", seq: 2, part_id: "p1", text: "B" },
      { type: "text_delta", seq: 1, part_id: "p1", text: "A" },
    ]);
    expect(s.parts[0]).toMatchObject({ text: "AB" });
    expect(s.lastSeq).toBe(2);
  });

  it("tracks a tool call lifecycle", () => {
    const s = run([
      { type: "tool_call", seq: 1, part_id: "t1", tool_use_id: "u1", name: "exec", input: { cmd: ["ls"] } },
      { type: "tool_progress", seq: 2, tool_use_id: "u1", stream: "stdout", chunk: "a\n" },
      { type: "tool_progress", seq: 3, tool_use_id: "u1", stream: "stdout", chunk: "b\n" },
      { type: "tool_result", seq: 4, tool_use_id: "u1", ok: true, output_preview: "a b", duration_ms: 12 },
    ]);
    expect(s.parts[0]).toMatchObject({ type: "tool", state: "done", log: "a\nb\n", durationMs: 12 });
  });

  it("marks cancelled and error states", () => {
    const usage = { input_tokens: 1, output_tokens: 1 };
    expect(run([{ type: "message_complete", seq: 1, message_id: "m", stop_reason: "cancelled", usage }]).status).toBe("cancelled");
    expect(run([{ type: "error", seq: 1, code: "x", message: "boom", retryable: false }])).toMatchObject({ status: "error", error: "boom" });
  });
});
