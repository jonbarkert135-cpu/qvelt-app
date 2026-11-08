"""The offline skill check must reject changed or extra vendored content."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def skill_tree(tmp_path):
    script = Path(__file__).parents[3] / "scripts/check_skills.py"
    target = tmp_path / "scripts/check_skills.py"
    target.parent.mkdir()
    shutil.copyfile(script, target)
    vendor = tmp_path / ".agents/skills/vendor" / ("example@" + "a" * 40)
    vendor.mkdir(parents=True)
    contents = {
        "SKILL.md": "---\nname: example\ndescription: A complete test description for the vendored example skill.\n---\nText only.\n",
        "LICENSE": "Test license fixture only.\n",
    }
    for name, content in contents.items():
        (vendor / name).write_text(content)
    (vendor / "VETTING.json").write_text(json.dumps({
        "commit": "a" * 40, "upstream_repository": "https://github.com/example/skills",
        "files": {name: hashlib.sha256(value.encode()).hexdigest()
                  for name, value in contents.items()},
    }))
    return target, vendor


def run_check(script):
    return subprocess.run([sys.executable, str(script)], capture_output=True, text=True, check=False)


def test_vendored_skill_hashes_and_membership_are_checked(skill_tree):
    script, vendor = skill_tree
    assert run_check(script).returncode == 0
    (vendor / "LICENSE").write_text("Modified after review")
    assert run_check(script).returncode != 0


def test_unreviewed_script_and_symlink_are_rejected(skill_tree):
    script, vendor = skill_tree
    added = vendor / "unreviewed.py"
    added.write_text("raise SystemExit('must never run')")
    assert run_check(script).returncode != 0
    added.unlink()
    nested = vendor / "rules"
    nested.mkdir()
    (nested / "VETTING.json").write_text("Unreviewed nested file")
    assert run_check(script).returncode != 0
    (nested / "VETTING.json").unlink()
    (vendor / "outside").symlink_to(script)
    assert run_check(script).returncode != 0
