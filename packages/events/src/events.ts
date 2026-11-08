// Single event contract shared by backend (JSON Schema generated later) and frontend.
export type ArtifactKind = "html" | "react" | "markdown" | "svg" | "mermaid" | "code" | "diff" | "file";

export interface Usage {
  input_tokens: number;
  output_tokens: number;
  reasoning_tokens?: number;
}

export type StopReason = "end_turn" | "max_tokens" | "cancelled" | "tool_limit";

export type StreamEvent =
  | { type: "message_start"; seq: number; message_id: string; chat_id: string; model: string }
  | { type: "text_delta"; seq: number; part_id: string; text: string }
  | { type: "status"; seq: number; part_id: string; summary: string }
  | { type: "tool_call"; seq: number; part_id: string; tool_use_id: string; name: string; input: unknown }
  | { type: "tool_progress"; seq: number; tool_use_id: string; stream: "stdout" | "stderr" | "info"; chunk: string }
  | { type: "tool_result"; seq: number; tool_use_id: string; ok: boolean; output_preview: string; output_ref?: string; duration_ms: number }
  | { type: "artifact_created"; seq: number; artifact_id: string; version: number; kind: ArtifactKind; title: string }
  | { type: "message_complete"; seq: number; message_id: string; stop_reason: StopReason; usage: Usage }
  | { type: "error"; seq: number; code: string; message: string; retryable: boolean };
