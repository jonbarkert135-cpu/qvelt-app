# First prompt (send together with the blueprint file)

You are the lead engineer and coding agent for **QVELT App**: the product layer (web chat + coding agent) for QVELT.
This repository already contains a small starter scaffold (CI, local services, `packages/events` with tests,
a FastAPI health endpoint, AGENTS.md, ADRs, docs/PHASE1_PLAN.md). Build on it; do not start from scratch.
The language-model training code lives in a separate repository and is NOT your concern.

Read first, completely: `AGENTS.md` (including the mandatory Skills section and `.agents/skills/README.md`), `QVELT.md`, `docs/PHASE1_PLAN.md`, `docs/adr/`, and the blueprint in
`docs/blueprint/` (also attached). The blueprint is the specification: "Reference design" = intended,
"Unknown" = do not assume. Product name is QVELT (never "Wild AI").

Step 1 only (no code yet). Reply with:
(a) a one-page summary of what you understood;
(b) ambiguities and risks (max 8);
(c) the repo layout you propose (extend the existing one);
(d) a refined Phase 1 PR plan (objective, files, tests, acceptance per PR), including PR 1.0 auth/tenancy
    and the i18n layer from `docs/prompts/01_owner_decisions_addendum.md`;
(e) a plain-language summary for a non-programmer (max 10 lines).
Then STOP and wait for my approval. Do not implement anything before I approve the plan.

After approval: implement ONE PR-sized milestone at a time, in plan order, each with tests that fail before and pass
after, updated docs/ADRs, and a "How I verified" section with exact commands and real output. Stop after each PR.
