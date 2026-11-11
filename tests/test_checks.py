#!/usr/bin/env python3
"""The checks catch what they're for: a missing or loosened "nightly" environment, and workflows that lose a rule.

usage: python3 -I tests/test_checks.py <this repo>
(The GameCove side is tests/fixtures/source: the lines check_workflows.py reads, as GameCove has them since the move,
so these tests don't depend on the pinned commit.)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_environment  # noqa: E402


def env_case(env, pols) -> list[str]:
    with tempfile.TemporaryDirectory() as d:
        e, p = os.path.join(d, "e.json"), os.path.join(d, "p.json")
        open(e, "w").write(json.dumps(env) if env is not None else "")
        open(p, "w").write(json.dumps(pols) if pols is not None else "")
        return check_environment.problems(e, p)


GOOD_ENV = {"name": "nightly", "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True}}
MAIN = {"branch_policies": [{"name": "main", "type": "branch"}]}
assert env_case(GOOD_ENV, MAIN) == []
assert env_case(None, None) and "doesn't exist" in env_case(None, None)[0]
assert env_case({"message": "Not Found"}, None)
assert env_case(dict(GOOD_ENV, deployment_branch_policy=None), MAIN), "all branches may deploy"
assert env_case(dict(GOOD_ENV, deployment_branch_policy={"protected_branches": True, "custom_branch_policies": False}), MAIN)
assert env_case(GOOD_ENV, {"branch_policies": [{"name": "main", "type": "branch"}, {"name": "dev", "type": "branch"}]})
assert env_case(GOOD_ENV, {"branch_policies": [{"name": "*", "type": "branch"}]})
assert env_case(GOOD_ENV, {"branch_policies": [{"name": "main", "type": "tag"}]})

root = sys.argv[1]
src = os.path.join(HERE, "fixtures", "source")
check = [sys.executable, "-I", os.path.join(HERE, "check_workflows.py")]
assert subprocess.run(check + [root, src], capture_output=True).returncode == 0, "the real workflows pass"


def mutated(path: str, old: str, new: str) -> str:
    """check_workflows.py's output for a copy of this repo with one workflow changed."""
    with tempfile.TemporaryDirectory() as d:
        shutil.copytree(os.path.join(root, ".github"), os.path.join(d, ".github"))
        shutil.copy(os.path.join(root, "gamecove-source.env"), d)
        p = os.path.join(d, ".github", "workflows", path)
        s = open(p).read()
        assert old in s, (path, old)
        open(p, "w").write(s.replace(old, new, 1))
        r = subprocess.run(check + [d, src], capture_output=True, text=True)
        assert r.returncode == 1, (path, old, r.stdout)
        return r.stdout


assert "nightly" in mutated("upscalers.yml", "    environment: nightly\n", "")
assert "nightly" in mutated("firmware.yml", "    environment: nightly\n", "    environment: other\n")
assert "read-only" in mutated("gamedb.yml", "      contents: read\n", "      contents: write\n")
assert "pinned" in mutated("device-photos.yml", "@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0",
                           "@v4 # v4.4.0")
assert "latest" in mutated("firmware.yml", "--latest=false", "")
assert "token" in mutated("gamedb.yml", "persist-credentials: false", "persist-credentials: true")
assert "signs as" in mutated("upscalers.yml", r"workflows/upscalers\.yml@refs/heads/main$", r"workflows/upscalers\.yml@refs/heads/.*$")
assert "checks out GameCove" in mutated("firmware.yml", "            tests/check_environment.py\n", "")
assert "only on main" in mutated("upscalers.yml", "    if: github.ref == 'refs/heads/main'\n", "")
assert "pinned commit" in mutated("gamedb.yml", 'run: test "$(git rev-parse HEAD)" = "$COMMIT"', "run: echo skipped")
assert "mirror files never" in mutated("upscalers.yml", 'gh release upload "$tag" "dist/$path"', 'gh release upload "$tag" "dist/$path" --clobber')
assert "pinned commit names this repo" in mutated("upscalers.yml", "REPO = \\\"$REPO\\\"", "REPO = x")

# the GameCove side: a pin that predates the move, or an app that pins another identity, fails
with tempfile.TemporaryDirectory() as d:
    shutil.copytree(src, os.path.join(d, "s"))
    mp = os.path.join(d, "s", "packaging/helpers/gamecove_upscale/mirror.py")
    text = open(mp).read()
    open(mp, "w").write(text.replace("GameCove-data", "GameCove"))
    r = subprocess.run(check + [root, os.path.join(d, "s")], capture_output=True, text=True)
    out = r.stdout + r.stderr
    assert "the helper pins" in out and "mirror.py REPO" in out, out
with tempfile.TemporaryDirectory() as d:
    shutil.copytree(src, os.path.join(d, "s"))
    gd = os.path.join(d, "s", "app/scripts/system/data_repo.gd")
    text = open(gd).read()
    assert "firmware\\\\.yml" in text
    open(gd, "w").write(text.replace("firmware\\\\.yml", "upscalers\\\\.yml"))
    r = subprocess.run(check + [root, os.path.join(d, "s")], capture_output=True, text=True)
    out = r.stdout + r.stderr
    assert "the app pins" in out, out
print("test_checks: all passed")
