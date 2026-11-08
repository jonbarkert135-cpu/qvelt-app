import type { ArtifactKind, StreamEvent } from "./events";

export type Part =
  | { id: string; type: "text"; text: string }
  | { id: string; type: "status"; summary: string }
  | {
      id: string;
      type: "tool";
      toolUseId: string;
      name: string;
      input: unknown;
      state: "running" | "done" | "error";
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
}

export function initialState(id = ""): MsgState {
  return { id, parts: [], status: "streaming", lastSeq: 0 };
}

/** Pure reducer. Events with seq <= lastSeq are ignored (reconnect / duplicate delivery). */
export function reduce(s: MsgState, ev: StreamEvent): MsgState {
  if (ev.seq <= s.lastSeq) return s;
  const next: MsgState = { ...s, lastSeq: ev.seq };
  switch (ev.type) {
    case "message_start":
      return { ...next, id: ev.message_id };
    case "text_delta": {
      const parts = [...s.parts];
      const i = parts.findIndex((p) => p.id === ev.part_id);
      const existing = i === -1 ? undefined : parts[i];
      if (existing && existing.type === "text") {
        parts[i] = { ...existing, text: existing.text + ev.text };
      } else if (i === -1) {
        parts.push({ id: ev.part_id, type: "text", text: ev.text });
      }
      return { ...next, parts };
    }
    case "status": {
      const parts = s.parts.filter((p) => p.id !== ev.part_id);
      parts.push({ id: ev.part_id, type: "status", summary: ev.summary });
      return { ...next, parts };
    }
    case "tool_call":
      return {
        ...next,
        parts: [
          ...s.parts,
          { id: ev.part_id, type: "tool", toolUseId: ev.tool_use_id, name: ev.name, input: ev.input, state: "running", log: "" },
        ],
      };
    case "tool_progress":
      return {
        ...next,
        parts: s.parts.map((p) =>
          p.type === "tool" && p.toolUseId === ev.tool_use_id ? { ...p, log: p.log + ev.chunk } : p,
        ),
      };
    case "tool_result":
      return {
        ...next,
        parts: s.parts.map((p) =>
          p.type === "tool" && p.toolUseId === ev.tool_use_id
            ? { ...p, state: ev.ok ? "done" : "error", outputPreview: ev.output_preview, durationMs: ev.duration_ms }
            : p,
        ),
      };
    case "artifact_created":
      return {
        ...next,
        parts: [
          ...s.parts,
          { id: `a_${ev.artifact_id}_${ev.version}`, type: "artifact", artifactId: ev.artifact_id, version: ev.version, kind: ev.kind, title: ev.title },
        ],
      };
    case "message_complete":
      return { ...next, status: ev.stop_reason === "cancelled" ? "cancelled" : "complete" };
    case "error":
      return { ...next, status: "error", error: ev.message };
  }
}
