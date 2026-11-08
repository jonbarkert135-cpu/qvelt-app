import { describe, expect, it } from "vitest";
import { initialState, reduce } from "./reducer";
import type { StreamEvent } from "./events";

const run = (events: StreamEvent[]) => events.reduce(reduce, initialState());

describe("reduce", () => {
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
