# Owner decisions addendum (send as the second message, or merge into the first)

Naming: product, model and ecosystem are QVELT. Package scope `@qvelt/*`, file `QVELT.md`, link scheme `qvelt-file://`.

Changes to the Phase 1 plan:
1. Accounts exist from the first version: PR 1.0 "auth + tenancy skeleton" BEFORE the chat PRs: registration/login,
   sessions, profile, tenant/owner id on every table, Row-Level Security prepared in Postgres, isolation tests, an
   org/enterprise tenant concept designed (not implemented). Payments are NOT in Phase 1; only a tariff-ready data model.
2. i18n from the start: all UI strings through a translation layer; locales English, Ukrainian, Russian; RTL readiness
   (Arabic, Hebrew, Persian); Unicode-correct input (IME).
3. Reasoning-level selector in the composer: levels come from the active provider's capabilities (effort_levels). If the
   provider reports none, hide/disable the selector. Never hard-code level names. Send the level only if supported.
4. Work summaries: for agent runs show a concise plain-language summary (plan, actions, changes, verification, failures).
   "Explain in more detail / in simple words" is a follow-up action. Raw reasoning is stored separately with a retention
   policy and not shown by default.
5. Approvals: destructive or irreversible actions (delete, overwrite outside selected files, network, package install,
   git push, publishing, opening a PR) always need explicit user approval, independent of what the model says.
6. User-data training consent: separate, default-OFF opt-in per account and per org, with deletion and export; consent is
   stored per record and enforced by any export job. No training export in Phase 1.
7. Honesty rule: never claim a test passed or a file changed unless the tool log proves it; state limits and failures plainly.
8. Delivery order: web first; desktop app and local agent later; third-party API and enterprise edition later. Design the
   event contract and permission model so a local agent can reuse them.

Update the Phase 1 PR list and acceptance tests accordingly, then wait for my approval.
