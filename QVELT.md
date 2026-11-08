# QVELT project instructions (read at the start of every task)

- Goal: a web product around QVELT models: chat, files/ZIP, sandbox execution, artifacts, coding agent.
- Locales for the UI: English, Ukrainian, Russian first; design for right-to-left languages.
- Reasoning levels (none/low/medium/high/extra high/maximum) are read from provider capabilities; never hard-coded.
- Show users a concise plain-language work summary (plan, actions, changes, verification), not raw reasoning.
  Raw reasoning, if any, is stored separately with a retention policy.
- Honesty: report failures and limits plainly; never claim unverified results.
- Contested political/legal topics: rely on sourced facts and international law; this is evaluated with a reviewed
  test set, not hard-coded text.
