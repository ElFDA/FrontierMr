#!/usr/bin/env python3
"""Write scraper/ss_dev.key, Frontier's ScreenScraper developer key, masked.

The key is not in git: tools/fe/ss_dev.secret (local, ignored by git) holds
'devid:devpassword'. The masked file goes with the SD files (package.py,
make_db.py, deploy.sh copy it); fe_scrape.py reads it. Whoever has Frontier can
still recover it (the scraper must send it in clear to ScreenScraper): the mask
only keeps it out of the source code and of searches.
  ss_key.py            write tools/fe/sd/frontier/scraper/ss_dev.key
  ss_key.py --check    exit 1 if it is missing or does not match the secret
"""
import argparse
import base64
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SECRET = HERE / 'ss_dev.secret'
SCRAPER = HERE / 'sd/frontier/scraper/fe_scrape.py'
KEY = SCRAPER.with_name('ss_dev.key')


def scraper():
    spec = importlib.util.spec_from_file_location('fe_scrape', SCRAPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encode(secret):
    raw = secret.encode()
    return base64.a85encode(bytes(a ^ b for a, b in zip(raw, scraper().ss_keystream(len(raw))))).decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not SECRET.is_file():
        sys.exit('%s is missing: put devid:devpassword in it' % SECRET)
    secret = SECRET.read_text().strip()
    if args.check:
        ok = KEY.is_file() and scraper().ss_dev() == secret.split(':', 1)
        print('ss_dev.key OK' if ok else 'ss_dev.key missing or different from the secret')
        sys.exit(0 if ok else 1)
    KEY.write_text(encode(secret) + '\n')
    print('Written', KEY)


if __name__ == '__main__':
    main()
