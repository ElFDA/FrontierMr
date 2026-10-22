#!/usr/bin/env python3
# Runs on the MiSTer: makes a virtual keyboard (uinput) and sends keys.
# Usage: python3 sendkeys.py down*3 leftalt+f12 enter   (names = KEY_* without prefix)
#      items "sleep:1.5" to wait, "hold:down:2" holds a key for 2 s
#      with the repeat of a real keyboard (250 ms, then every 33 ms).
import fcntl, os, struct, sys, time

KEYS = {'esc': 1, 'enter': 28, 'space': 57, 'tab': 15, 'up': 103, 'down': 108,
        'left': 105, 'right': 106, 'pageup': 104, 'pagedown': 109, 'home': 102,
        'end': 107, 'f12': 88, 'leftalt': 56, 'leftmeta': 125, 'back': 158, 'f1': 59, 'backspace': 14, 'minus': 12, 'equal': 13,
        'f2': 60, 'f5': 63, 'f9': 67, 'grave': 41, 'i': 23}
UI_SET_EVBIT, UI_SET_KEYBIT = 0x40045564, 0x40045565
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
EV_SYN, EV_KEY = 0, 1

fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
for code in range(1, 255):
    fcntl.ioctl(fd, UI_SET_KEYBIT, code)
# struct uinput_user_dev: name[80], id(4x u16), ff_effects_max, absmax/min/fuzz/flat[64]
dev = struct.pack('80sHHHHi', b'fe-test-keyboard', 3, 0x1234, 0x5678, 1, 0) + b'\0' * (64 * 4 * 4)
os.write(fd, dev)
fcntl.ioctl(fd, UI_DEV_CREATE)
time.sleep(2.5)  # MiSTer must detect the new device

def ev(t, c, v):
    s, us = divmod(int(time.time() * 1e6), 1000000)
    os.write(fd, struct.pack('llHHi', s, us, t, c, v))

for k in sys.argv[1:]:
    if k.startswith('sleep:'):
        time.sleep(float(k[6:]))
        continue
    if k.startswith('hold:'):
        _, name, secs = k.split(':')
        c, t0 = KEYS[name], time.time()
        ev(EV_KEY, c, 1); ev(EV_SYN, 0, 0)
        time.sleep(0.25)
        while time.time() - t0 < float(secs):
            ev(EV_KEY, c, 2); ev(EV_SYN, 0, 0)
            time.sleep(0.033)
        ev(EV_KEY, c, 0); ev(EV_SYN, 0, 0)
        time.sleep(0.2)
        continue
    rep = 1
    if '*' in k:
        k, rep = k.split('*')
        rep = int(rep)
    codes = [KEYS[x] for x in k.split('+')]  # e.g. leftalt+f12
    for _ in range(rep):
        for c in codes: ev(EV_KEY, c, 1); ev(EV_SYN, 0, 0); time.sleep(0.05)
        time.sleep(0.1)
        for c in reversed(codes): ev(EV_KEY, c, 0); ev(EV_SYN, 0, 0); time.sleep(0.05)
        time.sleep(0.2)

# MiSTer must read the last release before the device goes away: if it is busy
# (e.g. F5 reloads the theme for a second) a lost release stays "held" and the menu repeats it
time.sleep(2)
fcntl.ioctl(fd, UI_DEV_DESTROY)
os.close(fd)
