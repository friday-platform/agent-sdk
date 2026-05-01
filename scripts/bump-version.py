#!/usr/bin/env python3
"""Bump the friday-agent-sdk version and tag a release.

Usage:
    python3 scripts/bump-version.py             # patch bump (default)
    python3 scripts/bump-version.py --minor     # X.Y+1.0
    python3 scripts/bump-version.py --major     # X+1.0.0
    python3 scripts/bump-version.py --set 1.2.3 # explicit
    python3 scripts/bump-version.py --dry-run   # show plan, change nothing
    python3 scripts/bump-version.py --commit    # also `git commit` the changes
    python3 scripts/bump-version.py --tag       # implies --commit, also `git tag vX.Y.Z`
    python3 scripts/bump-version.py --push      # implies --tag, also `git push` both

Updates four in-tree version files in lockstep:
    packages/python/pyproject.toml                (project.version)
    packages/python/friday_agent_sdk/__init__.py  (__version__)
    packages/python/package.json                  (version)
    package.json                                  (version)

Also moves CHANGELOG.md `## [Unreleased]` under a fresh
`## [<new>] - YYYY-MM-DD` heading and inserts a new empty `[Unreleased]`
above it.

Source of truth for the current version is `packages/python/pyproject.toml`.
The script verifies all four files agree before bumping.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Each entry: (path, regex matching the version-bearing line). The regex must
# expose the version literal as group(1).
VERSION_FILES: list[tuple[Path, re.Pattern[str]]] = [
    (
        REPO_ROOT / "packages/python/pyproject.toml",
        re.compile(r'^version = "([^"]+)"', re.MULTILINE),
    ),
    (
        REPO_ROOT / "packages/python/friday_agent_sdk/__init__.py",
        re.compile(r'^__version__ = "([^"]+)"', re.MULTILINE),
    ),
    (
        REPO_ROOT / "packages/python/package.json",
        re.compile(r'^  "version": "([^"]+)"', re.MULTILINE),
    ),
    (
        REPO_ROOT / "package.json",
        re.compile(r'^  "version": "([^"]+)"', re.MULTILINE),
    ),
]

SOURCE_OF_TRUTH = VERSION_FILES[0]  # pyproject.toml
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+][\w.-]+)?$")


def read_current_version(path: Path, pattern: re.Pattern[str]) -> str:
    text = path.read_text()
    m = pattern.search(text)
    if m is None:
        sys.exit(f"error: could not find version literal in {path.relative_to(REPO_ROOT)}")
    return m.group(1)


def bump(current: str, *, level: str) -> str:
    m = SEMVER_RE.match(current)
    if m is None:
        sys.exit(f"error: current version {current!r} is not semver-shaped")
    major, minor, patch = (int(g) for g in m.groups())
    if level == "patch":
        patch += 1
    elif level == "minor":
        minor += 1
        patch = 0
    elif level == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise AssertionError(level)
    return f"{major}.{minor}.{patch}"


def write_version(path: Path, pattern: re.Pattern[str], new_version: str) -> str:
    """Replace the version literal on the matched line. Returns the previous version."""
    text = path.read_text()
    found: list[str] = []

    def repl(m: re.Match[str]) -> str:
        old_version = m.group(1)
        found.append(old_version)
        return m.group(0).replace(f'"{old_version}"', f'"{new_version}"', 1)

    new_text, n = pattern.subn(repl, text, count=1)
    if n == 0:
        sys.exit(f"error: pattern did not match in {path.relative_to(REPO_ROOT)}")
    path.write_text(new_text)
    return found[0]


def update_changelog(new_version: str) -> str | None:
    """Insert a dated heading under `## [Unreleased]`. Returns the inserted
    heading on success, None if no [Unreleased] section was found.
    """
    path = REPO_ROOT / "CHANGELOG.md"
    text = path.read_text()
    pattern = re.compile(r"^## \[Unreleased\]\s*$", re.MULTILINE)
    if not pattern.search(text):
        return None
    today = date.today().isoformat()
    new_heading = f"## [{new_version}] - {today}"
    # Trailing `\n` keeps the dated heading separated from whatever follows
    # (the previous release heading or a section). Without it, `vp fmt`
    # rejects the file with a "missing blank line before heading" error.
    new_text = pattern.sub(f"## [Unreleased]\n\n{new_heading}\n", text, count=1)
    path.write_text(new_text)
    return new_heading


def run_git(args: list[str], *, dry_run: bool) -> None:
    cmd = ["git", *args]
    print(f"  $ {' '.join(cmd)}")
    if dry_run:
        return
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    level = parser.add_mutually_exclusive_group()
    level.add_argument("--major", action="store_const", dest="level", const="major")
    level.add_argument("--minor", action="store_const", dest="level", const="minor")
    level.add_argument("--patch", action="store_const", dest="level", const="patch")
    level.add_argument(
        "--set",
        dest="explicit",
        metavar="X.Y.Z",
        help="Set an explicit version instead of auto-bumping",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without modifying any files",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="After bumping, run `git commit -am 'chore(release): cut <new>'`",
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        help="Imply --commit, then `git tag v<new>`",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Imply --tag, then `git push && git push origin v<new>`",
    )
    args = parser.parse_args()
    args.level = args.level or "patch"
    if args.push:
        args.tag = True
    if args.tag:
        args.commit = True
    return args


def main() -> int:
    args = parse_args()

    # 1. Determine the new version.
    current = read_current_version(*SOURCE_OF_TRUTH)
    if args.explicit is not None:
        if not SEMVER_RE.match(args.explicit):
            sys.exit(f"error: --set {args.explicit!r} is not semver-shaped")
        new = args.explicit
    else:
        new = bump(current, level=args.level)

    print(f"Current version: {current}")
    print(f"New version:     {new}")
    if current == new:
        sys.exit("error: new version is the same as current — nothing to do")

    # 2. Verify all four files agree on the current version.
    seen: set[str] = set()
    for path, pattern in VERSION_FILES:
        if not path.exists():
            sys.exit(f"error: {path.relative_to(REPO_ROOT)} not found")
        seen.add(read_current_version(path, pattern))
    if len(seen) > 1:
        sys.exit(
            f"error: version-tracking files disagree before bump: {sorted(seen)}\n"
            "fix the drift manually before running this script"
        )

    print()

    # 3. Apply the bump.
    if args.dry_run:
        print("(dry run — no files modified)")
        for path, _ in VERSION_FILES:
            print(f"  · {path.relative_to(REPO_ROOT)}: {current} → {new}")
        print(f"  · CHANGELOG.md: would insert `## [{new}] - {date.today().isoformat()}`")
        print()
    else:
        for path, pattern in VERSION_FILES:
            write_version(path, pattern, new)
            print(f"  ✓ {path.relative_to(REPO_ROOT)}: {current} → {new}")
        heading = update_changelog(new)
        if heading is not None:
            print(f"  ✓ CHANGELOG.md: inserted `{heading}`")
        else:
            print("  · CHANGELOG.md: no `## [Unreleased]` section, left alone")

    # 4. Optional git operations.
    if args.commit or args.tag or args.push:
        print()
        print("Git:")
        run_git(["commit", "-am", f"chore(release): cut {new}"], dry_run=args.dry_run)
        if args.tag:
            run_git(["tag", f"v{new}"], dry_run=args.dry_run)
        if args.push:
            run_git(["push"], dry_run=args.dry_run)
            run_git(["push", "origin", f"v{new}"], dry_run=args.dry_run)
    else:
        print(
            "\nNext steps:\n"
            "  git diff\n"
            "  # ...edit CHANGELOG.md if you want to clean up the new section...\n"
            f'  git commit -am "chore(release): cut {new}"\n'
            f"  git tag v{new}\n"
            f"  git push && git push origin v{new}\n"
            "\n"
            "Or rerun with --push to do all of that automatically."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
