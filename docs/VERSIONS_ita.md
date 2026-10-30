# Quale versione di un gioco parte

Nei sistemi (Computer, Console, Handheld, Other) Frontier mostra **una voce
per titolo**: "Altered Beast" una volta sola, anche quando la cartella ha i
file USA, Europa e Giappone, revisioni e prototipi. A ne avvia uno, la
**versione predefinita**; le altre sono nei dettagli.

## La versione predefinita

Frontier legge i nomi dei file in stile [No-Intro](https://no-intro.org), ad
esempio `Altered Beast (USA, Europe) (Rev 1).md`, e sceglie in questo ordine:

1. **Uscite prima delle non uscite**: beta, prototipi, sample e demo vengono
   dopo le versioni uscite, anche di un'altra regione.
2. **La regione preferita**: la prima di `regions=` in
   `/media/fat/frontier/frontier.ini` che il file ha. Predefinito:
   `regions=USA,World,Europe,Japan`. Un file con più regioni,
   `(USA, Europe)`, vale come la migliore delle due; le regioni che non sono
   nella lista vengono dopo tutte quelle che ci sono.
3. **Originali prima delle riedizioni**: Virtual Console, Switch Online,
   console mini, raccolte, Evercade... vengono dopo.
4. **L'ultima revisione**: `(Rev 2)` prima di `(Rev 1)` prima di nessuna;
   `(v1.1)` prima di `(v1.0)`.
5. Una versione senza `(Alt)` prima di un dump alternativo.

Ad esempio, con `regions=` predefinito:

| File nella cartella | Parte |
|---|---|
| `Sonic (Japan)`, `Sonic (USA, Europe)` | `Sonic (USA, Europe)` |
| `Game (USA) (Beta)`, `Game (Japan)` | `Game (Japan)`: l'uscita prima della beta |
| `Game (USA)`, `Game (USA) (Rev 1)` | `Game (USA) (Rev 1)` |
| `Game (Europe)`, `Game (USA) (Virtual Console)` | `Game (Europe)`: prima l'originale |

## Un'altra regione per prima

Cambia l'ordine in `frontier.ini`, ad esempio l'Europa per prima:

```ini
regions=Europe,World,USA,Japan
```

oppure prima le versioni giapponesi: `regions=Japan,World,USA,Europe`. Si può
usare qualsiasi regione dei nomi No-Intro (France, Germany, Italy, Spain,
Korea, Brazil, Asia...). Poi premi F5 in Frontier (o riavvialo).

Lo stesso ordine dice anche allo scraper da quale regione prendere nomi e
immagini (vedi [SCRAPER_ita.md](SCRAPER_ita.md)).

## Le altre versioni

Su un gioco premi **X**: i dettagli elencano tutte le sue versioni (regioni,
revisioni, prototipi) e anche gli altri titoli dello stesso gioco, ad esempio
*Thunder Force IV* e *Lightening Force*, collegati dalle liste di MAME. A su
una versione avvia quella.

Per collegare i titoli diversi dello stesso gioco, una volta per sistema, da
SSH:

```sh
python3 /media/fat/frontier/scraper/fe_scrape.py --groups --system MegaDrive
```

poi F5.

Favorites e Recent tengono il titolo: anche loro avviano la versione
predefinita.

## Giochi su più dischi

Nei sistemi con immagini di disco (PlayStation, Saturn, Mega CD...) una cartella con
solo i dischi di un gioco, es. `games/PSX/Xenogears/Xenogears (Disc 1).chd` e
`(Disc 2).chd`, è **un solo gioco** col nome della cartella, anche se i nomi non hanno la
regione: sta nell'elenco del sistema (anche un cue/chd/iso da solo nella sua
cartella). **A** avvia il primo disco; **X** elenca tutti i dischi nei dettagli, per avviarne
un altro. Lo scraper dà al gioco le immagini del primo disco. I file devono differire solo per il
numero del disco (`(Disc 1)`, `(Disc 2 of 3)`, `- CD2`...); una cartella con sottocartelle
o con altri giochi resta una cartella.

## File senza la regione nel nome

Ogni file con un'estensione del sistema è un gioco, qualunque sia il nome. Senza una regione
alla No-Intro (hack, traduzioni, `Crash Bandicoot.chd`...) il titolo è il nome del file,
ripulito: `_` come spazi, senza `[!]`, senza il numero del disco (`Spyro (Disc 1)` e
`Spyro (Disc 2)` sono un solo gioco, `Spyro`, e i dischi sono le sue versioni nei dettagli). I
codici dei paesi di GoodTools `(U)`, `(E)`, `(J)`, `(UE)`... contano come regioni, quindi
`Sonic (U)` e `Sonic (E)` sono un solo titolo con due versioni. Di un nome
[TOSEC](https://www.tosecdev.org) conta solo il titolo: `Predator 2 (1991)(ImageWorks)(Disk 1 of 2)[cr CPY]`,
`(Disk 2 of 2)` e le altre copie sono un solo gioco, `Predator 2`, che avvia il primo disco della copia
con meno tag `[...]` (crack, trainer, alternative). I BIOS chiamati `[BIOS] ...`
non si elencano.

Restano fuori dagli elenchi due cose: uno zip con nomi liberi dentro (uno zip di giochi C64
chiamati `Spy vs Spy.crt`: dagli zip si leggono solo le rom con la regione) e le cartelle
chiamate `Extra` (giochi senza licenza, prototipi, hack...; altri nomi si aggiungono con
`exclude_dirs=` in `frontier.ini`). `folders=1` in `frontier.ini` aggiunge **Folders** in
cima a ogni sistema: le cartelle vere di `games/` come sono, dove uno zip si apre come una
cartella. Le cartelle si vedono anche in **MiSTer**, dalla prima schermata.

I computer (categoria Computer: C64, Amiga, Spectrum, MSX...) si aprono direttamente nelle loro
cartelle vere, non per titolo: le loro raccolte hanno nomi liberi e cartelle che contano. Ogni
sistema si passa dall'uno all'altro modo in *Frontier Settings → Systems view*
(`view_folders=` e `view_titles=` in `frontier.ini`; `view=folders|titles` in `systems.ini`
cambia il comportamento di base).

## Core con piu' configurazioni (Amiga)

Amiga, Amiga 500, Amiga 500HD e Amiga 600HD sono ognuno un sistema della
categoria Computer, con la sua cartella in `games/` (`games/Amiga500HD`...).
L'MGL di `_Computer` che avvia la configurazione e' la prima voce della
cartella (`launchers=` in `systems.ini`): cosi' una configurazione che parte
da sola, per esempio da un hard disk (`.hdf`), parte anche da Frontier. I
file `.adf` della cartella partono con la stessa configurazione. Un percorso di `launchers=`
che finisce con `/` prende tutti gli MGL di quella cartella: i giochi di `_Computer/_X68000 Games`
sono in Sharp X68000. Un launcher mostra immagini, video e dati del gioco con lo stesso nome (per i
nomi senza regione lo scraper vuole `--all-files`: `fe_scrape.py --system X68000 --all-files`) e dopo il
gioco Frontier riapre la stessa lista. VIC-20:
partono anche le cartucce `.rom` (Megacart, Ultimate...).

I dischi del Commodore 64 (`.d64 .g64 .t64 .d81`) partono da soli: dopo il disco l'MGL carica
`frontier/autorun/c64.prg`, che scrive `LOAD"*",8,1` e `RUN` (come fanno i launcher di MeGaLoSorTer).
I dischi di Coleco Adam e Apple III sono seguiti da un reset (`reset=` in `systems.ini`). Dischi e
cassette degli altri computer che vogliono comandi digitati (Amstrad, Spectrum, C128...) partono con
la macchina al prompt, perche' un MGL non puo' premere tasti.

## Arcade e Neo Geo

* **Arcade**: ogni `.mra` di `_Arcade` è una voce, come nel browser
  originale; le versioni in `_Arcade/_alternatives` sono nei dettagli (X).
* **Neo Geo**: i romset si usano come fa il core (file `.neo` con il setname,
  gli zip di `games/NEOGEO/romsets.xml`); lo stesso titolo è una voce sola,
  parte il `.neo`, gli altri sono nei dettagli.
