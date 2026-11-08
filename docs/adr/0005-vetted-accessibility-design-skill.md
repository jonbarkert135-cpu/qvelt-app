# ADR-0005: One vetted accessibility design skill

Status: accepted

The owner supplied five skill archives for design. Install only the fully reviewed
`frontend-accessibility-best-practices` subset from canonical `sergiodxa/agent-skills`
at `40e21b46189d5c7de6610b68a25280af863f8775`. Its SKILL.md, seven rule files and MIT
LICENSE were read in full and matched byte-for-byte against raw GitHub at that SHA.
Retain the upstream text and copyright notice under the required pinned vendor path.
The local `VETTING.json` records provenance, individual hashes and scope.

This is documentation, with no executable scripts, external instruction loading or
installer. Upstream React Aria examples and source-specific paths are illustrations;
QVELT keeps Radix and the existing stack. Ponytail remains primary; the design brief,
AGENTS.md and security constraints take precedence. Use the useful guidance to
improve touch targets and preserve keyboard/focus behavior, with browser regression
tests. Do not claim a complete WCAG audit from an automated scan.

Other uploaded bundles are not installed: see `docs/skills/SKILLS.md` for the actual
inspection scope, license distinction, symlink entries and the 32 MiB transfer
limit. Do not treat unreviewed source material as executable project instructions.
