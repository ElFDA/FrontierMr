#!/usr/bin/env python3
"""Launches one file per slot of the systems of systems.ini on the MiSTer and takes a screenshot.

For every system of a category (default Computer) which has a core on the SD card and files in
games/ it makes the MGL the way Frontier does (rbf, setname, <file delay type index path>), loads it
with "load_core" and asks MiSTer for a screenshot. A run of the same core without any file is the
baseline: if the screenshot of the file is not different, the file was probably not loaded. The
verdict is only a hint: look at report.html.

  launch_test.py --dry-run                 only the list of the launches
  launch_test.py [--only Name ...] [--wait 13] [--out DIR]
  launch_test.py --report-only             rebuild report.html from the pictures of --out

Needs the MiSTer of tools/fe/env.sh. It writes only in /tmp/t on the MiSTer and the pictures
t_*.png in /media/fat/screenshots (removed at once), and ends with the menu core.
"""
import argparse
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INI = ROOT / 'tools/fe/sd/frontier/systems.ini'
SKIP = {'Amiga', 'Amiga500', 'Amiga500HD', 'Amiga600HD', 'AmigaCD32', 'X68000'}   # their own launchers


def env():
    out = subprocess.run(['bash', '-c', '. %s/tools/fe/env.sh && echo "$MISTER_IP $MISTER_PW"' % ROOT],
                         capture_output=True, text=True, check=True).stdout.split()
    return out[0], out[1]


IP, PW = env()
SSH = ['sshpass', '-p', PW, 'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
       '-o', 'LogLevel=ERROR', '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=5', 'root@' + IP]
SCP = ['sshpass', '-p', PW, 'scp', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
       '-o', 'LogLevel=ERROR']


def ssh(cmd, timeout=120):
    return subprocess.run(SSH + [cmd], capture_output=True, text=True, timeout=timeout).stdout


def systems(category):
    secs = re.split(r'^\[(.+)\]\s*$', INI.read_text(encoding='utf-8'), flags=re.M)
    for i in range(1, len(secs), 2):
        d = {'id': secs[i]}
        slots = []
        for line in secs[i + 1].splitlines():
            if line.startswith(';') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            if re.fullmatch(r'slot\d+', k):
                t, idx, delay, exts = (v.split(',', 3) + ['', '', '', ''])[:4]
                slots.append({'type': t.strip().lower(), 'index': int(idx), 'delay': int(delay), 'exts': exts.lower().split()})
            else:
                d[k] = v
        d['slots'] = slots
        if d.get('category') == category:
            yield d


def ext_match(pat, ext):
    return len(pat) == len(ext) and all(p == '?' or p == e for p, e in zip(pat, ext))


def mgl(sysd, slot, path, reset=0):
    if slot and slot['type'] == 's' and not reset:
        reset = int(sysd.get('reset', 0) or 0)   # systems.ini reset=N, as Frontier does
    out = ['<mistergamedescription>', '\t<rbf>%s</rbf>' % sysd['rbf']]
    if sysd.get('setname'):
        out.append('\t<setname%s>%s</setname>' % (' same_dir="1"' if sysd.get('setname_same_dir') == '1' else '', sysd['setname']))
    if slot:
        out.append('\t<file delay="%d" type="%s" index="%d" path="%s"/>' % (slot['delay'], slot['type'], slot['index'],
                   path.replace('&', '&amp;').replace('"', '&quot;')))
    if slot and slot['type'] == 's' and sysd.get('autorun') and slot['index'] == sysd['slots'][0]['index']:
        for x in sysd['slots']:
            if x['type'] == 'f' and 'prg' in x['exts']:
                out.append('\t<file delay="0" type="f" index="%d" path="/media/fat/%s"/>' % (x['index'], sysd['autorun']))
                break
    if slot and reset:
        out.append('\t<reset delay="%d"/>' % reset)
    out.append('</mistergamedescription>')
    return '\n'.join(out) + '\n'


def plan(args):
    """[(system, slot or None, file or None)]"""
    listing = ssh("cd /media/fat; ls _Computer | tr 'A-Z' 'a-z'; echo ===; cd /media/fat/games/ && find . -maxdepth 4 -type f | sed 's|^[.]/|games/|'", 180).split('\n===\n')
    rbfs = set(listing[0].split())
    files = listing[1].split('\n') if len(listing) > 1 else []
    bydir = {}
    for f in files:
        parts = f.split('/')
        if len(parts) < 3 or any(p.startswith('.') for p in parts):
            continue
        bydir.setdefault(parts[1].lower(), []).append(f)
    cases = []
    for s in systems(args.category):
        if s['id'] in SKIP or (args.only and s['id'] not in args.only):
            continue
        name = s['rbf'].split('/')[-1].lower()
        if not any(r == name + '.rbf' or r.startswith(name + '_') and r.endswith('.rbf') for r in rbfs):
            continue
        mine = []
        for fo in s.get('folders', '').split('|'):
            mine += bydir.get(fo.lower(), [])
        if not mine:
            continue
        # not the files of the system itself (boot.rom, boot.vhd, BIOS...)
        mine = [f for f in mine if not re.match(r'(boot|bios|nvram|config)', f.rsplit('/', 1)[-1].lower())]
        mine.sort(key=lambda f: ('[' in f or '(demo' in f.lower(), f.count('/'), f.lower()))
        base = (s, None, None)
        done = set()
        n0 = len(cases)
        for slot in s['slots']:
            key = (slot['type'], slot['index'])
            if slot['type'] not in args.slot_types:
                continue
            if key in done:
                continue
            for f in mine:
                ext = f.rsplit('.', 1)[-1].lower() if '.' in f.rsplit('/', 1)[-1] else ''
                if any(ext_match(e, ext) for e in slot['exts']):
                    cases.append((s, slot, f))
                    done.add(key)
                    break
        if len(cases) > n0:
            cases.insert(n0, base)   # the core alone, only when something is launched
    return cases


def case_id(s, slot):
    return s['id'] + ('' if not slot else '_%s%d' % (slot['type'], slot['index']))


def diff(a, b):
    from PIL import Image, ImageChops, ImageStat
    x, y = Image.open(a).convert('L'), Image.open(b).convert('L')
    if x.size != y.size:
        y = y.resize(x.size)
    st = ImageStat.Stat(ImageChops.difference(x, y))
    return st.mean[0]


def run(args, cases):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ssh('mkdir -p /tmp/t')
    # MiSTer remembers the last file of every entry in config/<core>.<f|s><n> and loads it again at the
    # next start of the core: the test puts the folder back as it was
    before = ssh("cd /media/fat/config && ls -1 *.[fs][0-9] 2>/dev/null").split()
    ssh("cd /media/fat/config && tar cf /tmp/t/cfg_before.tar *.[fs][0-9] 2>/dev/null")
    results = json.loads((out / 'results.json').read_text()) if (out / 'results.json').exists() else {}
    for n, (s, slot, f) in enumerate(cases, 1):
        cid = case_id(s, slot)
        png = out / (cid + '.png')
        if not png.exists():
            path = '/media/fat/' + f if f else ''
            text = mgl(s, slot, path, args.reset)
            shot = 't_%s.png' % re.sub(r'\W', '_', cid)
            cmd = ("cat > /tmp/t/case.mgl <<'EOF'\n%sEOF\n"
                   "echo load_core /tmp/t/case.mgl > /dev/MiSTer_cmd; sleep %d; "
                   "echo 'screenshot %s' > /dev/MiSTer_cmd; sleep 3; cat /tmp/CORENAME" % (text, args.wait, shot))
            core = ssh(cmd, args.wait + 60).strip()
            r = subprocess.run(SCP + ['root@%s:/media/fat/screenshots/%s' % (IP, shot), str(png)], capture_output=True, text=True)
            ssh("rm -f '/media/fat/screenshots/%s'" % shot)
            results[cid] = {'system': s['id'], 'name': s.get('name', s['id']), 'slot': slot and '%s,%d' % (slot['type'], slot['index']),
                            'file': f, 'core': core, 'shot': png.exists()}
            (out / 'results.json').write_text(json.dumps(results, indent=1))
        print('[%d/%d] %s %s %s' % (n, len(cases), cid, f or '(no file)', 'ok' if png.exists() else 'NO PICTURE'), flush=True)
    ssh('echo load_core /media/fat/menu.rbf > /dev/MiSTer_cmd')
    after = ssh("cd /media/fat/config && ls -1 *.[fs][0-9] 2>/dev/null").split()
    for f in after:
        if f not in before:
            ssh("rm -f '/media/fat/config/%s'" % f)
    ssh("cd /media/fat/config && [ -s /tmp/t/cfg_before.tar ] && tar xf /tmp/t/cfg_before.tar")
    print('config/*.[fs]N put back (%d files before, %d removed)' % (len(before), len([f for f in after if f not in before])))
    return results


def report(out, results):
    from PIL import Image
    rows = []
    for cid, r in sorted(results.items(), key=lambda kv: (kv[1]['system'].lower(), kv[1]['slot'] or '')):
        if not r['slot']:
            continue
        base = out / (r['system'] + '.png')
        test = out / (cid + '.png')
        if not (base.exists() and test.exists()):
            verdict, d = 'NO PICTURE', -1
        else:
            d = diff(base, test)
            verdict = 'different' if d > 0.3 else 'SAME as the core alone'
        rows.append((r, base, test, verdict, d))
    h = ['<meta charset="utf-8"><title>Launch test</title><style>body{font:14px sans-serif;background:#222;color:#eee}'
         'td{padding:4px;vertical-align:top}img{width:320px;image-rendering:pixelated}.s{color:#f88}.d{color:#8f8}</style><table>']
    for r, base, test, verdict, d in rows:
        h.append('<tr><td><b>%s</b><br>slot %s<br>%s<br><span class="%s">%s (%.2f)</span><br>core: %s</td>'
                 '<td>core alone<br><img src="%s"></td><td>with the file<br><img src="%s"></td></tr>' % (
                     html.escape(r['name']), r['slot'], html.escape(r['file'] or ''), 'd' if verdict == 'different' else 's',
                     verdict, d, html.escape(r['core']), html.escape(base.name), html.escape(test.name)))
    h.append('</table>')
    (out / 'report.html').write_text('\n'.join(h), encoding='utf-8')
    same = [r['name'] for r, b, t, v, d in rows if v != 'different']
    print('%d launches, %d different from the core alone, %d same/no picture' % (len(rows), len(rows) - len(same), len(same)))
    if same:
        print('same as the core alone: ' + ', '.join(same))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--category', default='Computer')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--wait', type=int, default=13)
    ap.add_argument('--reset', type=int, default=0, help='seconds: add <reset delay=N/> after the file')
    ap.add_argument('--slot-types', default='fs', help='f, s or fs: the types of slot to launch')
    ap.add_argument('--out', default=str(ROOT / 'dist/launch_test'))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--report-only', action='store_true')
    args = ap.parse_args()
    out = Path(args.out)
    if args.report_only:
        report(out, json.loads((out / 'results.json').read_text()))
        return
    cases = plan(args)
    if args.dry_run:
        for s, slot, f in cases:
            print('%-16s %-8s %s' % (s['id'], slot and '%s,%d' % (slot['type'], slot['index']) or 'alone', f or ''))
        print(len(cases), 'launches')
        return
    results = run(args, cases)
    report(out, results)


if __name__ == '__main__':
    main()
