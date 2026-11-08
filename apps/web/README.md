# QVELT web shell — Phase 1.1

Next.js App Router, React, TypeScript strict, Tailwind and a Radix Dialog mobile
drawer. The shell has light/dark/system themes, en/uk/ru dictionaries, responsive
navigation, draft suggestions and keyboard support. It makes no API/model calls.
Messaging and account integration are still future milestones; the send button is
explicitly unavailable. Drafts live only in component memory and disappear on reload.

From the repository root:

```sh
npm ci
npm run dev --workspace @qvelt/web
npm run typecheck --workspace @qvelt/web
npm run lint --workspace @qvelt/web
npm test --workspace @qvelt/web
```

Browser tests build and run the **production** app on port 3100 and cover:
locale/theme persistence, input preservation, confirmation before discarding,
mobile focus trapping/Escape, desktop sidebar collapse, unknown cookie values,
system color scheme, server-rendered preferences, and axe WCAG checks plus
screenshots at 390/768/1440 in both themes and directions. RTL checks layout only;
no RTL translation is claimed. Automated checks are not a full WCAG audit.

Tests use Playwright's installed Chromium. On a machine with a trusted system
Chromium, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium`. Otherwise install
the pinned browser with `npm exec --workspace @qvelt/web -- playwright install chromium`.
CI installs its browser and dependencies and retains screenshots/failure traces.
Use `PLAYWRIGHT_CHROMIUM_EXECUTABLE` only to select the intended browser binary.

Only validated language/theme preferences are stored in same-site cookies. Their
initial values are rendered on the server to avoid theme/language hydration jumps.
Draft text is never put in cookies, localStorage, URLs, logs or analytics. All
fonts and icons use platform/local resources; no external asset service is needed.
New chat (`Ctrl/Cmd+Shift+O`) asks before discarding a nonempty draft. Focus-visible,
logical CSS properties, reduced-motion and safe-area spacing are included.

Design studies: `docs/design/directions.html`. The selected Paper token/component
study is in `docs/design/components.html`. ADR-0004 records the autonomous selection.
