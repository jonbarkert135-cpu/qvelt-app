# ADR-0006: Shared wire schema and ordered replay

Status: accepted

## Context

Phase 1.2 needs one event contract for the browser and Python, not two handwritten
unions that drift. The reducer currently silently accepts sequence gaps, moves
updated status blocks, and permits mutations after cancellation.

## Decision

Use TypeBox in `packages/events/src/events.ts` as the schema/type source. Retain
the existing nine discriminants and field names. Infer TS types and export an
ordinary Draft-07 JSON Schema to the event package and a Python package resource.
The small native-Node exporter requires Node 22.18+ and supports a read-only check
that fails when either generated file differs. Python uses pinned `jsonschema`,
loads its installed resource and never downloads a schema at runtime.

Wire parsers reject additional fields, malformed JSON, nonfinite numbers and
invalid field types/enums. Sequence, version and token counts use safe integer
bounds for JavaScript interoperability, not provider capability limits. Tool input
remains unknown transport data; the orchestrator still owns tool validation and
permissions. Frame-size/depth/resource limits belong at the transport boundary.

Keep SSE ordered: discard older/equal sequence replay, but reject gaps before
advancing the cursor. Reconnect can then replay from the last successful state.
Do not add speculative buffering or a transport implementation in this milestone.
Reject conflicting message/part/tool identities and progress after tool completion.
Preserve status ordering, deduplicate identical artifact versions and reject
conflicting versions. Terminal states are absorbing; cancellation/error settles
running tools, successful end_turn requires completed tools, and interrupted
termination retains the stop reason and usage. Earlier state remains unchanged.

## Consequences

This tightens previously permissive behavior intentionally. No production event
producer consumes the starter contract yet, so a separate wire version/migration
is unnecessary now. A future deployed schema change needs explicit compatibility
planning. Restore/reconnect uses a trusted state with its applied cursor; accepting
an arbitrary partial stream by skipping missing sequence values is unsupported.

The shared fixture corpus runs in both languages, including adversarial payloads.
Reducer tests cover gaps, replay, immutable updates, tool lifecycle, cancellation,
identity collisions and artifact versions. Schema freshness is part of npm test;
Python package data is checked independently so wheel installs need no checkout.

An alternative TS-to-schema generator would preserve handwritten interfaces but
add a separate code-generation parser and provide no browser validator. Pydantic
alone would duplicate the event contract. A hand-rolled schema validator would
create more security-sensitive code than the two established pinned libraries.
