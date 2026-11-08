---
name: qvelt-chat-ui-design
description: Design and verify QVELT chat interfaces with readable content, responsive layouts, localization and accessibility.
---

# QVELT interface

Read `docs/DESIGN_BRIEF.md`, the current UI and relevant blueprint sections first.
Keep ponytail as the primary coding skill. Reuse the project's design tokens and
native HTML before adding component abstractions or libraries.

1. For a new visual direction, prepare three small light/dark studies with a
   rationale. Use the owner's selection; when explicitly authorized to work
   autonomously, record your selected default and alternatives in an ADR.
2. Build a calm reading surface, restrained accent, original mark and clear type
   hierarchy. Avoid gradients, decorative panels and simulated conversations.
3. Use semantic landmarks, labelled controls, visible focus, keyboard operation,
   reduced-motion styles and sufficient contrast. A mobile drawer must manage
   focus, Escape, scroll locking and return focus; use the established primitive.
4. All UI strings go through typed en/uk/ru dictionaries. Use logical CSS properties
   and test RTL positioning without claiming an untranslated locale is supported.
5. Never make an unavailable action appear to work. Keep drafts out of URLs and
   logs; persist only preferences until authenticated storage exists. Do not render
   untrusted HTML or add analytics, remote fonts or model calls for a shell.
6. Write an observable behavior check before implementing an interaction. Verify
   desktop/mobile, theme and locale persistence, keyboard/focus behavior, no
   horizontal overflow and accessibility with a real browser. Capture screenshots
   at 390, 768 and 1440 pixels in light/dark and RTL, and inspect them.
7. Run applicable tests, typecheck, lint and a production build. Separate an actual
   chat response from a draft or prototype. Record remaining integrations plainly.
