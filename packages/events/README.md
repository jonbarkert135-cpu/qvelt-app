# QVELT stream event contract

`src/events.ts` is the single source for the nine wire event variants, TypeScript
types and the exported Draft-07 JSON Schema. TypeBox supplies the schema/type link
and interpreter-based validation; no eval or runtime schema download is used.

```ts
import { initialState, parseEvent, reduce } from "@qvelt/events";

let state = initialState();
const event = parseEvent(rawJson); // throws a sanitized TypeError on bad wire data
state = reduce(state, event);
```

Run from the repository root with Node **22.18+**:

```sh
npm run schema:export --workspace @qvelt/events
npm run schema:check --workspace @qvelt/events
npm test --workspace @qvelt/events
```

The export command writes `schema/stream-event.schema.json` and the identical
packaged resource in `apps/api/src/qvelt_api/schemas/`. Both are checked in. After
changing a wire shape, export again and commit both outputs; `npm test` fails if
either is stale. Node's native type stripping runs the small exporter without
adding a second TypeScript execution tool. JSON Schema draft support comes from
the backend's pinned `jsonschema` dependency, not a handwritten Python event union.

```python
from qvelt_api.events import parse_event

event = parse_event(raw_json)  # same schema; generic ValueError on invalid input
```

## Wire validation

Unknown fields are rejected, including in usage. Sequence and artifact version
are positive safe integers; usage counts are nonnegative safe integers. Durations
are nonnegative finite numbers. IDs and names are nonempty strings. Unknown event
types, invalid enum values, malformed JSON and nonfinite numbers are rejected.
The safe-integer bound is JavaScript representation safety, not a model limit.

`usage.reported` is optional for compatibility; the Phase 1.3 producer always sets
it. False means counters were unavailable and numeric zeros are placeholders.
Neither false nor an absent flag establishes measured/billable usage. A `fake`
model's whitespace-token counters are test data even when reported is true.

`tool_call.input` deliberately stays unknown: any valid finite JSON is transport
data, **not** a validated tool request or permission grant. The future orchestrator
must validate the tool-specific schema, authorization and budgets separately.
No arbitrary text-size/model limit is embedded in the event schema. The transport
must separately enforce frame, input and resource limits before parsing large data.

## Reducer and reconnect rules

- A stream is ordered and scoped to one message. Older/equal `seq` values are replay
  and return the existing state unchanged. A new event must be exactly `lastSeq+1`.
  A gap raises RangeError before advancing state: stop consumption and resume after
  the last successfully applied cursor. Do not skip forward or buffer unboundedly.
- Structural/lifecycle errors are not retriable gaps. Close/reject malformed streams;
  do not repeatedly replay a permanently invalid frame. This package does not open
  SSE connections or implement transport retry policy; that is Phase 1.3.
- Existing status blocks update in place. Part IDs cannot change type; tool-use IDs
  cannot be reused. Progress/results require an active call. Tool input/output is
  untrusted data; the reducer never executes it or renders HTML.
- Identical artifact/version replay is idempotent even at a new sequence. A different
  title/kind for the same version is a protocol error; a new version gets a new part.
- Cancellation and error are terminal; later events cannot revive or append to the
  message. Running tools become cancelled/error. Successful `end_turn` cannot finish
  with running tools. Budget/max-token termination settles unfinished tools as errors.
- Completion retains `usage` and `stopReason`. Reducer updates preserve earlier state.
  Transport validation and state-transition validation are separate boundaries.

`fixtures/stream-events.json` is consumed by both TS and Python tests. It covers
all variants, Unicode, missing/extra fields, wrong types, enum and numeric boundaries.
