#!/usr/bin/env python3
"""Static checks of this repo's workflows (the same rules GameCove's packaging/tests/release.sh applied while they
lived there), and, with the pinned GameCove source next to it, that the identities the workflows sign with are exactly
the ones the app and its helper pin.

usage: python3 tests/check_workflows.py <this repo> [<GameCove checkout at gamecove-source.env's commit>]
Nothing is downloaded and nothing is written. Exit 1 with one line per problem.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import yaml

DATA = ("upscalers.yml", "firmware.yml", "gamedb.yml", "device-photos.yml")
SIGNED = {"upscalers.yml": "upscalers.json", "firmware.yml": "firmware.json.gz"}
SCRAPER = {"upscalers.yml": "tools/upscalers/build.py", "firmware.yml": "gamedb.firmware.build",
           "gamedb.yml": "gamedb.build", "device-photos.yml": "tools/device_photos/build.py"}
PIN = re.compile(r"^[^@ ]+@[0-9a-f]{40}$")
REPO = "IHulkSmashI/GameCove-data"

problems: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        problems.append(msg)


def runs(job: dict) -> str:
    return "\n".join(s.get("run", "") for s in job.get("steps", []))


def every_workflow(root: str) -> None:
    wfdir = os.path.join(root, ".github", "workflows")
    raw_all = {}
    for n in sorted(os.listdir(wfdir)):
        if not n.endswith(".yml"):
            continue
        raw = open(os.path.join(wfdir, n), encoding="utf-8").read()
        raw_all[n] = raw
        doc = yaml.safe_load(raw)
        check(doc.get("permissions") == {}, f"{n}: least privilege: nothing at the top level")
        for line in raw.splitlines():
            m = re.match(r"^\s*(?:- )?uses:\s*(\S+)(.*)$", line)
            if m:
                check(bool(PIN.match(m.group(1))) and re.match(r"\s+# v[0-9]", m.group(2)) is not None,
                      f"{n}: action not pinned by commit with its tag in a comment: {line.strip()}")
            if "pip install" in line:
                check(re.search(r"pip install --require-hashes --no-deps -r [./]*tools/ci/requirements-[a-z]*\.txt$",
                                line) is not None, f"{n}: pip install without hashes: {line.strip()}")
            if "gh release create" in line:
                check("--latest=false" in line, f"{n}: a data release must never become 'latest': {line.strip()}")
        for name, job in doc["jobs"].items():
            for s in job.get("steps", []):
                check("${{" not in s.get("run", ""), f"{n}:{name}: ${{{{ }}}} inside run: ({s.get('name', '?')})")
                if s.get("uses", "").startswith("actions/checkout@"):
                    check(s.get("with", {}).get("persist-credentials") is False, f"{n}:{name}: checkout keeps a token")
            if (job.get("permissions") or {}).get("id-token") == "write":
                check(job.get("environment") == "nightly", f"{n}:{name}: signs outside the 'nightly' environment")
    for n in DATA:
        check(n in raw_all, f"{n} is missing")


def source_pin(root: str) -> tuple[str, str]:
    text = open(os.path.join(root, "gamecove-source.env"), encoding="utf-8").read()
    repo = re.search(r"^GAMECOVE_REPO=(.*)$", text, re.M)
    commit = re.search(r"^GAMECOVE_COMMIT=(.*)$", text, re.M)
    check(bool(repo) and repo.group(1) == "IHulkSmashI/GameCove",
          "gamecove-source.env: GAMECOVE_REPO must be IHulkSmashI/GameCove")
    check(bool(commit) and re.fullmatch(r"[0-9a-f]{40}", commit.group(1)) is not None and set(commit.group(1)) != {"0"},
          "gamecove-source.env: GAMECOVE_COMMIT must be a full commit id")
    return (repo.group(1) if repo else "", commit.group(1) if commit else "")


def data_workflows(root: str) -> dict[str, list[str]]:
    """Per signing workflow, the identity regexes its own self-checks use, evaluated for this repo."""
    idents: dict[str, list[str]] = {}
    for n in DATA:
        doc = yaml.safe_load(open(os.path.join(root, ".github", "workflows", n), encoding="utf-8"))
        on = doc.get("on", doc.get(True))
        check("schedule" in on and "workflow_dispatch" in on, f"{n}: scheduled and by hand")
        jobs = doc["jobs"]
        check(set(jobs) == {"build", "publish"}, f"{n}: jobs are build and publish: {list(jobs)}")
        b, p = jobs["build"], jobs["publish"]
        check(b.get("permissions") == {"contents": "read"}, f"{n}: build is read-only: {b.get('permissions')}")
        check(b.get("if") == "github.ref == 'refs/heads/main'", f"{n}: build for publishing only on main")
        check(p.get("needs") == "build", f"{n}: publish needs build")
        brun, prun = runs(b), runs(p)
        check(SCRAPER[n] in brun, f"{n}: build runs {SCRAPER[n]}")
        for bad in ("sign-blob", "gh release upload", "gh release create", "gh release edit"):
            check(bad not in brun, f"{n}: build must not sign or publish ({bad})")
        for bad in ("pip install", "pytest", SCRAPER[n]):
            check(bad not in prun, f"{n}: publish must not run the builder or third-party packages ({bad})")
        check(any(s.get("uses", "").startswith("actions/upload-artifact@") for s in b["steps"]), f"{n}: build hands over an artifact")
        check(any(s.get("uses", "").startswith("actions/download-artifact@") for s in p["steps"]), f"{n}: publish takes the artifact")
        # the GameCove source: the pinned commit, checked out read-only, verified
        co = [s for s in b["steps"] if s.get("uses", "").startswith("actions/checkout@")]
        want = ["gamecove-source.env"] + (["tests/check_environment.py"] if n in SIGNED else [])
        check(len(co) == 2 and co[0]["with"].get("sparse-checkout", "").split() == want
              and co[1]["with"].get("repository") == "${{ steps.src.outputs.repo }}"
              and co[1]["with"].get("ref") == "${{ steps.src.outputs.commit }}",
              f"{n}: build checks out GameCove at gamecove-source.env's commit")
        check('test "$(git rev-parse HEAD)" = "$COMMIT"' in brun, f"{n}: build checks it got exactly the pinned commit")
        check("grep -qxE '[0-9a-f]{40}'" in brun, f"{n}: the pin must be a full commit id")
        if n in SIGNED:
            check(p.get("environment") == "nightly", f"{n}: publish runs in the 'nightly' environment")
            names = [s.get("run", "") for s in b["steps"]]
            env_i = [i for i, x in enumerate(names) if "tests/check_environment.py environment.json policies.json" in x]
            check(bool(env_i) and env_i[0] < 3, f"{n}: build checks the 'nightly' environment before anything else")
            check(p.get("permissions") == {"contents": "write", "id-token": "write"}, f"{n}: publish permissions {p.get('permissions')}")
            pco = [s for s in p["steps"] if s.get("uses", "").startswith("actions/checkout@")]
            check(len(pco) == 1 and pco[0]["with"].get("ref") == "${{ needs.build.outputs.commit }}",
                  f"{n}: publish checks out the commit the build used")
            check('test "$(git rev-parse HEAD)" = "$COMMIT"' in prun, f"{n}: publish checks the commit")
            f = SIGNED[n]
            check(f"cosign sign-blob --yes --bundle dist/{f}.sigstore.json dist/{f}" in prun, f"{n}: signs {f}")
            check(f"dist/{f}.sigstore.json" in prun and "--clobber" in prun, f"{n}: publishes the signature")
            check("COSIGN_SHA256=" in prun and "cosign-release: ${{ steps.cosign.outputs.version }}" in yaml.safe_dump(p),
                  f"{n}: signs with the cosign get-gamecove.sh pins")
            found = re.findall(r'"(\(\?i\)\^https://github\\\.com/\$\(printf .*?\$)"', brun + "\n" + prun)
            ev = []
            for expr in found:
                got = subprocess.run(["sh", "-c", 'printf "%s" "' + expr + '"'], env={"REPO": REPO, "PATH": "/usr/bin:/bin"},
                                     capture_output=True, text=True, check=True).stdout
                ev.append(got)
            check(bool(ev) and len(set(ev)) == 1, f"{n}: its identity checks disagree: {ev}")
            idents[n] = ev
        else:
            check(p.get("permissions") == {"contents": "write"}, f"{n}: publish permissions {p.get('permissions')}")
            check(not any(s.get("uses", "").startswith("actions/checkout@") for s in p["steps"]), f"{n}: publish needs no code")
            check("environment" not in p or p.get("environment") == "nightly", f"{n}: publish environment")
    up = yaml.safe_load(open(os.path.join(root, ".github", "workflows", "upscalers.yml"), encoding="utf-8"))["jobs"]["publish"]
    r = [s.get("run", "") for s in up["steps"]]
    chk = [i for i, x in enumerate(r) if "tools/upscalers/check_plan.py dist" in x]
    sig = [i for i, x in enumerate(r) if "cosign sign-blob" in x]
    check(bool(chk) and bool(sig) and chk[0] < sig[0], "upscalers.yml: check_plan.py must run before signing")
    ub = yaml.safe_load(open(os.path.join(root, ".github", "workflows", "upscalers.yml"), encoding="utf-8"))["jobs"]["build"]
    check('grep -qxF "REPO = \\"$REPO\\"" packaging/helpers/gamecove_upscale/mirror.py' in runs(ub),
          "upscalers.yml: build must check the pinned commit names this repo (mirror.py REPO)")
    allr = "\n".join(r)
    check(allr.count("--clobber") == 1 and "dist/upscalers.json.sigstore.json dist/upscalers.json.sha256 --clobber" in allr,
          "upscalers.yml: only the index is replaced; mirror files never")
    check('gh release upload "$tag" "dist/$path"' in allr and allr.index('gh release upload "$tag" "dist/$path"') < allr.index("--clobber"),
          "upscalers.yml: files first, the index last")
    g = yaml.safe_load(open(os.path.join(root, ".github", "workflows", "gamedb.yml"), encoding="utf-8"))["jobs"]["publish"]
    check("gh release upload gamedb dist/NOTICE.md" in runs(g) and "gh release edit gamedb --notes-file dist/NOTICE.md" in runs(g),
          "gamedb.yml: publishes NOTICE.md as an asset and as the notes")
    return idents


def against_source(src: str, idents: dict[str, list[str]]) -> None:
    """The identities this repo signs with are exactly what GameCove pins, and GameCove downloads from here."""
    mirror = open(os.path.join(src, "packaging/helpers/gamecove_upscale/mirror.py"), encoding="utf-8").read()
    helper = re.search(r'^SIGNER_IDENTITY = r"(.*)"$', mirror, re.M).group(1)
    check(idents.get("upscalers.yml", [None])[0] == helper, f"upscalers.yml signs as {idents.get('upscalers.yml')}, the helper pins {helper}")
    check(re.search(r'^REPO = "IHulkSmashI/GameCove-data"$', mirror, re.M) is not None, "mirror.py REPO must be this repo")
    gdp = os.path.join(src, "app/scripts/system/data_repo.gd")
    if not os.path.isfile(gdp):
        check(False, "the pinned GameCove has no app/scripts/system/data_repo.gd: it predates the move, bump gamecove-source.env")
        return
    gd = open(gdp, encoding="utf-8").read()
    app = re.search(r'^const FIRMWARE_SIGNER := "(.*)"$', gd, re.M).group(1).replace("\\\\", "\\")
    check(idents.get("firmware.yml", [None])[0] == app, f"firmware.yml signs as {idents.get('firmware.yml')}, the app pins {app}")
    up = re.search(r'^const UPSCALERS_SIGNER := "(.*)"$', gd, re.M).group(1).replace("\\\\", "\\")
    check(up == helper, "data_repo.gd UPSCALERS_SIGNER must equal mirror.py SIGNER_IDENTITY")
    check(f'const RELEASES := "https://github.com/{REPO}/releases/download/"' in gd, "data_repo.gd must download from this repo")
    for comp, rule in (("tools/upscalers/build.py", r"^MIN_AGE_H = 72\b"),):
        check(re.search(rule, open(os.path.join(src, comp), encoding="utf-8").read(), re.M) is not None,
              f"{comp}: the 72 h minimum release age")
    ggs = open(os.path.join(src, "packaging/get-gamecove.sh"), encoding="utf-8").read()
    for k in ("COSIGN_VERSION", "COSIGN_SHA256"):
        a = re.search(r"^%s=(\S+)$" % k, ggs, re.M).group(1)
        b = re.search(r'^%s = "(\S+)"$' % k, mirror, re.M).group(1)
        check(a == b, f"{k}: get-gamecove.sh {a} vs mirror.py {b}")


def main(argv: list[str]) -> int:
    root = argv[1]
    every_workflow(root)
    source_pin(root)
    idents = data_workflows(root)
    if len(argv) > 2:
        against_source(argv[2], idents)
    for p in problems:
        print("FAIL:", p)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
