#!/usr/bin/env python3
"""The "nightly" environment the signing jobs run in exists and only main can deploy to it.

GitHub creates a missing environment on the first run that names it, WITHOUT protection rules, so the signing
workflows run this in their read-only build job first: a missing or loosened environment fails the run before any
job names it, and the owner sees why (README.md, "Owner settings").

usage: python3 -I tests/check_environment.py <environment.json> <deployment-branch-policies.json>
(the answers of GET /repos/{repo}/environments/nightly and .../nightly/deployment-branch-policies; an empty or
missing file means the environment doesn't exist)
"""
from __future__ import annotations

import json
import sys


def problems(env_path: str, pol_path: str) -> list[str]:
    try:
        env = json.load(open(env_path, encoding="utf-8"))
    except (OSError, ValueError):
        env = {}
    if env.get("name", "").lower() != "nightly":
        return ["the 'nightly' environment doesn't exist: create it (Settings > Environments > New environment)"]
    out = []
    dbp = env.get("deployment_branch_policy") or {}
    if not dbp.get("custom_branch_policies") or dbp.get("protected_branches"):
        out.append("'nightly' must allow 'Selected branches and tags', not all branches or protected branches")
    try:
        pols = json.load(open(pol_path, encoding="utf-8")).get("branch_policies", [])
    except (OSError, ValueError):
        pols = []
    got = sorted((p.get("type", "branch"), p.get("name")) for p in pols)
    if got != [("branch", "main")]:
        out.append(f"'nightly' must allow exactly one rule, branch main (has {got})")
    return out


def main(argv: list[str]) -> int:
    found = problems(argv[1], argv[2])
    for p in found:
        print(f"::error::{p}")
    if not found:
        print("'nightly' exists and only main can deploy to it")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
