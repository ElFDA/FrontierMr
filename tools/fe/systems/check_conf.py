#!/usr/bin/env python3
"""Compares the slots of systems.ini with the CONF_STR of the real cores.

For every system of a category (default Computer) it finds the core repository in
the MiSTer-devel organisation (the rbf name), reads the CONF_STR of its top .sv file
and lists the file/disk entries of the core ("F1,PRGCRT,Load;" = file, index 1;
"S0,D64G64,Mount;" = disk image, index 0). Then it says what systems.ini does not
know or has wrong:

  OK        every slot of systems.ini is a real entry of the core with that type
  MISSING   an entry of the core (type, index, extensions) not in systems.ini
  WRONG     a slot whose type/index does not exist in the core
  EXT       extensions of systems.ini the core does not list (or that it lists for
            another index)

Needs gh (authenticated) for the GitHub API.
  check_conf.py [--category Computer] [--only NAME] [--json out.json]
"""
import argparse
import base64
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INI = ROOT / 'tools/fe/sd/frontier/systems.ini'


def gh(path):
    out = subprocess.run(['gh', 'api', path], capture_output=True, text=True)
    if out.returncode:
        return None
    return json.loads(out.stdout)


def raw(repo, branch, path):
    url = 'https://raw.githubusercontent.com/MiSTer-devel/%s/%s/%s' % (repo, branch, path)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.read().decode('utf-8', 'replace')
    except Exception:
        return None


def systems(category):
    secs = re.split(r'^\[(.+)\]\s*$', INI.read_text(encoding='utf-8'), flags=re.M)
    for i in range(1, len(secs), 2):
        d = {}
        slots = []
        for line in secs[i + 1].splitlines():
            if line.startswith(';') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            if re.fullmatch(r'slot\d+', k):
                t, idx, delay, exts = (v.split(',', 3) + ['', '', '', ''])[:4]
                slots.append((t.strip().lower(), int(idx), int(delay), exts.split()))
            else:
                d[k] = v
        if d.get('category') == category:
            yield secs[i], d, slots


def norm(s):
    s = s.lower()
    s = re.sub(r'_?mister$', '', s)
    return re.sub(r'[^a-z0-9]', '', s)


def conf_entries(text):
    """File/disk entries of the CONF_STR: [(type 'f'|'s', index, [ext], flags, label)]"""
    # every quoted string of the file: a CONF_STR is often split with `ifdef and a few "};"
    body = re.sub(r'//[^\n]*', '', text)
    out = []
    for q in re.findall(r'"([^"]*)"', body):
        for part in q.split(';'):
            part = part.strip()
            # prefixes: H/h/D/d + digit = condition (hidden/disabled), P + digit = page of the OSD
            m = re.match(r'^((?:[HhDdPp][0-9A-V])*)(F|S)([CS]*)([0-9A-V]?),([^,;]*)(?:,([^;]*))?$', part)
            if not m:
                continue
            pre, kind, flags, idx, exts, label = m.groups()
            if not set(flags) <= set('CS'):
                continue
            page = 'P' in pre.upper().replace('H', '').replace('D', '') and bool(re.search(r'P[0-9A-V]', pre))
            ext = [exts[i:i + 3].strip().lower() for i in range(0, len(exts), 3)]
            # same number as Main_MiSTer: a digit, anything else is 0
            num = int(idx) if idx.isdigit() else 0
            out.append((kind.lower(), num, [e for e in ext if e], flags, (label or '').strip(), page, pre))
    return out


def ext_ok(have, want):
    if len(have) != len(want):
        return False
    return all(a == b or '?' in (a + b) for a, b in zip(have, want))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--category', default='Computer')
    ap.add_argument('--only')
    ap.add_argument('--json')
    args = ap.parse_args()

    repos = []
    page = 1
    while True:
        r = gh('orgs/MiSTer-devel/repos?per_page=100&page=%d' % page)
        if not r:
            break
        repos += [x['name'] for x in r]
        page += 1
    by_norm = {}
    for r in repos:
        by_norm.setdefault(norm(r), r)

    report = {}
    for name, d, slots in systems(args.category):
        if args.only and args.only.lower() != name.lower():
            continue
        rbf = d.get('rbf', '').split('/')[-1]
        repo = by_norm.get(norm(rbf)) or by_norm.get(norm(name))
        if not repo:
            print('%-16s no repository found for %s' % (name, rbf))
            report[name] = 'norepo'
            continue
        info = gh('repos/MiSTer-devel/%s' % repo)
        branch = (info or {}).get('default_branch', 'master')
        files = gh('repos/MiSTer-devel/%s/contents/' % repo) or []
        svs = [f['name'] for f in files if f['name'].endswith('.sv')]
        text = None
        for sv in sorted(svs, key=lambda n: (norm(n[:-3]) != norm(rbf), n)):
            t = raw(repo, branch, sv)
            if t and 'CONF_STR' in t:
                text = t
                break
        if text is None:
            print('%-16s %s: no CONF_STR found (%s)' % (name, repo, ' '.join(svs)))
            report[name] = 'noconf'
            continue
        ent = conf_entries(text)
        if not ent:
            print('%-16s %s: UNKNOWN, no file/disk entries read from the config string' % (name, repo))
            report[name] = 'unknown'
            continue
        probs = []
        for (t, idx, delay, exts) in slots:
            cand = [e for e in ent if e[0] == t and e[1] == idx]
            if not cand:
                alt = [e for e in ent if not e[5] and any(ext_ok(k, x) for k in e[2] for x in exts)]
                hint = ' -> %s' % '; '.join('%s,%d (%s)' % (e[0], e[1], ' '.join(e[2])) for e in alt) if alt else ' -> no main-page entry takes these extensions'
                probs.append('WRONG   slot %s,%d,%s: no such entry in the core%s' % (t, idx, ','.join(exts), hint))
                continue
            if all(e[5] for e in cand):
                probs.append('PAGE    slot %s,%d,%s: the entry is in a sub page of the OSD (%s), the MGL cannot reach it' % (t, idx, ','.join(exts), cand[0][6]))
                continue
            known = set(x for e in cand for x in e[2])
            bad = [x for x in exts if not any(ext_ok(k, x) for k in known)]
            if bad and known:
                probs.append('EXT     slot %s,%d: %s not in the core (%s)' % (t, idx, ' '.join(bad), ' '.join(sorted(known))))
        for e in ent:
            if not e[5] and not any(s[0] == e[0] and s[1] == e[1] for s in slots):
                probs.append('MISSING %s%s%d %s  (%s)' % (e[0].upper(), e[3], e[1], ' '.join(e[2]), e[4]))
        print('%-16s %s %s' % (name, repo, 'OK' if not probs else ''))
        for p in probs:
            print('    ' + p)
        report[name] = {'repo': repo, 'entries': ent, 'problems': probs}
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
