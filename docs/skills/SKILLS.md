# Third-party skills: candidates and vetting policy

Status: one reviewed text-only accessibility skill is installed; see the audit below.
The older candidate table records suggestions from public listings, not full audits.
Star counts and rankings change; verify on the canonical repository before relying on them.

## Vetting policy (mandatory before installing any third-party skill)
1. Use only the canonical owner/repository. Search results contain many forks and clones; do not install from them.
2. Pin to a full commit SHA. Vendor a copy into `.agents/skills/vendor/<name>@<sha>/`. No auto-update; updates are a
   reviewed diff.
3. Read the ENTIRE skill: SKILL.md, scripts/, references/. Reject or patch if it: fetches instructions from a URL at
   runtime, runs network commands, uploads project files, writes outside the repo, hard-codes someone's local paths,
   disables checks, or asks for secrets.
4. Record the license and any obligations (e.g. ShareAlike, source-available limits) in the table below.
5. Review `allowed-tools` / scripts. Skill scripts run only in the sandbox or dev container.
6. A skill never overrides AGENTS.md or ADRs. If it conflicts, follow AGENTS.md and report the conflict.
7. Install only on the owner's approval, one skill at a time, with a short note in `docs/adr/`.

## Uploaded design archives: audit

| Upload | Identification | Result |
| --- | --- | --- |
| `agent-skills-main.zip` | `sergiodxa/agent-skills`, archive commit `40e21b46189d5c7de6610b68a25280af863f8775`, MIT | Installed only `frontend-accessibility-best-practices`; SKILL.md, all 7 rules and LICENSE read completely and verified byte-for-byte against canonical raw GitHub files at that commit. No scripts. |
| `AI-Agents-public-main.zip` | README identifies `vasilyu1983/AI-Agents-public`; archive commit `3424d6f5e94010409da012eeb1cb84aaecec88b3`; root MIT | Indexed; UI/UX candidate includes many references/assets. Not fully reviewed, not installed. |
| `ui-ux-pro-max-skill-main.zip` | README identifies `nextlevelbuilder/ui-ux-pro-max-skill`; archive commit `b7e3af80f6e331f6fb456667b82b12cade7c9d35`; root MIT | Indexed; contains symlink entries for data/scripts, tool-dependent workflows and API-key-based generation elsewhere in the bundle. Not fully reviewed, not installed. No extraction of symlinks. |
| `skills-main.zip` | README identifies `semgrep/skills`; archive commit `90cc990a535098a84950b18d8cf770e097da1c77`; Semgrep Rules License v1.0 | Security skills rather than design skills. Not installed; no MIT/Apache licensing assumption. |
| `ai-agents-skills-master.zip` | Unknown: executor transfer limit exceeded (32 MiB) | Not downloaded or inspected. No claims about provenance, license or safety. |

Only the first installed subset has been fully vetted. Archive comments identify
candidate commits; the accessibility files were additionally verified remotely.
The other bundles remain attachments, not active project instructions. Original
upstream React Aria examples do not authorize a framework migration or new dependencies.
44×44 CSS px is the project's tap-area target, not a claim of full AAA certification.

### Earlier candidates

| Area | Candidate | What it offers (per listings) | License note (verify) | Recommendation |
|---|---|---|---|---|
| Engineering process | `obra/superpowers` | TDD (red-green-refactor), systematic debugging, verification-before-completion, writing plans, code review, git worktrees; works with several coding agents | MIT (per README listing) | HIGH value. Vet and adopt selected skills. |
| Official examples | `anthropics/skills` | Reference skills (development/technical, testing web apps, MCP server building, skill-creator), Agent Skills spec and template | Many Apache-2.0; docx/pdf/pptx/xlsx are source-available, not open source | Use as reference and templates. Do not vendor the document skills without reading their terms. |
| Frontend | `vercel-labs/agent-skills` | `react-best-practices` (57 rules, 8 categories), `composition-patterns`, `web-design-guidelines` (100+ UI/a11y rules), view transitions | MIT stated in README; one listing says no LICENSE file; confirm | HIGH value for the web app. Note: one listing says `web-design-guidelines` pulls its rules from an external URL; vendor a pinned copy of the rules instead. Do NOT install `vercel-deploy-claimable` (uploads the project to an external service). |
| Security review | `trailofbits/skills` | differential-review, audit-context-building, property-based-testing, variant-analysis, agentic-actions-auditor (audits GitHub Actions for AI-agent risks), semgrep rule creation | CC BY-SA 4.0 (ShareAlike): do not copy text into our repo without a license decision | MEDIUM-HIGH. Use as an external review aid or as reference; get a license decision before vendoring. |
| Design (UI) | `anthropics/skills` skill `frontend-design` (also redistributed in many repos; use the canonical one) | guides distinctive, production-grade UI and avoiding generic AI look | see the repo's LICENSE for this skill | HIGH value for the design phase, with one caveat: it pushes bold, dramatic styles; a chat product needs calm and readable. Our `qvelt-chat-ui-design` skill and `docs/DESIGN_BRIEF.md` take precedence. |
| Design (UI) | `pbakaus/impeccable` skill `frontend-design` | extended version with references for typography, spatial design, responsive design, UX writing; asks for design context before designing | Apache-2.0, based on Anthropic's skill (per listing) | HIGH value after vetting; read all references first. |
| Math (exact computation) | `K-Dense-AI/scientific-agent-skills` skill `sympy` | symbolic algebra, calculus, equation solving, code generation | MIT (per listing) | Good fit for `math-and-numerics-check` backing. |
| Math (alternative) | `parcadei/continuous-claude-v3` skill `math` | routes math to deterministic SymPy scripts, numeric tools, mentions Lean 4 for formal proofs | check repo license | Optional. Lean 4 is research-only for now. |
| Skipped | `beita6969/scienceclaw` `math-computation` | has someone's local virtualenv path hard-coded in the skill text | n/a | Skip: poor portability. |
| Repo hygiene | `getsentry/agents-md`, `getsentry/code-review` | AGENTS.md authoring, code review (names per an awesome-list) | check | Optional; read before use. |
| Discovery | `agentskills.io` (spec), `gmh5225/awesome-skills`, `npx skills add <owner>/<repo>` CLI | the Agent Skills format; curated lists; installer | n/a | Use for discovery only. Do not run `npx skills add` without the vetting steps above. |

## Where each skill location matters
Different agent tools read different folders (`.claude/skills/`, `.github/skills/`, `.agent/skills/`, `.gemini/skills/`...).
This repo keeps ONE canonical folder, `.agents/skills/`. Run `make link-skills` to expose it to tools that expect another path.
