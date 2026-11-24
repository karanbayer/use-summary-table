#!/usr/bin/env python3
"""The app has one version, carried by every file below; the Dockerfile's `LABEL version` is the source.

The deploy workflow raises it by one before each deploy, commits the files and deploys with exactly that version,
so Agentrix, the image and the repo always agree (a version Agentrix has seen before makes it reuse its cache).

  python3 scripts/bump_version.py           # 1.2.79 -> 1.2.80 in every file; prints 1.2.80
  python3 scripts/bump_version.py --show    # prints the current version
  python3 scripts/bump_version.py --check   # exit 1 if the files disagree
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = r"\d+\.\d+\.\d+"

# (file, pattern with the version as group 2). Files that do not exist in this repo are skipped.
PLACES = [
    ("Dockerfile", rf'^(LABEL version=")({SEMVER})(")'),
    ("Dockerfile", rf"^(ENV AGENT_VERSION=)({SEMVER})()$"),
    ("agent-card.json", r'^(  "version": ")([^"]*)(")'),
    ("agenthub-agent.yaml", r'^(version: ")([^"]*)(")'),
]


def _found() -> list[tuple[str, str, str]]:
    out = []
    for name, pattern in PLACES:
        path = ROOT / name
        if not path.exists():
            continue
        m = re.search(pattern, path.read_text(encoding="utf-8"), re.M)
        if not m:
            raise SystemExit(f"{name}: no version line matching {pattern}")
        out.append((name, pattern, m.group(2)))
    return out


def current() -> str:
    found = _found()
    versions = {v for _, _, v in found}
    if len(versions) != 1 or not re.fullmatch(SEMVER, next(iter(versions))):
        raise SystemExit("version files disagree: " + ", ".join(f"{n}={v}" for n, _, v in found))
    return versions.pop()


def bump() -> str:
    major, minor, patch = current().split(".")
    new = f"{major}.{minor}.{int(patch) + 1}"
    for name, pattern, _ in _found():
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        path.write_text(re.sub(pattern, lambda m: m.group(1) + new + m.group(3), text, count=1, flags=re.M),
                        encoding="utf-8")
    return new


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    print(current() if arg in ("--show", "--check") else bump())
