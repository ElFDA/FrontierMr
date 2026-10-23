# Theme editor

Il theme editor è una sola pagina web, `theme_editor.html`, per fare e modificare i
temi di Frontier sul PC: si trascinano gli elementi, si cambiano le proprietà e si
salvano i file `.ini`. Non richiede installazione né internet.
English: [THEME_EDITOR.md](THEME_EDITOR.md).

## Dove prenderlo

* Scarica [theme_editor.html](https://github.com/ElFDA/FrontierMr/releases/latest/download/theme_editor.html)
  (è un file di ogni release; **non** è nello ZIP per la SD, perché gira sul PC).
* Aprilo con Chrome o Edge (doppio clic). Salvano direttamente nella cartella del
  tema; gli altri browser possono solo scaricare i file `.ini` con
  **Download .ini**.

## Cosa serve

Un tema è una cartella con `theme.ini` e le immagini e i font che usa. Si parte
più facilmente da una copia di un tema della SD
(`/media/fat/frontier/themes/simple`, oppure `citypop`) sul PC, rinominata, per
esempio `mytheme`.

## Passo per passo

1. **Open folder**: scegli la tua copia e permetti all'editor di modificarla. Una
   cartella senza `theme.ini` parte da un tema vuoto (**New** fa lo stesso).
2. **Variant** sceglie il file che stai modificando:

   | File | Schermata |
   |---|---|
   | `theme.ini` / `theme_43.ini` | elenco dei giochi, 16:9 e 4:3 (CRT) |
   | `detail.ini` / `detail_43.ini` | dettaglio di un gioco (X sul pad) |
   | `screensaver.ini` / `screensaver_43.ini` | screensaver |

   Quelli che mancano si fanno da quello corrente: **Make 4:3** (x e larghezze
   × 0,75), **Make detail** (copia di `theme.ini`) e **Make screensaver** (copia
   di `detail.ini` senza le versioni). `loading.ini` / `loading_43.ini`
   (schermata di caricamento) si modificano allo stesso modo; se un tema non li
   ha, Frontier usa quelli del tema simple.
3. Clicca un elemento nell'area di disegno o nell'elenco a destra.
   **Trascinalo** per spostarlo, usa le maniglie per ridimensionarlo; le frecce
   spostano di 1 px, Maiusc + frecce di 10 px, Maiusc mentre trascini spegne la
   griglia. **Add** aggiunge un rettangolo, un'immagine, un testo, una lista, un
   video o una barra; **Duplicate**, **Delete** e ▲ ▼ (l'ordine conta dove gli
   elementi si sovrappongono). Ctrl+Z annulla.
4. Nel pannello cambi le proprietà: colori, font e `size` (altezza in px base,
   come in CSS), `src` di un'immagine, `if` / `ifnot` (mostra l'elemento solo se
   una variabile non è vuota / è vuota), `layout=media` o `layout=text` (solo
   senza / con *Text layout*). Le chiavi che l'editor non conosce restano in
   "Other keys" e vengono salvate così come sono. **Add pictures...** copia le
   immagini nella cartella `img/` del tema.
5. **Sample data** (sotto il pannello) sono i valori delle `${variabili}` nell'anteprima:
   cambiali per vedere un titolo lungo, nessuna immagine, tanti giocatori... Ci
   sono anche `${game.cpu}`, `${game.memory}`, `${game.graphics}`,
   `${game.sound}`, `${game.media}` e `${game.units}` dei sistemi.
6. L'anteprima si regola con **Zoom**, **grid 8**, **240p preview** (come su un
   CRT a 240 righe: righe dimezzate e raddoppiate) e **text layout** (il tema
   come con *Text layout* ON). **Import .ini** carica i file `.ini` di un altro
   tema nell'editor, tenendo le immagini e i font della cartella aperta; chiede
   conferma prima di sostituire e si può annullare.
7. **Save to folder** scrive i file `.ini` nella cartella aperta (o **Download
   .ini** negli altri browser). I file vengono riscritti con le chiavi in ordine
   fisso e i commenti solo in testa.

## Provarlo sul MiSTer

1. Copia la cartella del tema in `/media/fat/frontier/themes/` sulla SD.
2. Sceglilo in Frontier Settings -> Themes, oppure scrivi `theme=mytheme` in
   `frontier.ini`.
3. Premi F5 in Frontier per ricaricarlo. Modifica, salva, copia di nuovo, F5.

## Limiti

* L'anteprima è approssimata e le animazioni (dissolvenze, scorrimento,
  fotogrammi, video) non sono animate.
* I font fuori dalla cartella aperta (per esempio `../simple/fonts/`) nell'editor
  si vedono in sans-serif: copiali in una cartella `fonts/` del tema e punta
  `font` lì; funziona anche sul MiSTer.

## Altro

* [GUIDA_TEMA_ita.txt](../tools/fe/sd/frontier/GUIDA_TEMA_ita.txt) rifà passo per
  passo il tema City Pop con l'editor (anche sulla SD, in `/media/fat/frontier/`).
* Le chiavi dei temi sono descritte (in inglese) in testa a
  `themes/simple/theme.ini`.
