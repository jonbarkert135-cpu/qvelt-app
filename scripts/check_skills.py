#!/usr/bin/env python3
"""Validate .agents/skills structure: each skill dir has SKILL.md with matching name and a description."""
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent / ".agents" / "skills"
errors: list[str] = []
count = 0
for d in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "vendor"):
    f = d / "SKILL.md"
    if not f.exists():
        errors.append(f"{d.name}: missing SKILL.md")
        continue
    m = re.match(r"^---\n(.*?)\n---\n", f.read_text(encoding="utf-8"), re.S)
    if not m:
        errors.append(f"{d.name}: missing frontmatter")
        continue
    fm = dict(
        line.split(":", 1) for line in m.group(1).splitlines() if ":" in line
    )
    name = fm.get("name", "").strip()
    desc = fm.get("description", "").strip()
    if name != d.name:
        errors.append(f"{d.name}: name '{name}' does not match directory")
    if len(desc) < 40:
        errors.append(f"{d.name}: description too short")
    count += 1
if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"OK: {count} project skills valid")
