"""Validate local skills and offline integrity of reviewed, pinned vendor files."""
import hashlib
import json
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent / ".agents" / "skills"
errors: list[str] = []
count = 0
vendor_count = 0


def check_frontmatter(directory: pathlib.Path, expected_name: str) -> None:
    f = directory / "SKILL.md"
    if not f.exists():
        errors.append(f"{directory.name}: missing SKILL.md")
        return
    m = re.match(r"^---\n(.*?)\n---\n", f.read_text(encoding="utf-8"), re.DOTALL)
    if not m:
        errors.append(f"{directory.name}: missing frontmatter")
        return
    fm = dict(
        line.split(":", 1) for line in m.group(1).splitlines() if ":" in line
    )
    name = fm.get("name", "").strip()
    desc = fm.get("description", "").strip()
    if name != expected_name:
        errors.append(f"{directory.name}: skill name does not match directory")
    if len(desc) < 40:
        errors.append(f"{directory.name}: description too short")


for d in sorted(p for p in root.iterdir() if p.is_dir() and p.name != "vendor"):
    if d.is_symlink():
        errors.append(f"{d.name}: symlinks are not allowed")
        continue
    check_frontmatter(d, d.name)
    count += 1

vendor_root = root / "vendor"
if vendor_root.is_symlink():
    errors.append("vendor: symlinks are not allowed")
elif vendor_root.exists():
    for directory in sorted(vendor_root.iterdir()):
        if directory.is_symlink() or not directory.is_dir():
            errors.append(f"{directory.name}: expected a directory without symlinks")
            continue
        files = list(directory.rglob("*"))
        if any(p.is_symlink() for p in files):
            errors.append(f"{directory.name}: symlinks are not allowed")
            continue
        try:
            info = json.loads((directory / "VETTING.json").read_text(encoding="utf-8"))
            commit = info["commit"]
            if not re.fullmatch(r"[0-9a-f]{40}", commit) or not directory.name.endswith("@" + commit):
                raise ValueError("invalid commit pin")
            if not re.fullmatch(r"https://github.com/[\w.-]+/[\w.-]+", info["upstream_repository"]):
                raise ValueError("invalid upstream identity")
            hashes = info["files"]
            actual = {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in files if p.is_file() and p != directory / "VETTING.json"}
            if not {"SKILL.md", "LICENSE"} <= set(hashes) or actual != hashes:
                raise ValueError("file hashes or reviewed file membership differ")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{directory.name}: invalid vendor integrity metadata ({exc})")
            continue
        check_frontmatter(directory, directory.name.rsplit("@", 1)[0])
        vendor_count += 1
if count + vendor_count == 0:
    errors.append("No skills found")
if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"OK: {count} project skills valid; {vendor_count} pinned vendor skills verified")
