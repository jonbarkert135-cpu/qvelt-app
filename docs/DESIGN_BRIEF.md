# QVELT web app: design brief

## What we are building
A website you open in a browser (desktop and mobile) and use like the familiar chat products: you talk to the model,
attach files and projects, watch the agent work, and open results (code, documents, previews) in a side panel.
The site runs in the cloud and talks to the model through our servers. Desktop app and local agent come later.

## Direction
Calm, fast, content-first. Premium through restraint and craft, not decoration. Original identity: our own logo,
color, icons and wording. We borrow only common interaction patterns, never another product's visual assets.
Final aesthetic choices (typeface, accent, shapes) are decided in the design phase from 2-3 proposals.

## Screens and surfaces (first release)
1. Chat: sidebar (new chat, history, projects, search), reading column, floating composer, message actions.
2. Composer: autosize text, attach (drag, paste, pick), file chips with status, send/stop, reasoning-level selector
   (only if the model supports levels), model/capability hints.
3. Assistant messages: streamed Markdown (tables, code with copy, math), status line, collapsible tool cards with live
   output, plain-language work summary, file cards, diff view with accept/reject per hunk.
4. Artifact panel: Preview / Code / Diff tabs, version picker, copy, download, fullscreen; full-screen sheet on mobile.
5. Files and projects: upload progress, ZIP tree, indexing status, download results.
6. Approvals: clear cards for risky actions (what, why, scope) with Approve / Deny.
7. Account: sign in, profile, data and training-consent controls (default off), export/delete.
8. Empty states, errors, offline, limits reached, long-running task view.

## Foundations
- Tokens in `apps/web/styles/tokens.css` (starter set in the blueprint, section 2.3). Light and dark from day one.
- Layout: reading width about 46rem, sidebar 280px collapsible, artifact panel about 48vw, mobile uses drawer and sheet.
- Type: one readable text family, one monospace family, open licenses, coverage for Latin and Cyrillic first, plan for
  more scripts. Sizes: body 16/1.6, code 14/1.55.
- Motion: 120-200 ms, purposeful (streaming caret, panel slide, toast), reduced-motion safe.
- Internationalization: en, uk, ru first; right-to-left ready.
- Accessibility target: WCAG 2.2 AA.

## Design phase process (for the coding agent)
1. Read this brief, `.agents/skills/qvelt-chat-ui-design/`, and any vetted design skills in `.agents/skills/vendor/`.
2. Produce 3 directions as small static pages (chat screen only, light + dark), each with name, palette, type, shape
   language, and a short rationale. No product code yet.
3. Owner picks one (or mixes). Agent writes the tokens file and a component kitchen-sink page.
4. Build real components with tests and screenshots (390 / 768 / 1440, light/dark/RTL).
5. After each PR, report with the skill footer from AGENTS.md.

## Quality bar
A reviewer should not be able to tell which template or AI produced it. No generic gradients, no glow, no
every-button-primary, no placeholder copy. Every state is designed. Fast on a mid-range phone.
