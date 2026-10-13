#!/usr/bin/env python
"""lint_runbook.py -- every script and flag a runbook names must exist.

    python rig/lint_runbook.py RIG_DAY_2026-10-14.md HELPER_CARD_2026-10-14.md [...]

For each command line in the documents (inside ``` blocks, table cells or
backticks) that names rig\\X.py, rig\\X.ps1, training\\X.py, cpp_controller.exe
or MpcPo8eUdpClosedLoop.exe, checks that the file exists and that every
--flag / -Flag on that line is declared (argparse add_argument, PowerShell
param block, or the C++ flag parser). Prints one line per mismatch; exit 1 if any.
Placeholders like <blk>, <V>, ______ are ignored.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

SCRIPT_RE = re.compile(r"((?:rig|training|scripts)[\\/][\w.]+\.(?:py|ps1)|cpp_controller\.exe|MpcPo8eUdpClosedLoop\.exe)")
PYFLAG_RE = re.compile(r"(?<![\w-])(--[a-z][\w-]*)")
PSFLAG_RE = re.compile(r"(?<![\w-])(-[A-Z][A-Za-z]+)\b")


def py_flags(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    return set(re.findall(r"add_argument\(\s*\"(--[\w-]+)\"", txt)) | set(re.findall(r"add_argument\(\s*'(--[\w-]+)'", txt))


def ps_params(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    m = re.search(r"param\s*\((.*?)\n\)", txt, re.S)
    body = m.group(1) if m else ""
    return {"-" + p for p in re.findall(r"\$(\w+)", body)}


def cpp_flags(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    return set(re.findall(r"\"(--[\w-]+)\"", txt))


_cache = {}


def declared(script):
    if script in _cache:
        return _cache[script]
    if script.endswith("cpp_controller.exe"):
        flags = cpp_flags(os.path.join(REPO, "cpp_controller", "main.cpp"))
    elif script.endswith("MpcPo8eUdpClosedLoop.exe"):
        flags = cpp_flags(os.path.join(REPO, "MpcPo8eUdpClosedLoop.cpp"))
    else:
        p = os.path.join(REPO, script.replace("\\", os.sep).replace("/", os.sep))
        if not os.path.isfile(p):
            _cache[script] = None
            return None
        flags = ps_params(p) if p.endswith(".ps1") else py_flags(p)
    _cache[script] = flags
    return flags


def lint_file(path):
    problems = []
    for ln, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
        for cell in re.split(r"\s\|\s|`", line):
            m = SCRIPT_RE.search(cell)
            if not m:
                continue
            script = m.group(1)
            flags = declared(script)
            if flags is None:
                problems.append("%s:%d: missing script %s" % (os.path.basename(path), ln, script))
                continue
            rest = cell[m.end():]
            rest = re.sub(r"<[^>]*>", " ", rest)
            rest = rest.split("   #")[0]
            if "--launch-args" in rest:
                # everything after --launch-args is passed to cpp_controller
                head, _, launch = rest.partition("--launch-args")
                rest = head + " --launch-args "
                cpp = declared("cpp_controller.exe")
                for f in PYFLAG_RE.findall(launch):
                    if f not in cpp:
                        problems.append("%s:%d: cpp_controller.exe (via --launch-args) has no flag %s"
                                        % (os.path.basename(path), ln, f))
            used = PYFLAG_RE.findall(rest) if not script.endswith(".ps1") else []
            if script.endswith(".ps1"):
                used = PSFLAG_RE.findall(rest)
            for f in used:
                if f == "--" or f in ("-Scope", "-ExecutionPolicy"):
                    continue
                if f not in flags:
                    problems.append("%s:%d: %s has no flag %s" % (os.path.basename(path), ln, script, f))
    return problems


def main():
    files = sys.argv[1:]
    if not files:
        print(__doc__)
        return 2
    total = []
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(REPO, f)
        probs = lint_file(p)
        total += probs
        print("%s: %d mismatch(es)" % (os.path.basename(f), len(probs)))
        for pr in probs:
            print("  " + pr)
    print("LINT %s: %d mismatch(es)" % ("PASS" if not total else "FAIL", len(total)))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
