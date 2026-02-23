#!/usr/bin/env python3
"""
describe_test.py — Show what a release verification test does, live from YAML.

Usage:
    python3 describe_test.py BOND-001           # print to stdout
    python3 describe_test.py BOND-001 --update  # also rewrite the .md sidecar file
    python3 describe_test.py --all              # all tests
    python3 describe_test.py --all --update     # regenerate all .md files
"""

import re
import sys
import yaml
from pathlib import Path

TASKS_ROOT = Path(__file__).parent / "roles/release_verification/tasks"
VARS_FILE  = Path(__file__).parent / "roles/release_verification/vars/main.yml"
# Also load inventory-level IP vars so tests using r1_eth1_ip etc. resolve properly
_EXTRA_VAR_FILES = [
    Path(__file__).parent / "group_vars/vyos_hosts/ip.yml",
]

# ── variable loading ──────────────────────────────────────────────────────────

def load_role_vars():
    """Load simple (non-template) variables from role vars/main.yml and ip.yml."""
    result = {}
    for path in [VARS_FILE] + _EXTRA_VAR_FILES:
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            result.update({
                k: str(v)
                for k, v in data.items()
                if isinstance(v, (str, int, float)) and "{{" not in str(v)
            })
        except Exception:
            pass
    return result


def subst(text, vd):
    """Substitute {{ var }} occurrences with known values."""
    for k, v in vd.items():
        text = text.replace("{{ " + k + " }}", v)
        text = text.replace("{{" + k + "}}", v)
    return text


# ── test discovery ────────────────────────────────────────────────────────────

# Matches: BOND-001, ETH-001, FW-GROUP-001, FW-GLOBAL-001, L2TPV3-001, etc.
_TEST_TAG = re.compile(r"^[A-Z][A-Z0-9]*(-[A-Z][A-Z0-9]*)*-\d+$")


def all_tests():
    """Yield (test_id, yml_file) for every implemented test file."""
    for yml_file in sorted(TASKS_ROOT.rglob("*.yml")):
        if yml_file.parent.name.startswith("_") or yml_file.name == "main.yml":
            continue
        try:
            data = yaml.safe_load(yml_file.read_text()) or []
            if not isinstance(data, list):
                continue
            for item in data:
                if not isinstance(item, dict) or "block" not in item:
                    continue
                for task in item["block"]:
                    for tag in task.get("tags", []) or []:
                        if _TEST_TAG.match(tag):
                            yield tag, yml_file
                            break
                    else:
                        continue
                    break
        except Exception:
            pass


def find_test(test_id):
    for tid, f in all_tests():
        if tid == test_id:
            return f
    return None


# ── assertion humaniser ───────────────────────────────────────────────────────

_BOILERPLATE = re.compile(
    r"^\w+\.(stdout|stdout_lines) (is defined|\| length > 0)$"
)

def humanize(cond, vd):
    """Convert a raw Ansible assert condition to human-readable text.
    Returns None to skip boilerplate lines."""
    # PyYAML already strips YAML outer quotes; just trim whitespace
    cond = cond.strip()

    if _BOILERPLATE.match(cond):
        return None

    # Substitute known vars first (resolves e.g. rv_ipv4_prefix → 192.0.2)
    cond = subst(cond, vd)

    # 'literal' in var.stdout[0]
    m = re.match(r"'([^']+)' in \w+\.stdout\[0\]$", cond)
    if m:
        return f"'{m.group(1)}' in output"

    # 'literal' in (var.stdout | join(' '))
    m = re.match(r"'([^']+)' in \(\w+\.stdout \| join\([^)]+\)\)$", cond)
    if m:
        return f"'{m.group(1)}' in output"

    # 'literal' in (var.stdout[0] | lower)
    m = re.match(r"'([^']+)' in \(?\w+\.stdout\[0\] \| lower\)?$", cond)
    if m:
        return f"'{m.group(1)}' in output (case-insensitive)"

    # (expr ~ 'suffix') in var.stdout[0]   — with parentheses
    m = re.match(r"\(([^)]+) ~ '([^']+)'\) in \w+\.stdout\[0\]$", cond)
    if m:
        base = m.group(1).strip()
        val  = vd.get(base, base)
        return f"'{val}{m.group(2)}' in output"

    # expr ~ 'suffix' in var.stdout[0]     — without parentheses
    m = re.match(r"(\w+) ~ '([^']+)' in \w+\.stdout\[0\]$", cond)
    if m:
        val = vd.get(m.group(1), m.group(1))
        return f"'{val}{m.group(2)}' in output"

    # expr in var.stdout[0]  (bare variable name or complex expression)
    m = re.match(r"(.+) in \w+\.stdout\[0\]$", cond)
    if m:
        expr = m.group(1).strip()
        # Resolve simple role variable names (e.g. rv_vxlan_name → 'vxlan0')
        if re.match(r"^\w+$", expr) and expr in vd:
            return f"'{vd[expr]}' in output"
        return f"{expr} in output"

    # Generic: clean up stdout references
    cond = re.sub(r"\b\w+\.stdout\[0\]\b", "output", cond)
    cond = re.sub(r"\b\w+\.stdout\b", "output", cond)
    return cond


# ── when-condition label ──────────────────────────────────────────────────────

def when_label(task):
    """Return a short label for a task's when condition.

    Three kinds of labels:
      [r1] / [r2]       — task-level per-host condition (asymmetric test)
      [if peer]         — runs when a peer router is present
      [if no peer]      — fallback when running without a peer
    """
    w = task.get("when")
    if w is None:
        return ""
    if isinstance(w, list):
        w = " and ".join(str(x) for x in w)
    w = str(w)
    # Per-host guards on individual tasks (asymmetric 2-node tests)
    if "inventory_hostname == 'r1'" in w or 'inventory_hostname == "r1"' in w:
        return "r1"
    if "inventory_hostname == 'r2'" in w or 'inventory_hostname == "r2"' in w:
        return "r2"
    if "inventory_hostname == 'r3'" in w or 'inventory_hostname == "r3"' in w:
        return "r3"
    # Peer-presence guards (symmetric 2-node tests)
    if "rv_peer is not defined" in w:
        return "if no peer"
    if "rv_peer is defined" in w:
        return "if peer"
    return f"when: {w}"


def block_hosts(item):
    """Derive which hosts execute this block from its top-level when: clause."""
    w = item.get("when")
    if not w:
        return "r1, r2"   # no guard → runs on all inventory hosts
    if isinstance(w, list):
        w = " and ".join(str(x) for x in w)
    w = str(w)
    if "inventory_hostname == 'r1'" in w or 'inventory_hostname == "r1"' in w:
        return "r1"
    if "inventory_hostname == 'r2'" in w or 'inventory_hostname == "r2"' in w:
        return "r2"
    if "inventory_hostname == 'r3'" in w or 'inventory_hostname == "r3"' in w:
        return "r3"
    return "r1, r2"


# ── parse one test file ───────────────────────────────────────────────────────

class Entry:
    def __init__(self, kind, text, label=""):
        self.kind  = kind   # config | show | assert | ping | wait | note
        self.text  = text
        self.label = label  # "" | "2-node" | "1-node" | ...


def parse(yml_file, test_id, vd):
    raw  = yml_file.read_text()
    data = yaml.safe_load(raw) or []

    # Extract header comment from YAML source
    header = ""
    topology = ""
    for line in raw.splitlines()[1:]:
        if not line.startswith("#"):
            break
        stripped = line.lstrip("#").strip()
        if stripped.startswith(test_id + ":"):
            header = stripped[len(test_id) + 1:].strip()
        elif stripped.startswith("Topology:"):
            topology = stripped[len("Topology:"):].strip()

    entries = []
    cleanup = []
    hosts   = "r1, r2"  # default

    for item in data:
        if not isinstance(item, dict) or "block" not in item:
            continue

        hosts = block_hosts(item)

        # ── block (main test tasks) ──
        for task in item.get("block", []):
            if not isinstance(task, dict):
                continue
            tags = task.get("tags", []) or []
            if test_id not in tags or "cleanup" in tags:
                continue
            wl = when_label(task)
            _collect(task, entries, wl, vd, test_id)

        # ── always (cleanup) — deduplicate across conditional branches ──
        seen_cleanup = set()
        for task in item.get("always", []):
            if not isinstance(task, dict):
                continue
            tags = task.get("tags", []) or []
            if test_id not in tags:
                continue
            for key in ("vyos.vyos.vyos_config", "vyos_config"):
                if key in task:
                    for line in task[key].get("lines", []):
                        cmd = subst(line, vd)
                        if cmd not in seen_cleanup:
                            seen_cleanup.add(cmd)
                            cleanup.append(cmd)

        break  # only one top-level block expected

    return header, topology, hosts, entries, cleanup


def _collect(task, entries, wl, vd, test_id):
    """Dispatch a single task into entries list."""

    # ── import_tasks helpers ──
    if "import_tasks" in task:
        helper = task["import_tasks"]
        hvars  = task.get("vars", {}) or {}
        if "show_assert" in helper:
            cmd = subst(hvars.get("_show_command", ""), vd)
            astr = subst(hvars.get("_assert_string", ""), vd)
            entries.append(Entry("show",   cmd, wl))
            entries.append(Entry("assert", f"'{astr}' in output", wl))
        elif "ping_peer" in helper:
            target = subst(hvars.get("_ping_target", "?"), vd)
            entries.append(Entry("ping", target, wl))
        elif "wait_route" in helper:
            prefix = subst(hvars.get("_route_prefix", "?"), vd)
            entries.append(Entry("wait", prefix, wl))
        return

    # ── local shell (delegate_to: localhost) ──
    for key in ("ansible.builtin.shell", "shell"):
        if key in task:
            if task.get("delegate_to") == "localhost":
                entries.append(Entry("note", "(controller) generate cert/key via openssl", wl))
            return

    # ── set_fact: skip ──
    for key in ("ansible.builtin.set_fact", "set_fact"):
        if key in task:
            return

    # ── debug: note ──
    for key in ("ansible.builtin.debug", "debug"):
        if key in task:
            msg = task[key].get("msg", "") if isinstance(task.get(key), dict) else ""
            if msg:
                entries.append(Entry("note", str(msg)[:120], wl))
            return

    # ── vyos_config ──
    for key in ("vyos.vyos.vyos_config", "vyos_config"):
        if key in task:
            for line in task[key].get("lines", []):
                entries.append(Entry("config", subst(line, vd), wl))
            return

    # ── vyos_command ──
    for key in ("vyos.vyos.vyos_command", "vyos_command"):
        if key in task:
            for cmd in task[key].get("commands", []):
                if isinstance(cmd, dict):
                    cmd = cmd.get("command", str(cmd))
                entries.append(Entry("show", subst(cmd, vd), wl))
            return

    # ── assert ──
    for key in ("ansible.builtin.assert", "assert"):
        if key in task:
            for cond in task[key].get("that", []):
                h = humanize(str(cond), vd)
                if h:
                    entries.append(Entry("assert", h, wl))
            return


# ── format output ─────────────────────────────────────────────────────────────

def _prefix(label):
    return f"[{label}] " if label else ""


def _lines_for(entries, *kinds):
    return [(e.label, e.text) for e in entries if e.kind in kinds]


def _ordering_matters(entries):
    """True when show/assert/ping/wait entries are interleaved with config entries.

    This happens in multi-phase tests where a verification step sits between
    two configuration phases (e.g. FW-IPV4-001: drop rule → verify blocked →
    accept rule → verify accepted).
    """
    kinds = [
        'check' if e.kind in ('assert', 'ping', 'wait') else e.kind
        for e in entries
        if e.kind in ('config', 'show', 'assert', 'ping', 'wait')
    ]
    last_config = max((i for i, k in enumerate(kinds) if k == 'config'), default=-1)
    return any(k in ('show', 'check') and i < last_config for i, k in enumerate(kinds))


def _grouped(entries):
    """Yield [group_kind, [entries]] grouping consecutive same-kind entries.
    Normalises assert/ping/wait → 'check' for grouping."""
    groups = []
    for e in entries:
        gk = 'check' if e.kind in ('assert', 'ping', 'wait') else e.kind
        if groups and groups[-1][0] == gk:
            groups[-1][1].append(e)
        else:
            groups.append([gk, [e]])
    return groups


def _emit_sequential(out, entries):
    """Emit entries in document order with ### sub-section headers on kind change."""
    for gk, elist in _grouped(entries):
        if gk == 'note':
            for e in elist:
                out.append(f"- {_prefix(e.label)}{e.text}")
            out.append("")
        elif gk == 'config':
            out.append("### Configure")
            out.append("")
            out.append("```")
            for e in elist:
                out.append(f"{_prefix(e.label)}{e.text}")
            out.append("```")
            out.append("")
        elif gk == 'show':
            out.append("### Verify")
            out.append("")
            out.append("```")
            for e in elist:
                out.append(f"{_prefix(e.label)}{e.text}")
            out.append("```")
            out.append("")
        elif gk == 'check':
            out.append("### Assert")
            out.append("")
            for e in elist:
                if e.kind == 'assert':
                    out.append(f"- {_prefix(e.label)}{e.text}")
                elif e.kind == 'ping':
                    out.append(f"- {_prefix(e.label)}ping {e.text} → 0% packet loss")
                elif e.kind == 'wait':
                    out.append(f"- {_prefix(e.label)}route {e.text} visible in routing table")
            out.append("")


def format_md(test_id, header, topology, hosts, entries, cleanup):
    out = []
    out.append(f"# {test_id}: {header}")
    out.append("")
    if topology:
        out.append(f"Topology: {topology}")
    labels_used = {e.label for e in entries if e.label}
    host_labels = labels_used & {"r1", "r2", "r3"}

    if hosts in ("r1", "r2", "r3"):
        out.append(f"Runs on: {hosts}")
    elif host_labels == {"r1", "r2", "r3"}:
        out.append("Runs on: r1, r2, r3 — 3-node asymmetric (each router runs different commands; see [r1]/[r2]/[r3] labels)")
    elif host_labels == {"r1", "r2"}:
        out.append("Runs on: r1, r2 — asymmetric (r1 and r2 run different commands; see [r1]/[r2] labels)")
    elif host_labels == {"r1"}:
        out.append("Runs on: r1, r2 — mostly shared; r1 has additional steps (see [r1] labels)")
    elif host_labels == {"r2"}:
        out.append("Runs on: r1, r2 — mostly shared; r2 has additional steps (see [r2] labels)")
    else:
        out.append("Runs on: r1, r2 — each router executes independently with its own variable values")

    # Legend: only include label types that actually appear
    legend = []
    if "r1" in labels_used:
        legend.append("[r1] = r1 only")
    if "r2" in labels_used:
        legend.append("[r2] = r2 only")
    if "r3" in labels_used:
        legend.append("[r3] = r3 only")
    if "if peer" in labels_used:
        legend.append("[if peer] = only when a peer router is present")
    if "if no peer" in labels_used:
        legend.append("[if no peer] = fallback when running without a peer")
    if legend:
        out.append("Labels:   " + ";  ".join(legend))
    out.append("")

    # Multi-phase tests (verify interleaved between configure phases): sequential.
    # Single-phase tests (configure → verify → assert): standard sections.
    if _ordering_matters(entries):
        out.append("## Steps")
        out.append("")
        _emit_sequential(out, entries)
    else:
        notes   = _lines_for(entries, "note")
        configs = _lines_for(entries, "config")
        shows   = _lines_for(entries, "show")
        asserts = _lines_for(entries, "assert")
        pings   = _lines_for(entries, "ping")
        routes  = _lines_for(entries, "wait")

        if notes:
            out.append("## Notes")
            out.append("")
            for lbl, txt in notes:
                out.append(f"- {_prefix(lbl)}{txt}")
            out.append("")

        if configs:
            out.append("## Configure commands")
            out.append("")
            out.append("```")
            for lbl, cmd in configs:
                out.append(f"{_prefix(lbl)}{cmd}")
            out.append("```")
            out.append("")

        if shows:
            out.append("## Verification commands")
            out.append("")
            out.append("```")
            for lbl, cmd in shows:
                out.append(f"{_prefix(lbl)}{cmd}")
            out.append("```")
            out.append("")

        if asserts or pings or routes:
            out.append("## Assertions")
            out.append("")
            for lbl, a in asserts:
                out.append(f"- {_prefix(lbl)}{a}")
            for lbl, target in pings:
                out.append(f"- {_prefix(lbl)}ping {target} → 0% packet loss")
            for lbl, prefix in routes:
                out.append(f"- {_prefix(lbl)}route {prefix} visible in routing table")
            out.append("")

    if cleanup:
        out.append("## Cleanup")
        out.append("")
        out.append("```")
        for cmd in cleanup:
            out.append(cmd)
        out.append("```")
        out.append("")

    return "\n".join(out)


# ── entry point ───────────────────────────────────────────────────────────────

def describe_one(test_id, vd, update_md=False):
    yml_file = find_test(test_id)
    if not yml_file:
        print(f"ERROR: test '{test_id}' not found", file=sys.stderr)
        return False

    header, topology, hosts, entries, cleanup = parse(yml_file, test_id, vd)
    text = format_md(test_id, header, topology, hosts, entries, cleanup)
    print(text)

    if update_md:
        md = yml_file.with_suffix(".md")
        md.write_text(text)
        print(f"  → {md.relative_to(Path.cwd())}", file=sys.stderr)

    return True


def main():
    args   = sys.argv[1:]
    update = "--update" in args
    args   = [a for a in args if not a.startswith("--")]

    if not args:
        print(__doc__)
        sys.exit(1)

    vd = load_role_vars()

    if args[0].lower() == "all":
        for test_id, _ in all_tests():
            describe_one(test_id, vd, update_md=update)
    else:
        ok = describe_one(args[0].upper(), vd, update_md=update)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
