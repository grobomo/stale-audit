#!/usr/bin/env python3
"""
Stale Project Auditor — interactive archive tool.

Scans git repos in a projects directory, scores staleness, and presents
an interactive checkbox UI to select repos for archiving.

Usage:
    python stale-audit.py                      # Interactive mode
    python stale-audit.py --dry-run            # Show what would be archived
    python stale-audit.py --summary            # Print summary only, no interaction
    python stale-audit.py --dir /path/to/root  # Override projects directory
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime
from pathlib import Path


def get_base_dir():
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--dir="):
            return Path(arg.split("=", 1)[1])
        if arg == "--dir" and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1])
    return Path(os.environ.get("PROJECTS_DIR", Path.home() / "Documents" / "ProjectsCL1"))


BASE = get_base_dir()
ARCHIVE = BASE / "Archive"

# Skip these when scanning top-level
TOP_LEVEL_SKIP = {"Archive", "scripts", ".claude", "node_modules", ".git"}


def discover_groups():
    """Auto-detect group dirs (any _ prefixed dir) plus top-level."""
    groups = []
    if not BASE.exists():
        return groups
    for child in sorted(BASE.iterdir()):
        if child.is_dir() and child.name.startswith("_"):
            groups.append((child.name.lstrip("_"), child))
            TOP_LEVEL_SKIP.add(child.name)
    groups.append(("top-level", BASE))
    return groups


# --- Staleness scoring ---

def score_staleness(info):
    """Higher = more stale. Max ~100."""
    s = 0
    if info["no_commits"]:
        s += 50
    if info["empty_git"]:
        s += 40
    if not info["has_remote"]:
        s += 10
    if not info["has_publish_json"]:
        s += 3
    if not info["has_secret_scan"]:
        s += 2
    if info["days_since_commit"] is not None:
        days = info["days_since_commit"]
        if days > 180:
            s += 30
        elif days > 90:
            s += 20
        elif days > 60:
            s += 15
        elif days > 30:
            s += 10
        elif days > 14:
            s += 5
    return s


def git_cmd(repo_path, *args):
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_path)] + list(args),
            capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip(), r.returncode
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "", 1


def scan_repo(repo_path, group):
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return None

    _, rc = git_cmd(repo_path, "rev-parse", "--git-dir")
    empty_git = rc != 0

    last_date_str, rc = git_cmd(repo_path, "log", "-1", "--format=%ci")
    no_commits = rc != 0 or not last_date_str
    last_commit = None
    days_since = None
    if not no_commits:
        try:
            last_commit = datetime.strptime(last_date_str[:10], "%Y-%m-%d")
            days_since = (datetime.now() - last_commit).days
        except ValueError:
            no_commits = True

    count_str, _ = git_cmd(repo_path, "rev-list", "--count", "HEAD")
    commit_count = int(count_str) if count_str.isdigit() else 0

    remote_out, _ = git_cmd(repo_path, "remote", "-v")
    has_remote = bool(remote_out.strip())

    has_publish = (repo_path / ".github" / "publish.json").exists()
    has_scan = (repo_path / ".github" / "workflows" / "secret-scan.yml").exists()

    user_out, _ = git_cmd(repo_path, "config", "user.name")

    info = {
        "name": repo_path.name,
        "path": repo_path,
        "group": group,
        "empty_git": empty_git,
        "no_commits": no_commits,
        "last_commit": last_commit,
        "days_since_commit": days_since,
        "commit_count": commit_count,
        "has_remote": has_remote,
        "has_publish_json": has_publish,
        "has_secret_scan": has_scan,
        "git_user": user_out or "NONE",
    }
    info["score"] = score_staleness(info)
    return info


def scan_all():
    groups = discover_groups()
    repos = []
    for group, scan_dir in groups:
        if not scan_dir.exists():
            continue
        for child in sorted(scan_dir.iterdir()):
            if not child.is_dir():
                continue
            if group == "top-level" and child.name in TOP_LEVEL_SKIP:
                continue
            info = scan_repo(child, group)
            if info:
                repos.append(info)
    repos.sort(key=lambda r: (-r["score"], r["name"]))
    return repos


# --- Display ---

def format_age(days):
    if days is None:
        return "never"
    if days == 0:
        return "today"
    if days == 1:
        return "1 day"
    if days < 30:
        return f"{days} days"
    if days < 60:
        return "1 month"
    months = days // 30
    return f"{months} months"


def staleness_color(score):
    if score >= 70:
        return "\033[91m"   # red
    if score >= 40:
        return "\033[93m"   # yellow
    if score >= 20:
        return "\033[33m"   # dark yellow
    if score >= 10:
        return "\033[36m"   # cyan
    return "\033[92m"       # green


def staleness_label_plain(score):
    if score >= 70:
        return "DEAD"
    if score >= 40:
        return "STALE"
    if score >= 20:
        return "AGING"
    if score >= 10:
        return "QUIET"
    return "ACTIVE"


def colored(text, score):
    return f"{staleness_color(score)}{text}\033[0m"


def print_summary(repos):
    print("\n\033[1m=== Project Staleness Audit ===\033[0m")
    print(f"    Base: {BASE}\n")

    current_label = None
    for r in repos:
        label = staleness_label_plain(r["score"])
        if label != current_label:
            current_label = label
            print(f"\n\033[1m--- {colored(label, r['score'])} (score {r['score']}+) ---\033[0m")

        age = format_age(r["days_since_commit"])
        date_str = r["last_commit"].strftime("%Y-%m-%d") if r["last_commit"] else "none"
        flags = []
        if r["empty_git"]:
            flags.append("empty .git")
        if r["no_commits"]:
            flags.append("no commits")
        if not r["has_remote"]:
            flags.append("no remote")
        if not r["has_publish_json"]:
            flags.append("no publish.json")
        if not r["has_secret_scan"]:
            flags.append("no secret-scan")

        flag_str = f"  \033[90m[{', '.join(flags)}]\033[0m" if flags else ""
        group_tag = f"\033[90m({r['group']})\033[0m"
        label_str = colored(f"{label:>6s}", r["score"])

        print(f"  {label_str}  {r['name']:<30s} {group_tag:<18s} last: {date_str:<12s} ({age}){flag_str}")

    dead = sum(1 for r in repos if r["score"] >= 70)
    stale = sum(1 for r in repos if 40 <= r["score"] < 70)
    aging = sum(1 for r in repos if 20 <= r["score"] < 40)
    quiet = sum(1 for r in repos if 10 <= r["score"] < 20)
    active = sum(1 for r in repos if r["score"] < 10)
    print(f"\n\033[1mTotal: {len(repos)} repos\033[0m — "
          f"\033[91m{dead} dead\033[0m, "
          f"\033[93m{stale} stale\033[0m, "
          f"\033[33m{aging} aging\033[0m, "
          f"\033[36m{quiet} quiet\033[0m, "
          f"\033[92m{active} active\033[0m\n")


# --- Interactive checkbox UI ---

def get_key():
    """Read a single keypress, return a named action."""
    if sys.platform == "win32":
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ch2 = msvcrt.getwch()
            return {"H": "up", "P": "down", "M": "right", "K": "left"}.get(ch2, "unknown")
        if ch == " ":
            return "space"
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x1b":
            return "esc"
        if ch.lower() == "a":
            return "a"
        if ch.lower() == "q":
            return "q"
        return ch
    else:
        import tty
        import termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    ch3 = sys.stdin.read(1)
                    return {"A": "up", "B": "down"}.get(ch3, "unknown")
                return "esc"
            if ch == " ":
                return "space"
            if ch in ("\r", "\n"):
                return "enter"
            if ch.lower() == "a":
                return "a"
            if ch.lower() == "q":
                return "q"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def interactive_select(repos):
    """Full-screen checkbox selector. Returns list of selected repo infos."""
    selected = set()
    cursor = 0
    scroll_offset = 0

    # Pre-select DEAD repos
    for i, r in enumerate(repos):
        if r["score"] >= 70:
            selected.add(i)

    while True:
        try:
            term_h = os.get_terminal_size().lines
        except OSError:
            term_h = 30
        visible_lines = max(term_h - 8, 5)

        if cursor < scroll_offset:
            scroll_offset = cursor
        if cursor >= scroll_offset + visible_lines:
            scroll_offset = cursor - visible_lines + 1

        # Draw
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.write("\033[1m  Select repos to archive\033[0m")
        sys.stdout.write(f"  \033[90m({len(selected)} selected, DEAD pre-checked)\033[0m\n")
        sys.stdout.write("  \033[90m[SPACE] toggle  [A] toggle all stale+  [ENTER] confirm  [Q] cancel\033[0m\n\n")

        end = min(scroll_offset + visible_lines, len(repos))
        for idx in range(scroll_offset, end):
            r = repos[idx]
            is_cursor = idx == cursor
            is_selected = idx in selected
            check = "\033[92m[x]\033[0m" if is_selected else "[ ]"
            pointer = ">" if is_cursor else " "
            label = colored(f"{staleness_label_plain(r['score']):>6s}", r["score"])
            age = format_age(r["days_since_commit"])
            date_str = r["last_commit"].strftime("%Y-%m-%d") if r["last_commit"] else "none"
            group_tag = f"\033[90m({r['group']})\033[0m"

            line = f"  {pointer} {check} {label}  {r['name']:<30s} {group_tag:<18s} {date_str} ({age})"
            if is_cursor:
                sys.stdout.write(f"\033[7m{line}\033[0m\n")
            else:
                sys.stdout.write(f"{line}\n")

        # Scroll indicators
        extras = []
        if scroll_offset > 0:
            extras.append(f"{scroll_offset} above")
        below = len(repos) - end
        if below > 0:
            extras.append(f"{below} below")
        if extras:
            sys.stdout.write(f"\n  \033[90m... {', '.join(extras)}\033[0m")

        sys.stdout.write(f"\n\n  \033[1m{len(selected)} selected\033[0m")
        sys.stdout.flush()

        key = get_key()
        if key == "up" and cursor > 0:
            cursor -= 1
        elif key == "down" and cursor < len(repos) - 1:
            cursor += 1
        elif key == "space":
            selected.symmetric_difference_update({cursor})
        elif key == "a":
            stale_set = {i for i, r in enumerate(repos) if r["score"] >= 40}
            if stale_set.issubset(selected):
                selected -= stale_set
            else:
                selected |= stale_set
        elif key == "enter":
            break
        elif key in ("q", "esc"):
            sys.stdout.write("\033[2J\033[H")
            return []

    sys.stdout.write("\033[2J\033[H")
    return [repos[i] for i in sorted(selected)]


# --- Archive ---

def archive_repos(to_archive, dry_run=False):
    if not to_archive:
        print("Nothing selected.")
        return

    ARCHIVE.mkdir(exist_ok=True)
    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n\033[1m{prefix}Archiving {len(to_archive)} repos:\033[0m\n")

    for r in to_archive:
        src = r["path"]
        dst = ARCHIVE / r["name"]
        if dst.exists():
            suffix = 1
            while dst.exists():
                dst = ARCHIVE / f"{r['name']}-{suffix}"
                suffix += 1

        print(f"  {r['name']:<30s} -> Archive/{dst.name}")
        if not dry_run:
            shutil.move(str(src), str(dst))

    color = "\033[92m" if not dry_run else "\033[93m"
    status = "Done." if not dry_run else "Dry run complete. No files moved."
    print(f"\n{color}{status}\033[0m")


# --- Main ---

def main():
    dry_run = "--dry-run" in sys.argv
    summary_only = "--summary" in sys.argv

    print("Scanning repos...", end="", flush=True)
    repos = scan_all()
    print(f" found {len(repos)} git repos.")

    print_summary(repos)

    if summary_only:
        return

    to_archive = interactive_select(repos)

    if not to_archive:
        print("No repos selected.")
        return

    print(f"\033[1mSelected for archiving:\033[0m")
    for r in to_archive:
        print(f"  - {r['name']} ({r['group']}, score {r['score']})")

    if dry_run:
        archive_repos(to_archive, dry_run=True)
    else:
        confirm = input(f"\nMove {len(to_archive)} repos to Archive/? [y/N] ").strip().lower()
        if confirm == "y":
            archive_repos(to_archive)
        else:
            print("Cancelled.")


if __name__ == "__main__":
    main()
