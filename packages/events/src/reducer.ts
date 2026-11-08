import type { ArtifactKind, StopReason, StreamEvent, Usage } from "./events";

export type Part =
  | { id: string; type: "text"; text: string }
  | { id: string; type: "status"; summary: string }
  | {
      id: string;
      type: "tool";
      toolUseId: string;
      name: string;
      input: unknown;
      state: "running" | "done" | "error" | "cancelled";
      log: string;
      outputPreview?: string;
      durationMs?: number;
    }
  | { id: string; type: "artifact"; artifactId: string; version: number; kind: ArtifactKind; title: string };

export interface MsgState {
  id: string;
  parts: Part[];
  status: "streaming" | "complete" | "error" | "cancelled";
  lastSeq: number;
  error?: string;
  stopReason?: StopReason;
  usage?: Usage;
}

export function initialState(id = ""): MsgState {
  return { id, parts: [], status: "streaming", lastSeq: 0 };
}

/** Ordered delivery: ignore replay, reject gaps, and keep terminal states absorbing. */
export function reduce(s: MsgState, ev: StreamEvent): MsgState {
  if (!Number.isSafeInteger(ev.seq) || ev.seq < 1) throw new RangeError("Invalid sequence");
  if (ev.seq <= s.lastSeq) return s;
  if (s.status !== "streaming") return s;
  if (ev.seq !== s.lastSeq + 1) throw new RangeError("Sequence gap; resume from lastSeq");
  const next: MsgState = { ...s, lastSeq: ev.seq };
  switch (ev.type) {
    case "message_start":
      if (s.lastSeq !== 0 || (s.id && s.id !== ev.message_id)) throw new Error("Invalid message start");
      return { ...next, id: ev.message_id };
    case "text_delta": {
      const parts = [...s.parts];
      const i = parts.findIndex((p) => p.id === ev.part_id);
      const existing = i === -1 ? undefined : parts[i];
      if (existing && existing.type !== "text") throw new Error("Part type collision");
      if (existing && existing.type === "text") {
        parts[i] = { ...existing, text: existing.text + ev.text };
      } else if (i === -1) {
        parts.push({ id: ev.part_id, type: "text", text: ev.text });
      }
      return { ...next, parts };
    }
    case "status": {
      const existing = s.parts.find(p => p.id === ev.part_id);
      if (existing && existing.type !== "status") throw new Error("Part type collision");
      const updated: Part = { id: ev.part_id, type: "status", summary: ev.summary };
      const parts = existing ? s.parts.map(p => p === existing ? updated : p) : [...s.parts, updated];
      return { ...next, parts };
    }
    case "tool_call":
      if (s.parts.some(p => p.id === ev.part_id || (p.type === "tool" && p.toolUseId === ev.tool_use_id))) {
        throw new Error("Duplicate tool call or part identifier");
      }
      return {
        ...next,
        parts: [
          ...s.parts,
          { id: ev.part_id, type: "tool", toolUseId: ev.tool_use_id, name: ev.name, input: ev.input, state: "running", log: "" },
        ],
      };
    case "tool_progress":
    case "tool_result": {
      const tool = s.parts.find(p => p.type === "tool" && p.toolUseId === ev.tool_use_id);
      if (!tool || tool.type !== "tool" || tool.state !== "running") throw new Error("No active tool call");
      const updated: Part = ev.type === "tool_progress"
        ? { ...tool, log: tool.log + ev.chunk }
        : { ...tool, state: ev.ok ? "done" : "error", outputPreview: ev.output_preview, durationMs: ev.duration_ms };
      return { ...next, parts: s.parts.map(p => p === tool ? updated : p) };
    }
    case "artifact_created": {
      const id = `a_${ev.artifact_id}_${ev.version}`;
      const existing = s.parts.find(p => p.id === id);
      if (existing) {
        if (existing.type !== "artifact" || existing.kind !== ev.kind || existing.title !== ev.title) {
          throw new Error("Conflicting artifact version");
        }
        return next;
      }
      return {
        ...next,
        parts: [
          ...s.parts,
          { id, type: "artifact", artifactId: ev.artifact_id, version: ev.version, kind: ev.kind, title: ev.title },
        ],
      };
    }
    case "message_complete":
      if (s.id && s.id !== ev.message_id) throw new Error("Message identity mismatch");
      if (ev.stop_reason === "end_turn" && s.parts.some(p => p.type === "tool" && p.state === "running")) {
        throw new Error("Unfinished tool call");
      }
      return {
        ...next, id: ev.message_id, status: ev.stop_reason === "cancelled" ? "cancelled" : "complete",
        stopReason: ev.stop_reason, usage: { ...ev.usage },
        parts: s.parts.map<Part>(p => p.type === "tool" && p.state === "running"
          ? { ...p, state: ev.stop_reason === "cancelled" ? "cancelled" : "error" } : p),
      };
    case "error":
      return {
        ...next, status: "error", error: ev.message,
        parts: s.parts.map<Part>(p => p.type === "tool" && p.state === "running" ? { ...p, state: "error" } : p),
      };
  }
}
