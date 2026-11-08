# Phase 1 plan

Implemented: 1.0 (accounts, sessions, owner-scoped chats and RLS) and 1.1 (web shell,
themes, responsive sidebar, en/uk/ru and browser accessibility checks). The 1.1
composer is a draft surface; messaging and model calls remain scheduled below.
Also implemented: 1.2, shared event-contract hardening, runtime wire validation,
Python JSON Schema export and cross-language fixtures. Next: 1.3, authenticated
messages, FakeProvider and resumable SSE backed by Redis Streams.

| PR | Objective | Tests / acceptance |
|---|---|---|
| 1.0 | Auth + tenancy skeleton: registration/login/sessions, owner/tenant ids on every table, RLS prepared | isolation tests: user A cannot read user B data |
| 1.1 | Next.js app shell, design tokens (light/dark), sidebar, i18n layer (en/uk/ru, RTL-ready) | typecheck, lint, a11y smoke test |
| 1.2 | `@qvelt/events` hardening: JSON Schema export for Python, more reducer tests | duplicate/out-of-order seq, reconnect, cancel |
| 1.3 | FastAPI chats/messages + SSE with FakeProvider + Redis Streams; Idempotency-Key; resume with Last-Event-ID | reconnect yields no duplicates |
| 1.4 | Model gateway + OpenAICompatibleProvider + capabilities object | works against a local OpenAI-compatible server |
| 1.5 | Markdown pipeline: healPartialMarkdown, code blocks, GFM tables, math, scroll anchoring | no flicker; incomplete fences/tables handled |
| 1.6 | Stop/Retry/Edit/branches; reasoning-level selector driven by capabilities | e2e tests |

Done when: streaming chat works against FakeProvider and a real OpenAI-compatible server; reconnect has no
duplicates; markdown streams without flicker; Stop works; CI green.
Payments are NOT in Phase 1 (tariff-ready data model only).
