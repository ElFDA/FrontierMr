#!/usr/bin/env python3
# Makes frontier/systems.ini from the MiSTer catalog of Zaparoo
# (https://github.com/ZaparooProject/zaparoo-core, mister/catalog/catalog.json, GPL-3.0).
# Usage: python3 gen_systems.py <catalog.json> <systems.ini>
#   curl -sfLo /tmp/catalog.json https://raw.githubusercontent.com/ZaparooProject/zaparoo-core/main/mister/catalog/catalog.json
import json, re, sys

NAMES = {
    '3DO': '3DO', 'AmigaCD32': 'Amiga CD32', 'Amiga': 'Amiga', 'Amstrad': 'Amstrad CPC', 'AppleII': 'Apple II',
    'AppleIIGS': 'Apple IIGS', 'Atari2600': 'Atari 2600', 'Atari2600ARM': 'Atari 2600 (ARM)', 'Atari5200': 'Atari 5200', 'Atari7800': 'Atari 7800',
    'Atari800': 'Atari 800', 'AtariLynx': 'Atari Lynx', 'C64': 'Commodore 64', 'C128': 'Commodore 128',
    'C16': 'Commodore 16', 'VIC20': 'Commodore VIC-20', 'CDI': 'Philips CD-i', 'ColecoVision': 'ColecoVision',
    'FDS': 'Famicom Disk System', 'GBA': 'Game Boy Advance', 'Gameboy': 'Game Boy', 'GameboyColor': 'Game Boy Color',
    'SuperGameboy': 'Super Game Boy', 'GameGear': 'Game Gear', 'Genesis': 'Mega Drive / Genesis', 'Intellivision': 'Intellivision',
    'Jaguar': 'Atari Jaguar', 'MasterSystem': 'Master System', 'MegaCD': 'Mega CD', 'MSX': 'MSX', 'NeoGeo': 'Neo Geo',
    'NeoGeoCD': 'Neo Geo CD', 'NeoGeoPocket': 'Neo Geo Pocket', 'NeoGeoPocketColor': 'Neo Geo Pocket Color',
    'NES': 'NES / Famicom', 'Nintendo64': 'Nintendo 64', 'Odyssey2': 'Odyssey 2', 'PCFX': 'PC-FX', 'PSX': 'PlayStation',
    'Saturn': 'Sega Saturn', 'Sega32X': 'Sega 32X', 'SG1000': 'SG-1000', 'SNES': 'SNES / Super Famicom',
    'SuperGrafx': 'SuperGrafx', 'TurboGrafx16': 'PC Engine / TurboGrafx-16', 'TurboGrafx16CD': 'PC Engine CD',
    'Vectrex': 'Vectrex', 'VirtualBoy': 'Virtual Boy', 'WonderSwan': 'WonderSwan', 'WonderSwanColor': 'WonderSwan Color',
    'X68000': 'Sharp X68000', 'ZXSpectrum': 'ZX Spectrum', 'ao486': 'PC 486', 'PokemonMini': 'Pokémon Mini',
    'ChannelF': 'Channel F', 'Arcadia': 'Arcadia 2001', 'Astrocade': 'Bally Astrocade', 'BBCMicro': 'BBC Micro',
    'MegaDuck': 'Mega Duck', 'SuperVision': 'Watara Supervision', 'GameNWatch': 'Game & Watch', 'NDS': 'Nintendo DS',
}
# English Wikipedia article of each system: the scraper takes from it the description
# (in the language chosen, through the links between languages) and the hardware
WIKI = {
    '3DO': '3DO Interactive Multiplayer', 'AcornAtom': 'Acorn Atom', 'AcornElectron': 'Acorn Electron',
    'AdventureVision': 'Entex Adventure Vision', 'AliceMC10': 'TRS-80 MC-10', 'Altair8800': 'Altair 8800',
    'Amiga': 'Amiga', 'AmigaCD32': 'Amiga CD32', 'Amstrad': 'Amstrad CPC', 'AmstradNC': 'Amstrad NC100',
    'AmstradPCW': 'Amstrad PCW', 'ao486': 'I486', 'AppleI': 'Apple I', 'AppleII': 'Apple II',
    'AppleIIGS': 'Apple IIGS', 'AppleIII': 'Apple III', 'AppleLisa': 'Apple Lisa', 'Aquarius': 'Mattel Aquarius',
    'Arcadia': 'Arcadia 2001', 'Arduboy': 'Arduboy', 'Astrocade': 'Bally Astrocade', 'Atari2600': 'Atari 2600',
    'Atari2600ARM': 'Atari 2600', 'Atari5200': 'Atari 5200', 'Atari7800': 'Atari 7800',
    'Atari800': 'Atari 8-bit computers', 'AtariLynx': 'Atari Lynx', 'AtariLynx2P': 'Atari Lynx',
    'BBCBridgeCompanion': 'BBC Bridge Companion', 'BBCMicro': 'BBC Micro', 'BK0011M': 'Electronika BK',
    'C128': 'Commodore 128', 'C16': 'Commodore 16', 'C64': 'Commodore 64', 'CasioLoopy': 'Casio Loopy',
    'CasioPV1000': 'PV-1000', 'CasioPV2000': 'PV-2000', 'CBMII': 'Commodore CBM-II', 'CDI': 'CD-i',
    'ChannelF': 'Fairchild Channel F', 'Chip8': 'CHIP-8', 'CoCo2': 'TRS-80 Color Computer',
    'CoCo3': 'TRS-80 Color Computer', 'ColecoAdam': 'Coleco Adam', 'ColecoVision': 'ColecoVision',
    'CreatiVision': 'VTech CreatiVision', 'EDSAC': 'EDSAC', 'EG2000': 'Video Genie',
    'Enterprise': 'Enterprise (computer)', 'FDS': 'Family Computer Disk System', 'FM7': 'FM-7', 'FMTowns': 'FM Towns',
    'Galaksija': 'Galaksija (computer)', 'Gamate': 'Gamate', 'Gameboy': 'Game Boy', 'Gameboy2P': 'Game Boy',
    'GameboyColor': 'Game Boy Color', 'GameCom': 'Game.com', 'GameGear': 'Game Gear', 'GameGear2P': 'Game Gear',
    'GameKing': 'GameKing', 'GameNWatch': 'Game & Watch', 'GBA': 'Game Boy Advance', 'GBA2P': 'Game Boy Advance',
    'Genesis': 'Sega Genesis', 'Intellivision': 'Intellivision', 'Interact': 'Interact Home Computer',
    'IQ151': 'IQ 151', 'Jaguar': 'Atari Jaguar', 'JaguarCD': 'Atari Jaguar CD', 'JR100': 'National JR-100',
    'Jupiter': 'Jupiter Ace', 'Laser': 'VTech Laser 200', 'Lynx48': 'Camputers Lynx', 'MacIIvi': 'Macintosh IIvi',
    'MacLC': 'Macintosh LC', 'MacLCII': 'Macintosh LC II', 'MacPlus': 'Macintosh Plus',
    'MacQuadra800': 'Macintosh Quadra 800', 'MasterSystem': 'Master System', 'MegaCD': 'Sega CD',
    'MegaDuck': 'Mega Duck', 'MicroBee': 'MicroBee', 'MSX': 'MSX', 'MSX1': 'MSX', 'MyVision': 'My Vision',
    'NDS': 'Nintendo DS', 'NeoGeo': 'Neo Geo (system)', 'NeoGeoCD': 'Neo Geo CD', 'NeoGeoPocket': 'Neo Geo Pocket',
    'NeoGeoPocketColor': 'Neo Geo Pocket Color', 'NES': 'Nintendo Entertainment System', 'NeXT': 'NeXTcube',
    'Nintendo64': 'Nintendo 64', 'Odyssey2': 'Magnavox Odyssey 2', 'OpenBOR': 'OpenBOR', 'Orao': 'Orao (computer)',
    'Oric': 'Oric (computer)', 'PC88': 'PC-8800 series', 'PC98': 'PC-9800 series', 'PCFX': 'PC-FX',
    'PCjr': 'IBM PCjr', 'PCXT': 'IBM Personal Computer XT', 'PCXTEGA': 'IBM Personal Computer XT', 'PDP1': 'PDP-1',
    'PET2001': 'Commodore PET', 'PETUniversal': 'Commodore PET', 'Pico8': 'Pico-8', 'PMD85': 'PMD 85',
    'PocketStation': 'PocketStation', 'PokemonMini': 'Pokémon Mini', 'PSX': 'PlayStation (console)',
    'QL': 'Sinclair QL', 'RX78': 'Bandai RX-78', 'SAMCoupe': 'SAM Coupé', 'Saturn': 'Sega Saturn', 'Sega32X': '32X',
    'SG1000': 'SG-1000', 'SGIIndy': 'SGI Indy', 'SNES': 'Super Nintendo Entertainment System', 'SordM5': 'Sord M5',
    'SparcStation': 'SPARCstation', 'SparcStation20': 'SPARCstation 20', 'Specialist': 'Specialist (computer)',
    'StudioII': 'RCA Studio II', 'SuperACan': "Super A'can", 'SuperCassetteVision': 'Super Cassette Vision',
    'SuperGameboy': 'Super Game Boy', 'SuperGrafx': 'PC Engine SuperGrafx', 'SuperVision': 'Watara Supervision',
    'SuperVision8000': 'Bandai Super Vision 8000', 'SVI328': 'Spectravideo SV-328', 'System80': 'Video Genie',
    'Tamagotchi': 'Tamagotchi', 'Tandy1000': 'Tandy 1000', 'TatungEinstein': 'Tatung Einstein',
    'Thomson': 'Thomson MO5', 'TI89': 'TI-89 series', 'TI994A': 'TI-99/4A', 'TomyTutor': 'Tomy Tutor',
    'TRS80': 'TRS-80', 'TurboGrafx16': 'TurboGrafx-16', 'TurboGrafx16CD': 'TurboGrafx-CD', 'UK101': 'Compukit UK101',
    'VC4000': 'Interton VC 4000', 'Vector06C': 'Vector-06C', 'Vectrex': 'Vectrex', 'VIC20': 'Commodore VIC-20',
    'VideoBrain': 'VideoBrain Family Computer', 'VirtualBoy': 'Virtual Boy', 'VSmile': 'V.Smile',
    'WonderSwan': 'WonderSwan', 'WonderSwanColor': 'WonderSwan Color', 'X68000': 'X68000', 'ZX81': 'ZX81',
    'ZXNext': 'ZX Spectrum Next', 'ZXSpectrum': 'ZX Spectrum',
}
HANDHELD = {'Gameboy', 'GameboyColor', 'Gameboy2P', 'GBA', 'GBA2P', 'GameGear', 'GameGear2P', 'AtariLynx', 'AtariLynx2P',
            'WonderSwan', 'WonderSwanColor', 'NeoGeoPocket', 'NeoGeoPocketColor', 'PokemonMini', 'SuperVision', 'MegaDuck',
            'Gamate', 'GameCom', 'GameKing', 'PocketChallengeV2', 'NDS', 'GameNWatch', 'Tamagotchi', 'PocketStation',
            'TI89', 'SuperGameboy', 'VirtualBoy'}

# systems which load romsets (zip files or folders listed in romsets.xml), like the core's browser
ROMSETS = {'NeoGeo'}

def name_of(sid):
    return NAMES.get(sid) or re.sub(r'(?<=[a-z])(?=[A-Z0-9])', ' ', sid)

def category_of(sid, rbf):
    if sid in HANDHELD: return 'Handheld'
    for c in ('Console', 'Computer', 'Other'):
        if rbf.startswith('_' + c + '/'): return c
    return 'Other'

cat = json.load(open(sys.argv[1]))['systems']
out = ['; Systems for Frontier (/media/fat/frontier/systems.ini): folders in games/ -> core and MGL.',
       '; Made by tools/fe/systems/gen_systems.py from the MiSTer catalog of Zaparoo',
       '; (https://github.com/ZaparooProject/zaparoo-core, mister/catalog/catalog.json, GPL-3.0).',
       '; It can be edited by hand; F5 in Frontier reads it again.',
       ';   name      name shown',
       ';   wiki      English Wikipedia article of the system (data of the system for the scraper)',
       ';   category  Console, Handheld, Computer, Other',
       ';   rbf       core, as in the <rbf> tag of the MGLs (folder/name without date)',
       ';   folders   folders in games/ separated by |',
       ';   setname   <setname> of the MGL (optional), setname_same_dir=1 for same_dir="1"',
       ';   romsets   1 = romsets as the Neo Geo core loads them: zip files and folders of romsets.xml (in slot1)',
       ';   slotN     type,index,delay,extensions (type f = file, s = disk image; extensions separated by spaces)',
       '']
n = 0
for sid in sorted(cat, key=str.lower):
    s = cat[sid]
    slots = [x for x in s.get('slots', []) if x.get('mgl') and x.get('extensions')]
    if not s.get('rbf') or not s.get('folders') or not slots:
        continue
    out.append('[%s]' % sid)
    out.append('name=%s' % name_of(sid))
    if WIKI.get(sid):
        out.append('wiki=%s' % WIKI[sid])
    out.append('category=%s' % category_of(sid, s['rbf']))
    out.append('rbf=%s' % s['rbf'])
    out.append('folders=%s' % '|'.join(s['folders']))
    if s.get('setName'):
        out.append('setname=%s' % s['setName'])
        if s.get('setNameSameDir'): out.append('setname_same_dir=1')
    if sid in ROMSETS:
        out.append('romsets=1')
    for i, sl in enumerate(slots, 1):
        m = sl['mgl']
        exts = ' '.join(e.lstrip('.').lower() for e in sl['extensions'])
        out.append('slot%d=%s,%d,%d,%s' % (i, m.get('method', 'f'), m.get('index', 0), m.get('delay', 1), exts))
    out.append('')
    n += 1
open(sys.argv[2], 'w').write('\n'.join(out))
print('%d systems -> %s' % (n, sys.argv[2]))
