#!/usr/bin/env python3
"""Test of theme_editor.py (the theme editor for the PC), without a screen (Qt offscreen).

Replays THEME_GUIDE.txt and GUIDA_TEMA_ita.txt (delete, add, 4:3 and detail variants, with the
blocks of keys of the guides) and checks that the result is themes/citypop; then reads and writes
every theme of tools/fe/sd/frontier/themes, draws all their variants, and tries Load .ini,
screensaver, Save, Save as ZIP, New theme, Add pictures, rotation and Undo.

Usage: python3 tools/fe/theme_editor_test.py      (needs PySide6: pip install PySide6)
"""
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
FE = os.path.dirname(os.path.abspath(__file__))
SD = os.path.join(FE, 'sd', 'frontier')
THEMES = os.path.join(SD, 'themes')
TMP = tempfile.mkdtemp(prefix='theme_editor_test_')
os.environ['FRONTIER_THEME_EDITOR_HOME'] = os.path.join(TMP, 'config')
sys.path.insert(0, FE)

import theme_editor as te   # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

failed = 0


def check(ok, what):
    global failed
    print(('ok    ' if ok else 'FAIL  ') + what)
    if not ok:
        failed += 1


def blocks(txt):
    """'  [name]' (+ '  delete') and '    key=value' ('   (empty)' = key to empty) blocks of a step."""
    out = []
    for l in txt.split('\n'):
        m = re.match(r'^  \[([^\]]+)\](\s+delete)?\s*$', l)
        if m:
            out.append({'name': m.group(1), 'del': bool(m.group(2)), 'props': {}})
            continue
        m = re.match(r'^    ([a-z_]+)=(.*)$', l)
        if m and out:
            out[-1]['props'][m.group(1)] = None if m.group(2) == '   (empty)' else m.group(2)
    return out


def canon(txt):
    """Sections and keys of an ini file, fonts of simple as in the guides."""
    t = []
    for l in txt.split('\n'):
        l = l.strip()
        if not l or l[0] == ';':
            continue
        if l[0] == '[':
            t.append([l, []])
            continue
        t[-1][1].append(l.replace('../simple/fonts/', 'fonts/'))
    return json.dumps([[n, sorted(k)] for n, k in t])


def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


app = QApplication(sys.argv)
ed = te.Editor()
log = []
ed.confirm = lambda m: True
ed.alert = lambda m: log.append(m)
ed.resize(1400, 900)
ed.show()
app.processEvents()


def set_all(obj, props):
    obj.clear()
    obj.update({k: v for k, v in props.items() if v is not None})


def apply_diff(t, bl, errs):
    for b in bl:
        if b['name'] == 'theme':
            for k, v in b['props'].items():
                if v is None:
                    t['global'].pop(k, None)
                else:
                    t['global'][k] = v
            continue
        i = next((j for j, e in enumerate(t['elements']) if e['name'] == b['name']), -1)
        if i < 0:
            errs.append('missing ' + b['name'])
            continue
        if b['del']:
            t['elements'].pop(i)
            continue
        for k, v in b['props'].items():
            if v is None:
                t['elements'][i]['props'].pop(k, None)
            else:
                t['elements'][i]['props'][k] = v


def add(after, b):
    ed.select(after)
    ed.add_element(b['props']['type'])
    el = ed.selected()
    el['name'] = b['name']
    set_all(el['props'], b['props'])
    return ed.S['sel']


# ---- the guides, done as a user would with the functions of the buttons
for guide in ('THEME_GUIDE.txt', 'GUIDA_TEMA_ita.txt'):
    g = read(os.path.join(SD, guide)).replace('\nPASSO ', '\nSTEP ')
    step = lambda n: next((x for x in g.split('\nSTEP ') if x.startswith('%d ' % n)), '')
    B = {n: blocks(step(n)) for n in (3, 4, 5, 6)}
    errs = []
    ed.new_theme(False)                                            # STEP 2-3
    while ed.theme()['elements']:
        ed.select(len(ed.theme()['elements']) - 1)
        ed.remove()
    set_all(ed.theme()['global'], B[3][0]['props'])
    last = -1
    for b in B[3][1:]:
        last = add(last, b)
    ed.S['cur'] = 'theme.ini'                                      # STEP 4: Make 4:3
    ed.make_43()
    apply_diff(ed.theme(), B[4], errs)
    ed.S['cur'] = 'theme.ini'                                      # STEP 5: Make detail
    ed.make_screen('detail')
    for n in ('position', 'list', 'text_system', 'text_desc', 'letter_shadow', 'letter_back', 'letter', 'name'):
        i = next((j for j, e in enumerate(ed.theme()['elements']) if e['name'] == n), -1)
        if i < 0:
            errs.append('no %s to delete' % n)
        else:
            ed.select(i)
            ed.remove()
    blk = lambda n: next((b for b in B[5] if b['name'] == n), None)
    set_all(ed.theme()['global'], B[5][0]['props'])
    for el in ed.theme()['elements']:
        if blk(el['name']):
            set_all(el['props'], blk(el['name'])['props'])
        else:
            errs.append('no block for ' + el['name'])
    for n, a in (('video', 'image'), ('players', 'genre'), ('description', 'stars'), ('text_desc', 'description'),
                 ('versions_title', 'text_desc'), ('versions_pos', 'versions_title'), ('versions', 'versions_pos')):
        add(next(j for j, e in enumerate(ed.theme()['elements']) if e['name'] == a), blk(n))
    ed.S['cur'] = 'detail.ini'                                     # STEP 6: Make 4:3
    ed.make_43()
    apply_diff(ed.theme(), B[6], errs)
    check(not errs, '%s: steps done%s' % (guide, ' (' + '; '.join(errs) + ')' if errs else ''))
    for v in ('theme.ini', 'theme_43.ini', 'detail.ini', 'detail_43.ini'):
        out = te.serialize_ini(ed.S['variants'][v], '') if v in ed.S['variants'] else ''
        check(canon(out) == canon(read(os.path.join(THEMES, 'citypop', v))), '%s: %s = themes/citypop/%s' % (guide, v, v))

# ---- Make 4:3 (bar and Variant menu), Make detail, Make screensaver: only what is missing, from the current file
ed.new_theme(False)
ed.S['cur'] = 'theme.ini'
ed.refresh_all()
labels = [i.get('label') for i in ed.variant_menu() if isinstance(i, dict)]
check({'Make 4:3', 'Make detail', 'Make screensaver'} <= set(labels), 'Variant menu: Make 4:3, Make detail, Make screensaver')
check(ed.btn_make43.isEnabled() and ed.can_make('detail') and not ed.can_make('screensaver'), 'new theme: Make 4:3 and Make detail, no screensaver yet')
ed.make_43()
check(ed.S['cur'] == 'theme_43.ini' and not ed.btn_make43.isEnabled() and not ed.can_make('43'), 'Make 4:3: theme_43.ini made and opened, nothing more to make')
ed.S['cur'] = 'theme.ini'
ed.refresh_all()
check(not ed.btn_make43.isEnabled(), 'Make 4:3 off when the 4:3 file exists')
ed.make_screen('detail')
check(ed.S['cur'] == 'detail.ini' and ed.can_make('screensaver') and ed.can_make('43'), 'Make detail: detail.ini, then screensaver and 4:3 can be made')
ed.make_screen('screensaver')
check(ed.S['cur'] == 'screensaver.ini' and 'screensaver.ini' in ed.S['variants'], 'Make screensaver: screensaver.ini from detail.ini')
ed.S['dirty'] = False

# ---- Load .ini: by name into its variant, another name into the current one
ed.new_theme(False)
ed.S['dirty'] = False
ed.import_ini([os.path.join(THEMES, 'citypop', 'theme.ini'), os.path.join(THEMES, 'citypop', 'detail.ini')])
V = ed.S['variants']
check(V['theme.ini']['global'].get('name') == 'City Pop' and len(V['detail.ini']['elements']) == 18 and ed.S['cur'] == 'theme.ini',
      'Load .ini: theme.ini and detail.ini into their variants')
ed.S['cur'] = 'detail.ini'
tmp_ini = os.path.join(TMP, 'blue.ini')
shutil.copy(os.path.join(THEMES, 'citypop_blue', 'theme_43.ini'), tmp_ini)
ed.import_ini([tmp_ini])
check(ed.S['variants']['detail.ini']['global'].get('name') == 'City Pop Blue' and ed.S['cur'] == 'detail.ini', 'Load .ini: another name into the current variant')
ed.undo()
check(ed.S['variants']['detail.ini']['global'].get('name') == 'City Pop', 'Load .ini: Undo')
ed.redo()
check(ed.S['variants']['detail.ini']['global'].get('name') == 'City Pop Blue', 'Load .ini: Redo')
ed.undo()

# ---- screensaver: detail.ini without the versions
ed.S['cur'] = 'detail.ini'
ed.go_screen('screensaver', False, False)
V = ed.S['variants']
check(ed.S['cur'] == 'screensaver.ini' and len(V['screensaver.ini']['elements']) == len(V['detail.ini']['elements']) - 3
      and not any(e['name'].startswith('versions') for e in V['screensaver.ini']['elements']), 'Screensaver: detail.ini without the versions')

# ---- every theme: read and write the same keys, draw every variant
bad, drawn = [], 0
for th in sorted(os.listdir(THEMES)):
    for v in te.VARIANTS:
        p = os.path.join(THEMES, th, v)
        if not os.path.isfile(p):
            continue
        a = te.parse_ini(read(p))
        b = te.parse_ini(te.serialize_ini(a, te.ini_header(read(p))))
        keep = lambda t: json.dumps([sorted((k, x) for k, x in t['global'].items() if x != ''),
                                     [[e['name'], sorted((k, x) for k, x in e['props'].items() if x != '' or k == 'text')] for e in t['elements']]])
        if keep(a) != keep(b):
            bad.append(th + '/' + v)
check(not bad, 'all the .ini files of the themes are written back with the same sections and keys' + (': ' + ', '.join(bad) if bad else ''))

blank = []
for th in sorted(os.listdir(THEMES)):
    if not ed.load_folder(os.path.join(THEMES, th)):
        blank.append(th + ' (not opened)')
        continue
    for v in list(ed.S['variants']):
        ed.go_screen(*(v[:-4].replace('_43', ''), v.endswith('_43.ini')), False)
        for text in (False, True):
            for crt, crti in ((False, False), (True, False), (False, True)):
                ed.S['opt'].update(text=text, crt=crt, crti=crti)
                ed.render()
                img = ed.canvas.grab().toImage()
                drawn += 1
                if img.isNull() or img.pixelColor(img.width() // 2, img.height() // 2) == QColor(0, 0, 0, 0):
                    blank.append('%s/%s' % (th, v))
ed.S['opt'].update(text=False, crt=False, crti=False)
check(not blank and drawn > 300, 'all the variants of all the themes drawn (%d previews, also text layout, 240p, 240i)' % drawn)

# fonts of ../simple/fonts are found (City Pop uses Bebas Neue from the simple theme)
ed.load_folder(os.path.join(THEMES, 'citypop'))
el = next(e for e in ed.theme()['elements'] if e['props'].get('font', '').startswith('../simple/fonts/'))
info = ed.media.font(ed.files.abs(el['props']['font']))
check(bool(info), 'fonts of ../simple/fonts/ are loaded for the preview (%s)' % (info[0] if info else el['props']['font']))

# ---- a copy of a theme: Save, Save as ZIP, Add pictures, rotation
work = os.path.join(TMP, 'citypop')
shutil.copytree(os.path.join(THEMES, 'citypop'), work)
ed.load_folder(work)
ed.select(0)
ed.snapshot()
ed.selected()['props']['rect'] = '1,2,3,4'
check(ed.S['dirty'], 'a change marks the theme as modified')
ed.save_folder()
again = te.parse_ini(read(os.path.join(work, 'theme.ini')))
check(again['elements'][0]['props']['rect'] == '1,2,3,4' and not ed.S['dirty'], 'Save writes theme.ini in the folder')
check('\r' not in read(os.path.join(work, 'theme.ini')), 'Save writes Unix line ends')
check(canon(read(os.path.join(work, 'detail.ini'))) == canon(read(os.path.join(THEMES, 'citypop', 'detail.ini'))), 'Save keeps the other variants as they were')

zpath = ed.save_zip(os.path.join(TMP, 'citypop.zip'))
with zipfile.ZipFile(zpath) as z:
    names = set(z.namelist())
check({'theme.ini', 'theme_43.ini', 'detail.ini', 'loading.ini'} <= names and any(n.startswith('img/') for n in names), 'Save as ZIP: .ini files and img/')

pic = os.path.join(TMP, 'square.png')
q = QImage(40, 20, QImage.Format.Format_ARGB32)
q.fill(QColor(255, 0, 0))
q.save(pic)
ed.add_assets([pic], 'img')
check(os.path.isfile(os.path.join(work, 'img', 'square.png')) and 'img/square.png' in ed.files.files, 'Add pictures copies into img/')
ed.create_element('image', [100, 100, 200, 100], {'src': 'img/square.png', 'fit': 'stretch'})
el = ed.selected()
ed.bake_rotation(el, 90)
check(el['props']['src'] == 'img/square_rot.png' and os.path.isfile(os.path.join(work, 'img', 'square_rot.png'))
      and te.parse_rect(el['props']['rect']) == [150, 50, 100, 200], 'rotation: rotated copy next to the original, rectangle turned')
rot = QImage(os.path.join(work, 'img', 'square_rot.png'))
check(rot.height() > rot.width(), 'rotation: the picture is turned')
ed.undo()
check(ed.selected()['props']['src'] == 'img/square.png', 'rotation: Undo')

# ---- New theme in an empty folder, example theme saved into a folder
newdir = os.path.join(TMP, 'my_theme')
os.makedirs(newdir)
ed.S['dirty'] = False
ed.new_theme_in_folder(folder=newdir)
check(os.path.isfile(os.path.join(newdir, 'theme.ini')) and ed.theme()['global'].get('name') == 'my_theme', 'New theme: theme.ini made in the folder')
ed.S['dirty'] = False
ed.open_example()
exdir = os.path.join(TMP, 'example')
os.makedirs(exdir)
ed.add_assets([pic], 'img')
check(not os.path.exists(os.path.join(exdir, 'img')) and ed.S['dirty'], 'Example theme: a picture added waits for a folder')
ed.save_to(exdir)
check(os.path.isfile(os.path.join(exdir, 'theme.ini')) and os.path.isfile(os.path.join(exdir, 'img', 'square.png')) and not ed.S['dirty'],
      'Example theme: Save into a folder writes theme.ini and copies the pictures')

# ---- unsaved work is kept
ed.snapshot()
ed.theme()['global']['name'] = 'Changed'
ed.session_tick()
ed2 = te.Editor()
ed2.confirm = lambda m: True
check(bool(ed2.last_session) and ed2.last_session['variants']['theme.ini']['global']['name'] == 'Changed', 'unsaved work is offered at the next start')
ed2.restore_session()
check(ed2.theme()['global']['name'] == 'Changed' and ed2.files.folder == exdir, 'Restore unsaved work')
ed2.S['dirty'] = False
ed2.close()

# ---- interface: Italian, light theme
ed.set_lang('it')
check(ed.btn_save.text() == 'Salva' and ed.tabs.tabText(2) == 'Dati di esempio', 'interface in Italian')
ed.set_lang('en')
ed.set_ui('light')
ed.set_ui('dark')
check(not log, 'no alerts' + (': ' + '; '.join(log) if log else ''))

ed.S['dirty'] = False
ed.close()
shutil.rmtree(TMP, ignore_errors=True)
print('%d FAILED' % failed if failed else 'all ok')
sys.exit(1 if failed else 0)
