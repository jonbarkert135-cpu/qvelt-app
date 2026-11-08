# ADR-0004: QVELT web shell and Paper direction

Status: accepted

## Context

Phase 1.1 requires an accessible app shell, theme tokens, sidebar and en/uk/ru
localization. The owner authorized autonomous development, including supplying
missing project skills. No browser UI currently exists, and the API's bearer
sessions are not yet integrated with a browser BFF.

## Decision

- Follow the planned Next.js App Router + TypeScript + Tailwind + Radix stack.
  Use one Radix Dialog primitive for the mobile drawer's focus, Escape and scroll
  behavior. Use native selects and platform fonts instead of more UI dependencies.
- Preserve three light/dark studies in `docs/design/directions.html`: Paper,
  Graphite and Linen. The agent selects Paper as the default under the owner's
  autonomous-work authorization, not as a claimed personal owner selection.
  It is closest to the provided blueprint: warm neutral surfaces, blue accent,
  system sans and Georgia headings, original Q mark, restrained borders.
- Keep all screen text in typed dictionaries. Store only validated theme/locale
  preferences in same-site cookies and render them server-side. This makes the
  root route dynamic but avoids hydration and initial theme flashes. Draft text
  stays in memory; changing preferences preserves it, reloading clears it.
- Use logical CSS and browser tests for RTL readiness. The supported translations
  remain English, Ukrainian and Russian. Do not imply an RTL translation exists.
- Do not simulate AI conversations or issue model calls. Disable sending with
  an explicit explanation until the planned streaming milestone. No browser
  credential store, BFF, persistence, uploads or artifact UI is scaffolded here.
- Original `qvelt-chat-ui-design` guidance is derived from the existing design
  brief; ponytail remains primary. Existing testing/security requirements take
  precedence over the skill's suggestions to minimize test infrastructure.

## Verification and consequences

Playwright runs against a production build. Its browser tests exercise live
preferences and navigation, and axe checks the shell plus open mobile drawer.
Capture both themes and directions at all three required widths; inspect actual
screenshots. This is evidence about the shell, not a full accessibility audit or
working chat/inference. Normal CI now includes browser install, production build,
browser tests, existing TS/Python tests, typechecks, lint and skill validation.

Keep the UI skill's baseline protections when the shell gains authentication:
future browser sessions must follow ADR-0003. Add providers/streaming according
to the existing plan, without storing API bearer tokens in browser preferences.
