#!/usr/bin/env python3
"""Frontier MRTE: theme editor for Frontier, the MiSTer frontend.

A desktop program (Windows, macOS, Linux) that opens the folder of a theme
(/media/fat/frontier/themes/<name>/ copied to the computer, or the SD card
itself), shows a preview drawn with the same rules as fe_render.cpp, and
writes the .ini files back into the folder.

Needs Python 3.9 or newer and PySide6:
    pip install PySide6
    python theme_editor.py [theme folder]
"""

import copy
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile

os.environ.setdefault('QT_LOGGING_RULES', 'qt.multimedia*=false')   # no decoder messages for the first frames of the videos

try:
    from PySide6.QtCore import (QByteArray, QEvent, QObject, QPoint, QPointF, QRectF, QSettings, QSize,
                                QStandardPaths, Qt, QTimer, QUrl, Signal)
    from PySide6.QtGui import (QAction, QBrush, QColor, QCursor, QFont, QFontDatabase, QFontMetricsF, QIcon,
                               QImage, QImageReader, QKeySequence, QLinearGradient, QPainter, QPalette, QPen,
                               QPixmap, QRawFont, QTransform)
    from PySide6.QtWidgets import (QAbstractItemView, QAbstractSpinBox, QApplication, QColorDialog, QComboBox,
                                   QCompleter, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                                   QListWidget, QListWidgetItem, QMainWindow, QMenu, QMenuBar, QMessageBox,
                                   QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
                                   QStackedWidget, QTabWidget, QTextBrowser, QTextEdit, QToolButton,
                                   QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
    from PySide6.QtSvg import QSvgRenderer
except ImportError:
    sys.stderr.write('This program needs PySide6 (Qt for Python). Install it with:\n    pip install PySide6\n')
    sys.exit(1)

try:
    from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
except ImportError:   # first frames of the videos are then not shown
    QMediaPlayer = QVideoSink = None

IS_MAC = sys.platform == 'darwin'   # menus in the system menu bar, shortcuts shown by macOS
APP_VERSION = '0.3.2'   # counter: after x.x.9 the next ten starts (0.2.9 -> 0.3.0)

# ======================================================================
# Language: automatic from the system (Italian or English), or chosen in View > Language
# ======================================================================

IT = {
    'File': 'File',
    'Edit': 'Modifica',
    'View': 'Vista',
    'Variant': 'Variante',
    'Help': 'Aiuto',
    'Open folder': 'Apri cartella',
    'Open a theme folder (theme.ini, pictures, fonts)  Ctrl+O': 'Apri una cartella tema (theme.ini, immagini, font)  Ctrl+O',
    'Align to canvas': 'Allinea alla tela',
    'Align left': 'Allinea a sinistra',
    'Center horizontally': 'Centra in orizzontale',
    'Align right': 'Allinea a destra',
    'Align top': 'Allinea in alto',
    'Center vertically': 'Centra in verticale',
    'Align bottom': 'Allinea in basso',
    'Grid': 'Griglia',
    "Show the 32 px grid  Ctrl+'": "Mostra la griglia da 32 px  Ctrl+'",
    'Snap 8': 'Aggancio 8',
    'Snap to an 8 px grid (Shift while dragging = off)': 'Aggancia a una griglia da 8 px (Shift mentre trascini = disattivato)',
    '240i preview': 'Anteprima 240i',
    'Shows it as on a 240i CRT: 480 lines drawn as two alternating fields, so thin horizontal lines flicker': 'Lo mostra come su un CRT 240i: 480 righe disegnate in due semiquadri alternati, quindi le linee orizzontali sottili sfarfallano',
    '240i CRT preview': 'Anteprima CRT 240i',
    '240p preview': 'Anteprima 240p',
    'Shows it as on a 240p CRT: lines halved and doubled': 'Lo mostra come su un CRT 240p: righe dimezzate e raddoppiate',
    'Text layout': 'Text layout',
    'As with Frontier Settings > Themes > Text layout ON: elements with layout=text instead of layout=media': 'Come con Frontier Settings > Themes > Text layout ON: gli elementi con layout=text al posto di quelli con layout=media',
    'Undo  Ctrl+Z': 'Annulla  Ctrl+Z',
    'Redo  Ctrl+Shift+Z': 'Ripristina  Ctrl+Shift+Z',
    'Help and shortcuts': 'Aiuto e scorciatoie',
    'Layers': 'Livelli',
    'Assets': 'Risorse',
    'Sample data': 'Dati di esempio',
    'Properties': 'Proprietà',
    'New layer': 'Nuovo livello',
    'Duplicate  Ctrl+D': 'Duplica  Ctrl+D',
    'Bring forward  Ctrl+]': 'Porta avanti  Ctrl+]',
    'Send backward  Ctrl+[': 'Porta indietro  Ctrl+[',
    'Delete  Del': 'Elimina  Del',
    'Add pictures…': 'Aggiungi immagini…',
    'Copies pictures to the img/ folder of the theme': 'Copia le immagini nella cartella img/ del tema',
    'Drag to resize': 'Trascina per ridimensionare',
    'Zoom out  Ctrl+-': 'Riduci  Ctrl+-',
    'Zoom': 'Zoom',
    'Zoom in  Ctrl++': 'Ingrandisci  Ctrl++',
    'Fit': 'Adatta',
    'Interface theme (Shift+F1 darker, Shift+F2 lighter)': "Tema dell'interfaccia (Shift+F1 più scuro, Shift+F2 più chiaro)",
    'Light': 'Chiaro',
    'Medium gray': 'Grigio medio',
    'Dark gray': 'Grigio scuro',
    'Drop the theme folder here': 'Rilascia qui la cartella del tema',
    'Close': 'Chiudi',
    'Select': 'Selezione',
    'Rectangle': 'Rettangolo',
    'Picture': 'Immagine',
    'Text': 'Testo',
    'List': 'Lista',
    'Video': 'Video',
    'Bar': 'Barra',
    'Select / move  (V)': 'Selezione / sposta  (V)',
    'Rectangle  (U): drag to draw': 'Rettangolo  (U): trascina per disegnare',
    'Picture  (P): drag to draw': 'Immagine  (P): trascina per disegnare',
    'Text  (T): drag to draw': 'Testo  (T): trascina per disegnare',
    'List  (L): drag to draw': 'Lista  (L): trascina per disegnare',
    'Video  (M): drag to draw': 'Video  (M): trascina per disegnare',
    'Progress bar  (B): drag to draw': 'Barra di avanzamento  (B): trascina per disegnare',
    'New theme…': 'Nuovo tema…',
    'Open folder…': 'Apri cartella…',
    'Load .ini…': 'Carica .ini…',
    'Undo': 'Annulla',
    'Redo': 'Ripristina',
    'Duplicate layer': 'Duplica livello',
    'Delete layer': 'Elimina livello',
    'Bring forward': 'Porta avanti',
    'Send backward': 'Porta indietro',
    'Deselect': 'Deseleziona',
    'Zoom in': 'Ingrandisci',
    'Zoom out': 'Riduci',
    'Fit on screen': 'Adatta allo schermo',
    'Show grid': 'Mostra griglia',
    'Snap to grid (8 px)': 'Aggancia alla griglia (8 px)',
    '240p CRT preview': 'Anteprima CRT 240p',
    'Interface: Light': 'Interfaccia: Chiaro',
    'Interface: Medium gray': 'Interfaccia: Grigio medio',
    'Interface: Dark gray': 'Interfaccia: Grigio scuro',
    'Language': 'Lingua',
    'Auto (follows the system)': 'Automatica (come il sistema)',
    'Game list': 'Lista giochi',
    'Detail': 'Dettaglio',
    'Screensaver': 'Screensaver',
    'Loading': 'Caricamento',
    'Screen': 'Schermata',
    'Other files': 'Altri file',
    '+ make {0}': '+ crea {0}',
    'Make 4:3': 'Crea 4:3',
    'Make detail': 'Crea dettaglio',
    'Make screensaver': 'Crea screensaver',
    'Makes the 4:3 variant (theme_43.ini, detail_43.ini...) adapting the current 16:9 one: x and widths ×0.75':
        'Crea la variante 4:3 (theme_43.ini, detail_43.ini...) adattando quella 16:9 corrente: x e larghezze ×0,75',
    'needs {0}': 'serve {0}',
    '{0} does not exist yet. Make it from {1}?': '{0} non esiste ancora. Lo creo da {1}?',
    '{0} does not exist and there is nothing to make it from': "{0} non esiste e non c'è da cosa crearlo",
    '{0} made from {1}: x and widths scaled to 4:3, check the layout': '{0} creato da {1}: x e larghezze portate a 4:3, controlla il layout',
    '16:9 screens: theme.ini, detail.ini, screensaver.ini': 'Schermi 16:9: theme.ini, detail.ini, screensaver.ini',
    '4:3 screens (CRT): theme_43.ini, detail_43.ini, screensaver_43.ini. If the file does not exist yet it is made from the 16:9 one': 'Schermi 4:3 (CRT): theme_43.ini, detail_43.ini, screensaver_43.ini. Se il file non esiste ancora viene creato da quello 16:9',
    'Which screen of the theme you are editing: game list, detail, screensaver': 'Quale schermata del tema stai modificando: lista giochi, dettaglio, screensaver',
    'How to use it and shortcuts': 'Come si usa e scorciatoie',
    "What's new": 'Novità',
    'Insert a variable': 'Inserisci una variabile',
    'General': 'Generali',
    'Game': 'Gioco',
    'Media': 'Media',
    'picture': 'immagine',
    '(empty)': '(vuoto)',
    'Theme file… (type img/name.png)': 'File del tema… (scrivi img/nome.png)',
    'Show / hide in the editor (it is still saved)': "Mostra / nascondi nell'editor (resta comunque nel file)",
    'Theme settings': 'Impostazioni tema',
    'Open a theme folder or make a new theme.': 'Apri una cartella tema o crea un nuovo tema.',
    'Nothing selected: these are the global settings of the theme.': 'Nessuna selezione: queste sono le impostazioni globali del tema.',
    'Name of the [name] section in the file': 'Nome della sezione [nome] nel file',
    '(default)': '(predefinito)',
    'width': 'larghezza',
    'height': 'altezza',
    'Name already used by another element': 'Nome già usato da un altro elemento',
    'Visibility': 'Visibilità',
    'Show this element': 'Mostra questo elemento',
    'Always': 'Sempre',
    'Only if a variable has a value': 'Solo se una variabile ha un valore',
    'Only if a variable is empty': 'Solo se una variabile è vuota',
    'Custom condition (see Advanced conditions)': 'Condizione personalizzata (vedi Condizioni avanzate)',
    'Variable': 'Variabile',
    'Visible only when {0} has a value (is not empty).': 'Visibile solo quando {0} ha un valore (non è vuota).',
    'Visible only when {0} is empty.': 'Visibile solo quando {0} è vuota.',
    'This element has a custom condition: edit it in "Advanced conditions" below.': 'Questo elemento ha una condizione personalizzata: modificala in "Condizioni avanzate" qui sotto.',
    'Visible in': 'Visibile in',
    'Both layouts': 'Entrambi i layout',
    'Picture layout only': 'Solo layout con immagini',
    'Text layout only': 'Solo layout testuale',
    'Text layout shows descriptions instead of pictures (a Frontier setting). Use "Text layout" in the top bar to preview it.': 'Il layout testuale mostra le descrizioni al posto delle immagini (impostazione di Frontier). Usa "Text layout" nella barra in alto per vederlo in anteprima.',
    'Now in the preview: shown': "Ora nell'anteprima: visibile",
    'Now in the preview: hidden by the condition': "Ora nell'anteprima: nascosto dalla condizione",
    'Now in the preview: hidden by the layout': "Ora nell'anteprima: nascosto dal layout",
    'Advanced conditions': 'Condizioni avanzate',
    'Raw if / ifnot. "if" = visible if the text is not empty, "ifnot" = visible if it is empty. You can mix variables, e.g. ${a}${b}.': 'if / ifnot in forma grezza. "if" = visibile se il testo non è vuoto, "ifnot" = visibile se è vuoto. Si possono mescolare variabili, es. ${a}${b}.',
    'Animate GIF': 'Anima GIF',
    'Animate GIFs': 'Anima le GIF',
    'Plays the animated GIFs in the preview (off = first frame, lighter on the computer)': "Riproduce le GIF animate nell'anteprima (spento = primo fotogramma, più leggero per il computer)",
    'GIF: it is animated only in this preview. Make sure your version of Frontier can read GIF files on the MiSTer; otherwise use a sequence of frames (src with *) and fps.': 'GIF: si anima solo in questa anteprima. Verifica che la tua versione di Frontier sappia leggere i file GIF sul MiSTer; altrimenti usa una sequenza di fotogrammi (src con *) e fps.',
    'Theme': 'Tema',
    'Background': 'Sfondo',
    'Text defaults': 'Testo predefinito',
    'Fill': 'Riempimento',
    'Font': 'Font',
    'Effects': 'Effetti',
    'Scrolling': 'Scorrimento',
    'Colors': 'Colori',
    'Tags and text': 'Etichette e testo',
    'Layer': 'Livello',
    'Transform': 'Trasformazione',
    'Conditions': 'Condizioni',
    'Other keys': 'Altre chiavi',
    'Pictures': 'Immagini',
    'Fonts': 'Font',
    'No pictures.': 'Nessuna immagine.',
    'No fonts.': 'Nessun font.',
    'Open a folder to see pictures and fonts.': 'Apri una cartella per vedere immagini e font.',
    '{0} pictures, {1} fonts in "{2}". Double-click to apply to the selection.': '{0} immagini, {1} font in "{2}". Doppio click per applicarli alla selezione.',
    'Double-click: apply to the selection': 'Doppio click: applica alla selezione',
    'Double-click: apply to the selection (or as the theme font)': 'Doppio click: applica alla selezione (o come font del tema)',
    'Background = {0}': 'Sfondo = {0}',
    'Theme font = {0}': 'Font del tema = {0}',
    'No theme open': 'Nessun tema aperto',
    'new theme': 'nuovo tema',
    'untitled theme': 'tema senza titolo',
    'modified': 'modificato',
    'Save': 'Salva',
    'Writes all the .ini files in the open folder  Ctrl+S': 'Scrive tutti i file .ini nella cartella aperta  Ctrl+S',
    'Downloads the .ini files of the theme (create or open the theme in a folder with Chrome/Edge to save in place)  Ctrl+S': 'Scarica i file .ini del tema (crea o apri il tema in una cartella con Chrome/Edge per salvare direttamente)  Ctrl+S',
    '{0} downloaded': '{0} scaricati',
    'New theme created in {0}': 'Nuovo tema creato in {0}',
    'There is no theme.ini in "{0}", but there are these .ini files: {1}. Open them as the theme, using these names?': 'In "{0}" non c\'è theme.ini, ma ci sono questi file .ini: {1}. Li apro come tema, con questi nomi?',
    'This browser cannot write in a folder: Save will download the .ini files': 'Questo browser non può scrivere in una cartella: Salva scaricherà i file .ini',
    'The folder "{0}" already contains a theme.ini. Open it instead of creating a new one?': 'La cartella "{0}" contiene già un theme.ini. Aprirlo invece di crearne uno nuovo?',
    'Discard the changes?': 'Scartare le modifiche?',
    'There is no theme.ini in the folder: starting from a new theme.': "Nella cartella non c'è theme.ini: si parte da un tema nuovo.",
    'Saved to {0}': 'Salvato in {0}',
    'Saving failed: {0}': 'Salvataggio non riuscito: {0}',
    'Only one file with another name at a time: it goes into the current variant ({0}).': 'Un solo file con un altro nome alla volta: va nella variante corrente ({0}).',
    'Replace {0} with the imported file?': 'Sostituire {0} con il file importato?',
    '{0} imported': '{0} importato',
    '{0} imported: open the theme folder for its pictures and fonts': '{0} importato: apri la cartella del tema per le sue immagini e i suoi font',
    'Copy failed: {0}': 'Copia non riuscita: {0}',
    'Videos': 'Video',
    'No videos.': 'Nessun video.',
    'Add videos…': 'Aggiungi video…',
    'Copies videos (.mp4, .mkv, .webm...) to the video/ folder of the theme': 'Copia i video (.mp4, .mkv, .webm...) nella cartella video/ del tema',
    '{0} pictures, {1} videos, {2} fonts in "{3}". Double-click to apply to the selection.': '{0} immagini, {1} video, {2} font in "{3}". Doppio click per applicarli alla selezione.',
    '{0} videos copied to video/': '{0} video copiati in video/',
    '{0} videos loaded: copy them yourself to video/ in the theme folder': '{0} video caricati: copiali tu in video/ nella cartella del tema',
    'Videos must be .mp4, .mkv, .webm, .avi, .mov or .mpg files': 'I video devono essere file .mp4, .mkv, .webm, .avi, .mov o .mpg',
    '{0} already exists in {1}/ and is different. Replace it?': '{0} esiste già in {1}/ ed è diverso. Lo sostituisco?',
    'This browser cannot show the first frame of this video (the file is copied anyway)': 'Questo browser non riesce a mostrare il primo fotogramma del video (il file viene copiato lo stesso)',
    'Rotation {0}°  (release to apply, Shift = steps of 15°)': 'Rotazione {0}°  (rilascia per applicare, Maiusc = scatti di 15°)',
    'Rotation needs a picture of the theme (PNG or JPG) in src': "Per ruotare serve un'immagine del tema (PNG o JPG) in src",
    'Rotation needs a picture of the theme (PNG or JPG) in src, not a ${variable}.': "Per ruotare serve un'immagine del tema (PNG o JPG) in src, non una ${variabile}.",
    'Cannot read {0}': 'Non riesco a leggere {0}',
    'rotate': 'ruota',
    'Rotate': 'Ruota',
    'Turns the picture: makes a rotated copy (the original stays in the folder) and uses it. You can also drag just outside a corner handle.': "Ruota l'immagine: crea una copia ruotata (l'originale resta nella cartella) e la usa. Puoi anche trascinare appena fuori da una maniglia d'angolo.",
    'Picture rotated {0}°: the original is untouched, the rotated copy is {1}': "Immagine ruotata di {0}°: l'originale non è toccato, la copia ruotata è {1}",
    'Picture rotated {0}°: the rotated copy is {1} (copy it yourself to the theme folder)': 'Immagine ruotata di {0}°: la copia ruotata è {1} (copiala tu nella cartella del tema)',
    'Start a new theme, open the folder of one you already have, or look at the example.': "Inizia un tema nuovo, apri la cartella di uno che hai già, oppure guarda l'esempio.",
    'Example theme': 'Tema di esempio',
    'You can also drop a theme folder here.': 'Puoi anche trascinare qui la cartella di un tema.',
    'Reopen "{0}"': 'Riapri "{0}"',
    'Cannot reopen the folder: {0}': 'Non riesco a riaprire la cartella: {0}',
    'This browser cannot write into a theme folder: Save will download a ZIP with the whole theme. Chrome and Edge can save straight into the folder.': 'Questo browser non può scrivere in una cartella del tema: Salva scarica uno ZIP con tutto il tema. Chrome ed Edge possono salvare direttamente nella cartella.',
    'There is no theme.ini directly in "{0}", but there is one in: {1}. Choose that folder instead.': 'Non c\'è nessun theme.ini direttamente in "{0}", ma ce n\'è uno in: {1}. Scegli quella cartella.',
    'There is no theme.ini in the folder "{0}": nothing was opened. Choose the folder that contains theme.ini.': 'Non c\'è nessun theme.ini nella cartella "{0}": non ho aperto niente. Scegli la cartella che contiene theme.ini.',
    'Opened "{0}": this browser cannot write into the folder, Save will download a ZIP with the whole theme': 'Aperta "{0}": questo browser non può scrivere nella cartella, Salva scaricherà uno ZIP con tutto il tema',
    'Saved in the folder "{0}": {1}': 'Salvato nella cartella "{0}": {1}',
    '{0} downloaded to your Downloads folder: it holds the whole theme (.ini, img/, fonts/, video/)': '{0} scaricato nella cartella Download: contiene tutto il tema (.ini, img/, fonts/, video/)',
    'This browser cannot write into the theme folder, so Save downloads a ZIP ({0}) with the whole theme: the .ini files and the img/, fonts/ and video/ folders. Unzip it and use that folder on the MiSTer (or in place of your old theme folder). Chrome and Edge can save straight into the folder.': 'Questo browser non può scrivere nella cartella del tema, quindi Salva scarica uno ZIP ({0}) con tutto il tema: i file .ini e le cartelle img/, fonts/ e video/. Scompattalo e usa quella cartella sul MiSTer (o al posto della vecchia cartella del tema). Chrome ed Edge possono salvare direttamente nella cartella.',
    'Writing in the theme folder': 'Scrive nella cartella del tema',
    'In memory only': 'Solo in memoria',
    'Save writes straight into the theme folder, and pictures, videos and fonts are copied into it.': 'Salva scrive direttamente nella cartella del tema, e immagini, video e font vengono copiati lì dentro.',
    'This browser cannot write into the folder: Save makes a ZIP with the whole theme (.ini, img/, fonts/, video/). Chrome and Edge can write straight into the folder.': 'Questo browser non può scrivere nella cartella: Salva crea uno ZIP con tutto il tema (.ini, img/, fonts/, video/). Chrome ed Edge possono scrivere direttamente nella cartella.',
    'Save as ZIP…': 'Salva come ZIP…',
    'Restore unsaved work': 'Recupera il lavoro non salvato',
    'Restore unsaved work: "{0}" ({1})': 'Recupera il lavoro non salvato: "{0}" ({1})',
    'Work restored: "{0}"': 'Lavoro recuperato: "{0}"',
    '{0} fonts added in memory: Save makes a ZIP with them in fonts/': '{0} font aggiunti in memoria: Salva crea uno ZIP con loro in fonts/',
    '{0} videos added in memory: Save makes a ZIP with them in video/': '{0} video aggiunti in memoria: Salva crea uno ZIP con loro in video/',
    '{0} pictures added in memory: Save makes a ZIP with them in img/': '{0} immagini aggiunte in memoria: Salva crea uno ZIP con loro in img/',
    'Picture rotated {0}°: the rotated copy is {1} (in memory: Save makes a ZIP with it)': 'Immagine ruotata di {0}°: la copia ruotata è {1} (in memoria: Salva crea uno ZIP che la contiene)',
    'Add fonts…': 'Aggiungi font…',
    'Copies fonts (.ttf, .otf) to the fonts/ folder of the theme': 'Copia i font (.ttf, .otf) nella cartella fonts/ del tema',
    '{0} fonts copied to fonts/': '{0} font copiati in fonts/',
    '{0} fonts loaded: copy them yourself to fonts/ in the theme folder': '{0} font caricati: copiali tu in fonts/ nella cartella del tema',
    '{0} is already in fonts/: not replaced (rename the file if it is another font)': '{0} è già in fonts/: non sostituito (rinomina il file se è un altro font)',
    'Fonts must be .ttf or .otf files': 'I font devono essere file .ttf o .otf',
    'Pictures must be PNG, JPG or GIF files': 'Le immagini devono essere file PNG, JPG o GIF',
    '.otf font: the Frontier guide speaks of TTF, if it does not show on the MiSTer convert it to .ttf': 'Font .otf: la guida di Frontier parla di TTF, se sul MiSTer non si vede convertilo in .ttf',
    '{0} pictures copied to img/': '{0} immagini copiate in img/',
    '{0} pictures loaded: copy them yourself to img/ in the theme folder': '{0} immagini caricate: copiale tu in img/ nella cartella del tema',
    '{0} made from a copy of {1}: change the list into the versions, add the description': '{0} creato da una copia di {1}: trasforma la lista nelle versioni e aggiungi la descrizione',
    '{0} made from a copy of {1} without the versions: make the description bigger, help "Start: play"': '{0} creato da una copia di {1} senza le versioni: ingrandisci la descrizione, aiuto "Start: gioca"',
    'Theme name': 'Nome del tema',
    'Reference resolution, e.g. 1280x720': 'Risoluzione di riferimento, es. 1280x720',
    'Background picture (theme file)': 'Immagine di sfondo (file del tema)',
    'cover / contain / stretch': 'cover (riempie) / contain (contiene) / stretch (deforma)',
    'contain / cover / stretch': 'contain (contiene) / cover (riempie) / stretch (deforma)',
    'Background color': 'Colore di sfondo',
    'TTF font (theme file)': 'Font TTF (file del tema)',
    'Font height in base px': 'Altezza del font in px base',
    'Color': 'Colore',
    'Text shadow color': "Colore dell'ombra del testo",
    'Shadow offset (base px)': "Scostamento dell'ombra (px base)",
    'Element type': 'Tipo di elemento',
    'x, y, width, height': 'x, y, larghezza, altezza',
    'Visible only if the expanded text is not empty': 'Visibile solo se il testo espanso non è vuoto',
    'Visible only if the expanded text is empty': 'Visibile solo se il testo espanso è vuoto',
    'media = only with the pictures, text = only with "Text layout" ON (descriptions in place of the pictures), empty = always': 'media = solo con le immagini, text = solo con "Text layout" attivo (descrizioni al posto delle immagini), vuoto = sempre',
    'Second color (vertical gradient)': 'Secondo colore (sfumatura verticale)',
    'Theme file or ${media.snap}|${media.title}|img/none.png': 'File del tema oppure ${media.snap}|${media.title}|img/none.png',
    'left / center / right': 'sinistra / centro / destra',
    'top / middle / bottom': 'alto / centro / basso',
    'fade 250 = fade in ms': 'fade 250 = dissolvenza in ms',
    'Frames per second (src with *)': 'Fotogrammi al secondo (src con *)',
    'Text with ${variables}': 'Testo con ${variabili}',
    '1 = wraps': '1 = va a capo',
    'horizontal / vertical: scrolls if it does not fit': 'horizontal / vertical: scorre se non entra',
    'base px per second': 'px base al secondo',
    'ms before scrolling': 'ms prima di scorrere',
    'Row height (base px)': 'Altezza della riga (px base)',
    'Inner margin (base px)': 'Margine interno (px base)',
    'Folder color': 'Colore delle cartelle',
    'Color of the tags on the right': 'Colore delle etichette a destra',
    'Folder tag': 'Etichetta delle cartelle',
    'Tag of ..': 'Etichetta di ..',
    'Selection bar color': 'Colore della barra di selezione',
    'Selected text color': 'Colore del testo selezionato',
    'Selection bar picture': 'Immagine della barra di selezione',
    '1 = long selected name scrolls': '1 = il nome selezionato troppo lungo scorre',
    'Bar width (0 = none)': 'Larghezza della barra (0 = nessuna)',
    'Bar color': 'Colore della barra',
    'Knob color': 'Colore del cursore',
    'Text if the folder is empty': 'Testo se la cartella è vuota',
    'ms before the video starts': 'ms prima che parta il video',
    'Progress in percent, e.g. ${progress}': 'Avanzamento in percentuale, es. ${progress}',
    'Font width': 'Larghezza del font',
    'Font hinting': 'Hinting del font',
}

IT.update({
    # strings of the desktop program (the ones above come from the web editor 0.2.7)
    'Not in a folder yet': 'Non ancora in una cartella',
    'Save asks for the folder of the theme and writes the .ini files, pictures, videos and fonts into it.':
        'Salva chiede la cartella del tema e ci scrive i file .ini, le immagini, i video e i font.',
    'Writes all the .ini files in the theme folder  Ctrl+S': 'Scrive tutti i file .ini nella cartella del tema  Ctrl+S',
    'Asks for the folder of the theme, then writes everything into it  Ctrl+S': 'Chiede la cartella del tema, poi ci scrive tutto  Ctrl+S',
    'The folder "{0}" already contains a theme.ini. Replace it with this theme?': 'La cartella "{0}" contiene già un theme.ini. Sostituirlo con questo tema?',
    'Choose the folder of the theme': 'Scegli la cartella del tema', 'Choose the folder of the new theme': 'Scegli la cartella del nuovo tema',
    'Save the theme as ZIP': 'Salva il tema come ZIP', 'Load .ini files': 'Carica file .ini',
    'Add pictures': 'Aggiungi immagini', 'Add videos': 'Aggiungi video', 'Add fonts': 'Aggiungi font',
    'Theme files': 'File dei temi', 'Pictures': 'Immagini', 'Videos': 'Video', 'Fonts': 'Font',
    '{0} saved: it holds the whole theme (.ini, img/, fonts/, video/)': '{0} salvato: contiene tutto il tema (.ini, img/, fonts/, video/)',
    'Opened "{0}"': 'Aperta "{0}"', 'Cannot show the first frame of this video (the file is copied anyway)': 'Non riesco a mostrare il primo fotogramma del video (il file viene copiato lo stesso)',
    'Picture rotated {0}°: the rotated copy is {1} (Save puts it in the theme folder)': 'Immagine ruotata di {0}°: la copia ruotata è {1} (Salva la mette nella cartella del tema)',
    '{0} pictures added: Save copies them to img/': '{0} immagini aggiunte: Salva le copia in img/',
    '{0} videos added: Save copies them to video/': '{0} video aggiunti: Salva li copia in video/',
    '{0} fonts added: Save copies them to fonts/': '{0} font aggiunti: Salva li copia in fonts/',
    'Opacity: 100% solid, 0% invisible (saved as the AA of #RRGGBBAA)': 'Opacità: 100% pieno, 0% invisibile (salvata come AA di #RRGGBBAA)',
    'Choose the color': 'Scegli il colore', 'Language': 'Lingua', 'Interface theme': 'Tema dell\'interfaccia',
    'The theme has unsaved changes. Discard them?': 'Il tema ha modifiche non salvate. Scartarle?',
    'Frontier MRTE: theme editor': 'Frontier MRTE: editor dei temi',
    'Copy failed: {0}': 'Copia non riuscita: {0}',
})

TYPE_NAMES = {'rect': 'Rectangle', 'image': 'Picture', 'text': 'Text', 'list': 'List', 'video': 'Video', 'bar': 'Bar'}
LANG = 'en'


def resolve_lang(pref):
    if pref in ('it', 'en'):
        return pref
    from PySide6.QtCore import QLocale
    langs = QLocale.system().uiLanguages() or [QLocale.system().name()]
    return 'it' if str(langs[0]).lower().startswith('it') else 'en'


def tx(s, *a):
    """The Italian text if the interface is in Italian, else the English one; {0}, {1}... = a."""
    r = (LANG == 'it' and IT.get(s)) or s
    for i, v in enumerate(a):
        r = r.replace('{%d}' % i, str(v))
    return r


# ======================================================================
# Model: INI files like the ones read by fe_theme.cpp / fe_render.cpp
# ======================================================================

TYPES = ['rect', 'image', 'text', 'list', 'video', 'bar']

# known keys per type (order in the file)
KEYS = {
    'global': ['name', 'base', 'background', 'background_fit', 'background_color', 'font', 'size', 'font_width', 'font_hinting', 'color', 'shadow'],
    'common': ['type', 'rect', 'if', 'ifnot', 'layout'],
    'rect': ['color', 'gradient'],
    'image': ['src', 'fit', 'align', 'valign', 'transition', 'fps'],
    'text': ['text', 'font', 'size', 'font_width', 'color', 'align', 'valign', 'wrap', 'shadow', 'shadow_offset', 'scroll', 'scroll_speed', 'scroll_delay'],
    'list': ['font', 'size', 'font_width', 'row_height', 'padding', 'color', 'dir_color', 'tag_color', 'tag_dir', 'tag_up', 'sel_background', 'sel_color', 'sel_image', 'sel_scroll', 'scroll_speed', 'scroll_delay', 'scrollbar_width', 'scrollbar_color', 'scrollbar_knob', 'empty_text', 'shadow', 'shadow_offset'],
    'video': ['src', 'fit', 'align', 'valign', 'delay'],
    'bar': ['value', 'color', 'background'],
}

# how the properties panel groups the keys (order of the sections)
GROUPS = {
    'global': [['Theme', ['name', 'base']], ['Background', ['background', 'background_fit', 'background_color']], ['Text defaults', ['font', 'size', 'font_width', 'font_hinting', 'color', 'shadow']]],
    'rect': [['Fill', ['color', 'gradient']]],
    'image': [['Picture', ['src', 'fit', 'align', 'valign', 'transition', 'fps']]],
    'video': [['Video', ['src', 'fit', 'align', 'valign', 'delay']]],
    'bar': [['Bar', ['value', 'color', 'background']]],
    'text': [['Text', ['text', 'wrap', 'align', 'valign']], ['Font', ['font', 'size', 'font_width', 'color']], ['Effects', ['shadow', 'shadow_offset']], ['Scrolling', ['scroll', 'scroll_speed', 'scroll_delay']]],
    'list': [['Font', ['font', 'size', 'font_width', 'row_height', 'padding']], ['Colors', ['color', 'dir_color', 'tag_color', 'sel_background', 'sel_color', 'sel_image']], ['Tags and text', ['tag_dir', 'tag_up', 'empty_text']], ['Scrolling', ['sel_scroll', 'scroll_speed', 'scroll_delay', 'scrollbar_width', 'scrollbar_color', 'scrollbar_knob']], ['Effects', ['shadow', 'shadow_offset']]],
}

KEY_INFO = {
    'name': 'Theme name', 'base': 'Reference resolution, e.g. 1280x720', 'background': 'Background picture (theme file)',
    'background_fit': 'cover / contain / stretch', 'background_color': 'Background color', 'font': 'TTF font (theme file)',
    'size': 'Font height in base px', 'color': 'Color', 'shadow': 'Text shadow color', 'shadow_offset': 'Shadow offset (base px)',
    'type': 'Element type', 'rect': 'x, y, width, height', 'if': 'Visible only if the expanded text is not empty',
    'ifnot': 'Visible only if the expanded text is empty',
    'layout': 'media = only with the pictures, text = only with "Text layout" ON (descriptions in place of the pictures), empty = always',
    'gradient': 'Second color (vertical gradient)',
    'src': 'Theme file or ${media.snap}|${media.title}|img/none.png', 'fit': 'contain / cover / stretch',
    'align': 'left / center / right', 'valign': 'top / middle / bottom', 'transition': 'fade 250 = fade in ms',
    'fps': 'Frames per second (src with *)', 'text': 'Text with ${variables}', 'wrap': '1 = wraps',
    'scroll': 'horizontal / vertical: scrolls if it does not fit', 'scroll_speed': 'base px per second', 'scroll_delay': 'ms before scrolling',
    'row_height': 'Row height (base px)', 'padding': 'Inner margin (base px)', 'dir_color': 'Folder color', 'tag_color': 'Color of the tags on the right',
    'tag_dir': 'Folder tag', 'tag_up': 'Tag of ..', 'sel_background': 'Selection bar color', 'sel_color': 'Selected text color',
    'sel_image': 'Selection bar picture', 'sel_scroll': '1 = long selected name scrolls', 'scrollbar_width': 'Bar width (0 = none)',
    'scrollbar_color': 'Bar color', 'scrollbar_knob': 'Knob color', 'empty_text': 'Text if the folder is empty', 'delay': 'ms before the video starts',
    'value': 'Progress in percent, e.g. ${progress}', 'font_width': 'Font width', 'font_hinting': 'Font hinting',
}

CHOICES = {
    'type': TYPES, 'fit': ['contain', 'cover', 'stretch'], 'background_fit': ['cover', 'contain', 'stretch'],
    'align': ['left', 'center', 'right'], 'valign': ['top', 'middle', 'bottom'], 'wrap': ['0', '1'], 'sel_scroll': ['0', '1'],
    'scroll': ['', 'horizontal', 'vertical'], 'layout': ['', 'media', 'text'],
}

# 'background' is a picture in [theme] but a color in [bar]: handled in field()
COLOR_KEYS = {'color', 'gradient', 'background_color', 'shadow', 'dir_color', 'tag_color', 'sel_background', 'sel_color', 'scrollbar_color', 'scrollbar_knob'}
FILE_KEYS = {'background', 'sel_image', 'src'}
FONT_KEYS = {'font'}
VIDEO_RE = re.compile(r'\.(mp4|m4v|mov|mkv|webm|avi|mpg|mpeg|ogv)$', re.I)
IMAGE_RE = re.compile(r'\.(png|jpe?g|gif)$', re.I)
FONT_RE = re.compile(r'\.(ttf|otf)$', re.I)


def parse_ini(text):
    theme = {'global': {}, 'elements': []}
    section = ''
    for line in re.split(r'\r?\n', text):
        m = re.search(r'[ \t];', line)
        if m:
            line = line[:m.start()]
        line = line.strip()
        if not line or line[0] in ';#':
            continue
        if line[0] == '[':
            e = line.find(']')
            section = (line[1:e] if e > 0 else line[1:]).strip()
            if section.lower() != 'theme':
                theme['elements'].append({'name': section, 'props': {}})
            continue
        eq = line.find('=')
        if eq < 0:
            continue
        k, v = line[:eq].strip().lower(), line[eq + 1:].strip()
        if not section or section.lower() == 'theme':
            theme['global'][k] = v
        else:
            theme['elements'][-1]['props'][k] = v
    return theme


def ordered_keys(props, known):
    keys = [k for k in known if k in props]
    keys += [k for k in props if k not in keys]
    return keys


def serialize_ini(theme, header):
    out = []
    if header:
        out += ['; ' + l for l in header.split('\n')]
    out += ['', '[theme]']
    for k in ordered_keys(theme['global'], KEYS['global']):
        out.append(k + '=' + theme['global'][k])
    for el in theme['elements']:
        t = el['props'].get('type') or 'rect'
        out += ['', '[' + el['name'] + ']']
        for k in ordered_keys(el['props'], KEYS['common'] + KEYS.get(t, [])):
            if el['props'][k] != '' or k == 'text':
                out.append(k + '=' + el['props'][k])
    return '\n'.join(out) + '\n'


def js_int(s):
    """parseInt(s, 10) of JavaScript: the leading integer, None if there is none."""
    m = re.match(r'\s*([+-]?\d+)', s or '')
    return int(m.group(1)) if m else None


def num(s, default=0.0):
    """+s of JavaScript for the numbers of the theme ('' = 0); default when it is not a number."""
    s = (s or '').strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return default


def parse_base(s):
    m = re.search(r'(\d+)\s*[x,]\s*(\d+)', s or '')
    return (int(m.group(1)), int(m.group(2))) if m else (1280, 720)


def parse_rect(s):
    v = [js_int(x) for x in (s or '').split(',')]
    return [(v[i] if i < len(v) and v[i] is not None else 0) for i in range(4)]


def join_rect(r):
    return ','.join(str(int(round(x))) for x in r)


def parse_color(s, default=None):
    """'#RRGGBB' / '#RRGGBBAA' -> QColor; default when it is not a color."""
    m = re.match(r'^#?([0-9a-f]{6})([0-9a-f]{2})?$', (s or '').strip(), re.I)
    if not m:
        return default
    n = int(m.group(1), 16)
    a = int(m.group(2), 16) if m.group(2) else 255
    return QColor((n >> 16) & 255, (n >> 8) & 255, n & 255, a)


def expand(t, variables):
    return re.sub(r'\$\{([^}]*)\}', lambda m: variables.get(m.group(1), ''), t or '')


def norm_path(p):
    parts = []
    for x in (p or '').replace('\\', '/').split('/'):
        if x == '..':
            if parts:
                parts.pop()
        elif x and x != '.':
            parts.append(x)
    return '/'.join(parts)


VARIANTS = ['theme.ini', 'theme_43.ini', 'detail.ini', 'detail_43.ini', 'screensaver.ini', 'screensaver_43.ini', 'loading.ini', 'loading_43.ini']
SCREENS = ['theme', 'detail', 'screensaver', 'loading']
SCREEN_NAMES = {'theme': 'Game list', 'detail': 'Detail', 'screensaver': 'Screensaver', 'loading': 'Loading'}


def file_of(scr, f43):
    return scr + ('_43' if f43 else '') + '.ini'


def ini_header(text):
    """Leading comments of an .ini file."""
    head = []
    for l in re.split(r'\r?\n', text):
        if re.match(r'^\s*[;#]', l):
            head.append(re.sub(r'^\s*[;#]\s?', '', l))
        elif l.strip():
            break
        elif head:
            head.append('')
    return '\n'.join(head).strip()


def guess_variant(fname, loose=False):
    """A file name renamed by a browser ("Theme editor MiSTer.ini", "Theme 43.ini") -> the variant it most likely is.
    loose=True also maps a name with no hint to theme.ini."""
    base = re.sub(r'^.*[\\/]', '', fname).lower()
    if base in VARIANTS:
        return base
    if not base.endswith('.ini'):
        return ''
    n = re.sub(r'[\s\-.]+', '_', base[:-4])
    f43 = '43' in n
    scr = 'detail' if 'detail' in n else 'screensaver' if 'saver' in n else 'loading' if 'loading' in n else ''
    if not scr and not f43 and not loose:
        return ''
    return file_of(scr or 'theme', f43)


def header_for(headers, v):
    if headers.get(v):
        return headers[v]
    if v.endswith('_43.ini'):
        return '4:3 variant of the theme.'
    if v.startswith('detail'):
        return 'Detail screen of the theme.'
    if v.startswith('screensaver'):
        return 'Screensaver of the theme.'
    if v.startswith('loading'):
        return 'Loading screen of the theme (while a core loads the game).'
    return 'Theme for Frontier, the MiSTer frontend (made with the theme editor).'


NEW_THEME_INI = r'''[theme]
name=New theme
base=1280x720
background_color=#101820
size=24
color=#F0F0F0

[background]
type=rect
rect=0,0,1280,720
color=#1A2740
gradient=#080C14

[title]
type=text
rect=40,16,800,56
text=${title}
size=40
color=#FFC040

[list]
type=list
rect=40,96,600,560
size=24
row_height=37
padding=12
sel_background=#2F5FB3
sel_color=#FFFFFF
dir_color=#FFD878
tag_dir=>
tag_up=<
sel_scroll=1

[image]
type=image
rect=680,96,560,320
src=${media.snap}|${media.title}
fit=contain
transition=fade 250

[name]
type=text
rect=680,432,560,40
text=${game.title}
size=28
color=#FFC040

[description]
type=text
rect=680,480,560,176
text=${game.desc}
size=18
wrap=1
valign=top
scroll=vertical
'''

DEFAULT_SAMPLE = '''title=Arcade
folder=Arcade
pos=14/2206
count=2206
system=arcade
system.name=Arcade
progress=63
loading.file=1942.zip
game.name=1942 (Revision B)
game.title=1942 (Revision B)
game.file=1942 (Revision B).mra
game.date=
game.desc=1942 is a vertical scrolling shooter set in the Pacific during World War II: the player flies the "Super Ace" and must shoot down waves of enemy planes avoiding their bullets.
game.year=1984
game.released=01/01/1984
game.developer=Capcom
game.publisher=Capcom
game.genre=Shooter / Flying Vertical
game.players=2
game.rating=0.80
game.stars=★★★★☆
game.favorite=1
game.cpu=Zilog Z80 @ 4 MHz
game.memory=64 KB RAM
game.graphics=256 x 224, 256 colours
game.sound=YM2203 + AY-3-8910
game.media=Cartridge
game.units=1 million
message=
jump=
version=1942 (Revision B)
versions.status=
media.system=
media.snap=@snap
media.box=@box
media.title=@title
media.marquee=@marquee
media.fanart=
media.video=@video'''

SAMPLE_LIST = [
    ('..', 1), ('alternatives', 1), ('Cave CV1000', 1), ('ST-V', 1), ('005', 0), ('1 on 1 Government (Japan)', 0),
    ('18 Challenge Pro Golf (DECO)', 0), ('1941 Counter Attack (World 900227)', 0), ('1942 (Revision B)', 0),
    ('1943 Kai Midway Kaisen (Japan)', 0), ('1943 The Battle of Midway (Euro)', 0), ('1944 The Loop Master (Europe 000620)', 0),
    ('19XX The War Against Destiny (Europe 960104)', 0), ('4D Warriors (315-5162)', 0), ('Aero Fighters', 0), ('After Burner II', 0),
    ('Alien Syndrome', 0), ('Altered Beast', 0), ('Arkanoid', 0), ('Bomb Jack', 0), ('Bubble Bobble', 0), ('Commando', 0),
]
SAMPLE_SEL = 8

NEW_PROPS = {
    'rect': {'color': '#1C2A44E0'},
    'image': {'src': '${media.snap}|${media.title}', 'fit': 'contain', 'transition': 'fade 250'},
    'text': {'text': '${game.title}', 'size': '28', 'color': '#FFFFFF'},
    'list': {'size': '24', 'row_height': '36', 'padding': '10', 'sel_background': '#2F5FB3', 'sel_color': '#FFFFFF', 'tag_dir': '>', 'tag_up': '<', 'sel_scroll': '1'},
    'video': {'src': '${media.video}', 'fit': 'contain', 'delay': '1500'},
    'bar': {'value': '${progress}', 'color': '#FFC040', 'background': '#1C2A44'},
}
DEFAULT_SIZE = {'rect': (200, 120), 'image': (240, 160), 'text': (280, 48), 'list': (320, 320), 'video': (320, 200), 'bar': (320, 16)}


def parse_sample(text):
    variables = {}
    for line in text.split('\n'):
        eq = line.find('=')
        if eq > 0:
            variables[line[:eq].strip()] = line[eq + 1:]
    return variables


def make_variant(src_theme, how, scr):
    """A missing variant made from another one: 'scale' = 4:3 from the 16:9 one, 'copy' = detail from the game list,
    screensaver from the detail (without the versions). Returns (theme, header)."""
    t = copy.deepcopy(src_theme)
    if how == 'scale':
        # base 4:3 (960x720): x and widths scaled, the texts keep their size
        bw, bh = parse_base(t['global'].get('base'))
        nw = int(round(bh * 4 / 3))
        k = nw / bw
        t['global']['base'] = '%dx%d' % (nw, bh)
        for el in t['elements']:
            r = parse_rect(el['props'].get('rect'))
            el['props']['rect'] = join_rect([round(r[0] * k), r[1], round(r[2] * k), r[3]])
        return t, 'Variant for 4:3 screens (CRT, 640x240...): used when the screen is narrower than about 3:2.'
    if scr == 'detail':
        return t, 'Detail screen (X on the gamepad). Variables: see the detail.ini of the simple theme.'
    t['elements'] = [e for e in t['elements'] if not re.match(r'^versions(_title|_pos|_back)?$', e['name'])]
    return t, 'Screensaver: random games after some time without keys, Start plays the game shown. Variables: those of detail.ini and ${system.name}.'


# ======================================================================
# Drawing (same rules as fe_render.cpp, as far as possible)
# ======================================================================

def fit_rect(iw, ih, x, y, w, h, fit):
    """(sx, sy, sw, sh, dw, dh) of a picture iw x ih drawn in the rectangle with fit = contain / cover / stretch."""
    if fit == 'stretch':
        return 0, 0, iw, ih, w, h
    if fit == 'cover':
        sw, sh, sx, sy = iw, ih, 0, 0
        if iw * h > ih * w:
            sw = w * ih / h
            sx = (iw - sw) / 2
        else:
            sh = h * iw / w if w else ih
            sy = (ih - sh) / 2
        return sx, sy, sw, sh, w, h
    dw, dh = w, h
    if iw * h > ih * w:
        dh = ih * w / iw
    else:
        dw = iw * h / ih if ih else w
    return 0, 0, iw, ih, dw, dh


def align_num(s, default):
    s = (s or default or '').lower()
    return 1 if s in ('center', 'middle') else 2 if s in ('right', 'bottom') else 0


def resolve_src(src, variables):
    for alt in (src or '').split('|'):
        alt = alt.strip()
        if '${' in alt:
            v = expand(alt, variables)
            if v:
                return v
        elif alt:
            return alt
    return ''


def visible(p, variables, text_layout):
    # "Text layout" of Frontier's settings: elements with layout=text instead of layout=media
    if (p.get('layout') or '').lower() == ('media' if text_layout else 'text'):
        return False
    return ((not p.get('if') or expand(p['if'], variables) != '') and
            (not p.get('ifnot') or expand(p['ifnot'], variables) == ''))


_placeholders = {}


def placeholder(kind):
    if kind in _placeholders:
        return _placeholders[kind]
    w, h = {'snap': (320, 240), 'title': (320, 240), 'box': (300, 420), 'marquee': (512, 128), 'fanart': (640, 360), 'video': (320, 240)}.get(kind, (320, 240))
    hue = {'snap': 210, 'title': 160, 'box': 20, 'marquee': 300, 'fanart': 260}.get(kind, 200)   # video: blue, as in the web editor
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    g = QPainter(img)
    g.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0, QColor.fromHslF((hue % 360) / 360, 0.55, 0.38))
    grad.setColorAt(1, QColor.fromHslF(((hue + 40) % 360) / 360, 0.55, 0.22))
    g.fillRect(0, 0, w, h, QBrush(grad))
    g.setPen(QPen(QColor(255, 255, 255, 31), 1))
    for x in range(0, w, 16):
        g.drawLine(QPointF(x + 0.5, 0), QPointF(x + 0.5, h))
    f = QFont()
    f.setPixelSize(28)
    f.setBold(True)
    g.setFont(f)
    g.setPen(QColor(255, 255, 255, 217))
    g.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, '▶ VIDEO' if kind == 'video' else kind.upper())
    g.end()
    _placeholders[kind] = img
    return img


class Media(QObject):
    """Pictures, GIF frames, fonts and first frames of the videos of the open theme, loaded once."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.images = {}    # absolute path -> QImage (None = cannot be read)
        self.gifs = {}      # absolute path -> ([(QImage, ms)], total ms) for animated GIFs
        self.fonts = {}     # absolute path -> (family, weight, style) or None
        self.videos = {}    # absolute path -> {'still': QImage|None, 'dur': s, 'failed': bool}
        self._vqueue = []
        self._player = None

    def clear(self):
        self.images.clear()
        self.gifs.clear()
        self.videos.clear()
        self._vqueue.clear()

    def image(self, path):
        if path not in self.images:
            img = QImage(path)
            self.images[path] = None if img.isNull() else img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            if path.lower().endswith('.gif'):
                r = QImageReader(path)
                if r.supportsAnimation() and r.imageCount() != 1:
                    frames, total = [], 0
                    while r.canRead() and len(frames) < 400:
                        fr = r.read()
                        if fr.isNull():
                            break
                        dur = max(20, r.nextImageDelay() or 100)
                        frames.append((fr.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied), dur))
                        total += dur
                    if len(frames) > 1:
                        self.gifs[path] = (frames, total)
        return self.images[path]

    def frame(self, path, img, animate, now_ms):
        """The frame of a GIF for this moment (the first one when the animation is off). Returns (image, animated)."""
        g = self.gifs.get(path)
        if not g:
            return img, False
        frames, total = g
        if not animate:
            return frames[0][0], False
        t = now_ms % total
        for fr, dur in frames:
            if t < dur:
                return fr, True
            t -= dur
        return frames[0][0], True

    def font(self, path):
        """(family, weight, style) of a TTF/OTF file, registered with Qt; None if it cannot be read."""
        if path not in self.fonts:
            info = None
            if os.path.isfile(path):
                fid = QFontDatabase.addApplicationFont(path)
                fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
                if fams:
                    raw = QRawFont(path, 20)
                    fam = raw.familyName() if raw.isValid() and raw.familyName() in fams else fams[0]
                    info = (fam, raw.weight() if raw.isValid() else 400, raw.style() if raw.isValid() else QFont.Style.StyleNormal)
            self.fonts[path] = info
        return self.fonts[path]

    def qfont(self, path, px):
        f = QFont()
        info = self.font(path) if path else None
        if info:
            f = QFont(info[0])
            try:
                f.setWeight(QFont.Weight(info[1]))
            except (ValueError, TypeError):
                f.setBold(info[1] >= 600)
            f.setStyle(info[2])
        else:
            f.setStyleHint(QFont.StyleHint.SansSerif)
        f.setPixelSize(max(1, int(round(px))))
        return f

    # first frame of a video (the preview does not play videos), made with QtMultimedia one video at a time
    def video(self, path):
        rec = self.videos.get(path)
        if rec is None:
            rec = self.videos[path] = {'still': None, 'dur': 0, 'failed': QMediaPlayer is None}
            if QMediaPlayer is not None:
                self._vqueue.append(path)
                QTimer.singleShot(0, self._next_video)
        return rec

    def _next_video(self):
        if self._player is not None or not self._vqueue:
            return
        path = self._vqueue.pop(0)
        rec = self.videos.get(path)
        if rec is None:
            QTimer.singleShot(0, self._next_video)
            return
        player, sink = QMediaPlayer(), QVideoSink()
        self._player = (player, sink, path)
        player.setVideoSink(sink)

        def done(failed):
            if self._player is None or self._player[2] != path:
                return
            rec['failed'] = failed and rec['still'] is None
            self._player = None
            player.stop()
            player.deleteLater()
            sink.deleteLater()
            self.changed.emit()
            QTimer.singleShot(0, self._next_video)

        def frame(fr):
            if rec['still'] is not None or not fr.isValid():
                return
            img = fr.toImage()
            if img.isNull():
                return
            rec['still'] = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            rec['dur'] = player.duration() / 1000 if player.duration() > 0 else 0
            done(False)

        sink.videoFrameChanged.connect(frame)
        player.errorOccurred.connect(lambda *a: done(True))
        player.setSource(QUrl.fromLocalFile(path))
        player.play()
        QTimer.singleShot(8000, lambda: done(True))


class ThemeFiles:
    """The files of the theme: path relative to the theme folder -> absolute path (on disk in the folder, or
    picked elsewhere and not saved yet). Paths outside the folder (e.g. ../simple/fonts/) are read from the disk."""

    def __init__(self, folder=None, files=None):
        self.folder = folder
        self.files = dict(files or {})

    @staticmethod
    def scan(folder):
        files = {}
        for root, dirs, names in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
            for n in sorted(names):
                full = os.path.join(root, n)
                files[os.path.relpath(full, folder).replace(os.sep, '/')] = full
        return files

    def abs(self, path):
        rel = norm_path(path)
        if rel in self.files:
            return self.files[rel]
        if self.folder and path:
            p = os.path.normpath(os.path.join(self.folder, path.replace('/', os.sep)))
            if os.path.isfile(p):
                return p
        return None

    def has(self, path):
        return norm_path(path) in self.files

    def glob(self, pattern):
        rx = re.escape(norm_path(pattern)).replace(r'\*', '[^/]*').replace(r'\?', '[^/]')
        rx = re.compile('^' + rx + '$')
        return sorted(k for k in self.files if rx.match(k))

    def outside(self):
        """Files that are not in the theme folder yet (picked elsewhere, rotated copies...)."""
        out = []
        for rel, full in self.files.items():
            if not self.folder or os.path.normcase(os.path.normpath(full)) != os.path.normcase(os.path.normpath(os.path.join(self.folder, rel))):
                out.append(rel)
        return out


class SceneDrawer:
    """Draws a theme variant with a QPainter in base units, as fe_render.cpp does on the MiSTer."""

    def __init__(self, media):
        self.media = media
        self.animating = False

    def draw(self, p, theme, variables, files, text_layout=False, animate=True, now_ms=0, rot=None):
        """rot(el) -> degrees while a picture is being rotated by hand, else None."""
        self.animating = False
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        g = theme['global']
        bw, bh = parse_base(g.get('base'))
        p.fillRect(QRectF(0, 0, bw, bh), parse_color(g.get('background_color'), QColor(0, 0, 0)))
        if g.get('background'):
            path = files.abs(g['background'])
            img = self.media.image(path) if path else None
            if img is not None:
                img = self._frame(path, img, animate, now_ms)
                sx, sy, sw, sh, dw, dh = fit_rect(img.width(), img.height(), 0, 0, bw, bh, (g.get('background_fit') or 'cover').lower())
                p.drawImage(QRectF((bw - dw) / 2, (bh - dh) / 2, dw, dh), img, QRectF(sx, sy, sw, sh))
        for el in theme['elements']:
            self.element(p, theme, el, variables, files, text_layout, animate, now_ms, rot(el) if rot else None)

    def _frame(self, path, img, animate, now_ms):
        fr, anim = self.media.frame(path, img, animate, now_ms)
        if anim:
            self.animating = True
        return fr

    def element(self, p, theme, el, variables, files, text_layout, animate, now_ms, ang):
        if el.get('hid'):   # hidden in the editor only (eye of the layers panel)
            return
        pr, g = el['props'], theme['global']
        t = (pr.get('type') or 'rect').lower()
        r = parse_rect(pr.get('rect'))
        if not visible(pr, variables, text_layout):
            return
        def_color = parse_color(g.get('color'), QColor(240, 240, 240))
        shadow = parse_color(pr.get('shadow') or g.get('shadow'), None)
        sd = max(1.0, num(pr.get('shadow_offset') or '2', 2))
        p.save()
        if ang:   # picture being rotated by hand: shown turned around its center
            cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
            p.translate(cx, cy)
            p.rotate(ang)
            p.translate(-cx, -cy)
        rect = QRectF(r[0], r[1], r[2], r[3])
        if t == 'rect':
            c1 = parse_color(pr.get('color'), QColor(0, 0, 0))
            if pr.get('gradient'):
                gr = QLinearGradient(0, r[1], 0, r[1] + r[3])
                gr.setColorAt(0, c1)
                gr.setColorAt(1, parse_color(pr['gradient'], c1))
                p.fillRect(rect, QBrush(gr))
            else:
                p.fillRect(rect, c1)
        elif t == 'bar':
            # progress bar (loading.ini): value= percent of the width in color
            pct = max(0, min(100, js_int(expand(pr.get('value', ''), variables)) or 0))
            if pr.get('background'):
                p.fillRect(rect, parse_color(pr['background'], QColor(0, 0, 0, 0)))
            p.fillRect(QRectF(r[0], r[1], r[2] * pct / 100, r[3]), parse_color(pr.get('color'), QColor(255, 192, 64)))
        elif t in ('image', 'video'):
            self._picture(p, pr, r, variables, files, animate, now_ms)
        elif t == 'text':
            self._text(p, pr, g, r, variables, files, def_color, shadow, sd)
        elif t == 'list':
            self._list(p, pr, g, r, files, def_color, shadow, sd, animate, now_ms)
        p.restore()

    def _picture(self, p, pr, r, variables, files, animate, now_ms):
        src = resolve_src(pr.get('src'), variables)
        img, path, missing = None, '', False
        if src.startswith('@'):
            img = placeholder(src[1:])
        elif src:
            rel = (files.glob(src) or [''])[0] if '*' in src else src
            path = files.abs(rel) if rel else None
            if path and VIDEO_RE.search(path):   # a video of the theme: its first frame stands for it
                rec = self.media.video(path)
                img = rec['still']
                missing = rec['failed'] and img is None
            elif path:
                img = self.media.image(path)
                if img is not None:
                    img = self._frame(path, img, animate, now_ms)
                missing = img is None
            else:
                missing = True
        if img is not None:
            self.draw_fit(p, img, r, pr, 'center')
        elif missing:
            pen = QPen(QColor('#e5484d'), 1)
            pen.setDashPattern([4, 4])
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(r[0] + .5, r[1] + .5, r[2], r[3]))

    @staticmethod
    def draw_fit(p, img, r, pr, def_align):
        sx, sy, sw, sh, dw, dh = fit_rect(img.width(), img.height(), r[0], r[1], r[2], r[3], (pr.get('fit') or 'contain').lower())
        ax, ay = align_num(pr.get('align'), def_align), align_num(pr.get('valign'), 'middle')
        p.drawImage(QRectF(r[0] + (r[2] - dw) * ax / 2, r[1] + (r[3] - dh) * ay / 2, dw, dh), img, QRectF(sx, sy, sw, sh))

    def _font(self, pr, g, files):
        px = num(pr.get('size') or g.get('size') or '24', 24) or 24
        spec = pr.get('font') or g.get('font') or ''
        f = self.media.qfont(files.abs(spec) if spec else None, px)
        fm = QFontMetricsF(f)
        return f, fm, fm.ascent(), fm.ascent() + fm.descent()

    @staticmethod
    def ellipsize(fm, s, maxw):
        if fm.horizontalAdvance(s) <= maxw:
            return s
        t = s
        while t and fm.horizontalAdvance(t + '...') > maxw:
            t = t[:-1].rstrip()
        return t + '...' if t else ''

    @staticmethod
    def draw_string(p, s, x, y, color, shadow, sd):
        if shadow is not None:
            p.setPen(shadow)
            p.drawText(QPointF(x + sd, y + sd), s)
        p.setPen(color)
        p.drawText(QPointF(x, y), s)

    def _text(self, p, pr, g, r, variables, files, def_color, shadow, sd):
        f, fm, asc, lh = self._font(pr, g, files)
        p.setFont(f)
        txt = expand(pr.get('text'), variables)
        color = parse_color(pr.get('color'), def_color)
        if num(pr.get('wrap')):
            lines = []
            for para in txt.split('\n'):
                line = ''
                for w in para.split(' '):
                    test = line + ' ' + w if line else w
                    if line and fm.horizontalAdvance(test) > r[2]:
                        lines.append(line)
                        line = w
                    else:
                        line = test
                lines.append(line)
        else:
            lines = [txt]
        maxl = max(1, int(r[3] // lh)) if lh > 0 else 1
        if len(lines) > maxl:
            lines = lines[:maxl]
            lines[-1] += '...'
        total = len(lines) * lh
        y = r[1]
        va, ha = align_num(pr.get('valign'), 'middle'), align_num(pr.get('align'), 'left')
        if va == 1:
            y += (r[3] - total) / 2
        elif va == 2:
            y += r[3] - total
        p.setClipRect(QRectF(r[0], r[1], r[2], r[3]), Qt.ClipOperation.IntersectClip)
        for l in lines:
            s = self.ellipsize(fm, l, r[2])
            w = fm.horizontalAdvance(s)
            self.draw_string(p, s, r[0] + (r[2] - w) * ha / 2, y + asc, color, shadow, sd)
            y += lh

    def _list(self, p, pr, g, r, files, def_color, shadow, sd, animate, now_ms):
        f, fm, asc, lh = self._font(pr, g, files)
        p.setFont(f)
        row_h = max(lh + 1, num(pr.get('row_height') or '0'))
        pad = num(pr.get('padding', '8'), 8)
        rows = max(1, int(r[3] // row_h))
        sbw = num(pr.get('scrollbar_width', '6'), 6)
        count = len(SAMPLE_LIST)
        sb = sbw + pad if count > rows and sbw else 0
        row_w = r[2] - sb
        top = max(0, min(SAMPLE_SEL - rows // 2, count - rows))
        color = parse_color(pr.get('color'), def_color)
        sel_img, sel_path = None, None
        if pr.get('sel_image'):
            sel_path = files.abs(pr['sel_image'])
            sel_img = self.media.image(sel_path) if sel_path else None
        white = QColor(255, 255, 255)
        for i in range(rows):
            if top + i >= count:
                break
            label, is_dir = SAMPLE_LIST[top + i]
            y = r[1] + i * row_h
            is_sel = top + i == SAMPLE_SEL
            if is_sel:
                if sel_img is not None:
                    p.drawImage(QRectF(r[0], y, row_w, row_h), self._frame(sel_path, sel_img, animate, now_ms))
                else:
                    p.fillRect(QRectF(r[0], y, row_w, row_h), parse_color(pr.get('sel_background'), QColor(47, 95, 179)))
            ty = y + (row_h - lh) / 2 + asc
            right = r[0] + row_w - pad
            tag = (pr.get('tag_up', '') if label == '..' else pr.get('tag_dir', '')) if is_dir else ''
            if tag:
                tw = fm.horizontalAdvance(tag)
                self.draw_string(p, tag, right - tw, ty, parse_color(pr.get('sel_color'), white) if is_sel else parse_color(pr.get('tag_color'), color), shadow, sd)
                right -= tw + lh
            c = parse_color(pr.get('sel_color'), white) if is_sel else parse_color(pr.get('dir_color'), color) if is_dir else color
            self.draw_string(p, self.ellipsize(fm, label, right - r[0] - pad), r[0] + pad, ty, c, shadow, sd)
        if sb:
            sx, sh = r[0] + r[2] - sbw, rows * row_h
            knob = max(sbw * 2, sh * rows / count)
            pos = (sh - knob) * top / max(1, count - rows)
            p.fillRect(QRectF(sx, r[1], sbw, sh), parse_color(pr.get('scrollbar_color'), QColor(58, 74, 102)))
            p.fillRect(QRectF(sx, r[1] + pos, sbw, knob), parse_color(pr.get('scrollbar_knob'), QColor(140, 160, 192)))


def render_image(theme, variables, files, media, scale=1.0, text_layout=False):
    """The variant drawn into a QImage (base size x scale), as the preview without the editor overlays."""
    bw, bh = parse_base(theme['global'].get('base'))
    img = QImage(max(1, round(bw * scale)), max(1, round(bh * scale)), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0))
    p = QPainter(img)
    p.scale(scale, scale)
    SceneDrawer(media).draw(p, theme, variables, files, text_layout=text_layout, animate=False)
    p.end()
    return img


# ======================================================================
# Icons (the same drawings as the web editor)
# ======================================================================

ICONS = {
    'select': '<path d="M4 2l8 6.5-3.6.6 2.2 4.4-1.6.8-2.2-4.4L4 12.5z" fill="currentColor"/>',
    'rect': '<rect x="2.5" y="3.5" width="11" height="9" rx="1"/>',
    'image': '<rect x="2" y="3" width="12" height="10" rx="1"/><circle cx="5.5" cy="6.5" r="1.2"/><path d="M2.5 12l3.5-3.5 2.5 2.5 2-2 3 3"/>',
    'text': '<path d="M3 4.5V3h10v1.5M8 3v10M6 13h4"/>',
    'list': '<path d="M2.5 3.5h11M2.5 12.5h11"/><rect x="2.5" y="6" width="11" height="4" rx="1" fill="currentColor" stroke="none" opacity=".55"/>',
    'video': '<rect x="2" y="3.5" width="12" height="9" rx="1"/><path d="M6.8 6v4l3.4-2z" fill="currentColor"/>',
    'bar': '<rect x="2" y="6" width="12" height="4" rx="1"/><rect x="2" y="6" width="7" height="4" rx="1" fill="currentColor"/>',
    'eye': '<path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"/><circle cx="8" cy="8" r="2"/>',
    'eyeoff': '<path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z" opacity=".45"/><path d="M3 13L13 3"/>',
    'up': '<path d="M4 10l4-4 4 4"/>',
    'down': '<path d="M4 6l4 4 4-4"/>',
    'dup': '<rect x="5.5" y="5.5" width="8" height="8" rx="1"/><path d="M10.5 3.5v-1h-8v8h1"/>',
    'trash': '<path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8.5h5.8l.6-8.5M7 7v4M9 7v4"/>',
    'plus': '<path d="M8 3v10M3 8h10"/>',
    'chev': '<path d="M6 4l4 4-4 4"/>',
    'chevdown': '<path d="M4 6l4 4 4-4"/>',
    'undo': '<path d="M5 3.5L2.5 6 5 8.5M2.5 6H9a3.5 3.5 0 010 7H6"/>',
    'al': '<path d="M2.5 2v12"/><rect x="4.5" y="4" width="8" height="3"/><rect x="4.5" y="9" width="5" height="3"/>',
    'ac': '<path d="M8 2v12"/><rect x="3.5" y="4" width="9" height="3"/><rect x="5" y="9" width="6" height="3"/>',
    'folder': '<path d="M2 4.5h4l1.5 1.5H14v6.5H2z"/>',
    'save': '<path d="M3 3h8l2 2v8H3z"/><path d="M5.5 3v3h5V3M5.5 13v-4h5v4"/>',
    'lock': '<rect x="4" y="7" width="8" height="6" rx="1"/><path d="M5.5 7V5a2.5 2.5 0 015 0v2"/>',
}

ROTATE_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke-linecap="round" stroke-linejoin="round">'
              '<g stroke="#fff" stroke-width="4.2"><path d="M18.5 8A8 8 0 1 0 20 13"/><path d="M19 3v5.5h-5.5"/></g>'
              '<g stroke="#000" stroke-width="2"><path d="M18.5 8A8 8 0 1 0 20 13"/><path d="M19 3v5.5h-5.5"/></g></svg>')


def svg_pixmap(svg, w, h, dpr=2.0):
    pm = QPixmap(int(w * dpr), int(h * dpr))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(svg.encode())).render(p)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon_pixmap(name, color, size=16, transform=None):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="%s" '
           'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">%s</svg>') % (color, ICONS[name].replace('currentColor', color))
    pm = svg_pixmap(svg, size, size)
    if transform:
        dpr = pm.devicePixelRatio()
        pm = pm.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
    return pm


def make_icon(name, color, on_color=None, size=16, transform=None):
    ic = QIcon()
    ic.addPixmap(icon_pixmap(name, color, size, transform), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(icon_pixmap(name, on_color or color, size, transform), QIcon.Mode.Normal, QIcon.State.On)
    ic.addPixmap(icon_pixmap(name, on_color or color, size, transform), QIcon.Mode.Selected, QIcon.State.Off)
    return ic


# ======================================================================
# Interface themes: dark gray (default), medium gray, light
# ======================================================================

UI_THEMES = {
    'dark': dict(app='#262626', panel='#323232', panel_hd='#2a2a2a', ctrl='#404040', ctrl_h='#4b4b4b', input='#262626',
                 line='#1b1b1b', line2='#454545', text='#d6d6d6', dim='#8f8f8f', stage='#1d1d1d', menu='#2e2e2e',
                 accent='#2f86eb', accent_h='#4a9bf5', accent_t='#ffffff', sel='#1e5a9e', sel_t='#ffffff', danger='#e5484d'),
    'medium': dict(app='#3b3b3b', panel='#535353', panel_hd='#474747', ctrl='#666666', ctrl_h='#737373', input='#444444',
                   line='#2e2e2e', line2='#6a6a6a', text='#efefef', dim='#c0c0c0', stage='#424242', menu='#4d4d4d',
                   accent='#2f86eb', accent_h='#4a9bf5', accent_t='#ffffff', sel='#2d6fb8', sel_t='#ffffff', danger='#ff6b70'),
    'light': dict(app='#c8c8c8', panel='#e4e4e4', panel_hd='#d4d4d4', ctrl='#f5f5f5', ctrl_h='#ffffff', input='#ffffff',
                  line='#a6a6a6', line2='#c3c3c3', text='#262626', dim='#5c5c5c', stage='#b3b3b3', menu='#f1f1f1',
                  accent='#1473e6', accent_h='#2b86f5', accent_t='#ffffff', sel='#b9d5f8', sel_t='#0a2a4f', danger='#d7373f'),
}
UI_ORDER = ['light', 'medium', 'dark']

QSS = '''
QMainWindow, QDialog {{ background: {app}; }}
#menubar {{ background: {panel_hd}; border-bottom: 1px solid {line}; }}
#menubtn {{ padding: 4px 10px; }}
#menubtn::menu-indicator {{ image: none; width: 0; }}
#menubtn:hover, #menubtn:pressed, #menubtn:open {{ background: {ctrl}; }}
QMenu {{ background: {menu}; border: 1px solid {line}; padding: 4px; }}
QMenu::item {{ padding: 5px 26px 5px 24px; border-radius: 4px; }}
QMenu::item:selected {{ background: {accent}; color: {accent_t}; }}
QMenu::item:disabled {{ color: {dim}; }}
QMenu::separator {{ height: 1px; background: {line2}; margin: 4px 6px; }}
QMenu::section {{ padding: 6px 8px 3px; font-size: 10px; font-weight: bold; color: {dim}; }}
#optbar {{ background: {panel}; border-bottom: 1px solid {line}; }}
#tools {{ background: {panel}; border-right: 1px solid {line}; }}
#right {{ background: {panel}; border-left: 1px solid {line}; }}
#stage, #stage > QWidget > QWidget {{ background: {stage}; border: none; }}
#welcome {{ background: {stage}; }}
#welcome QLabel {{ background: transparent; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 3px; color: {text}; }}
QToolButton:hover {{ background: {ctrl}; }}
QToolButton:checked {{ background: {accent}; color: {accent_t}; }}
QToolButton:disabled {{ color: {dim}; }}
QToolButton[tg="1"] {{ border: 1px solid {line2}; color: {dim}; padding: 3px 9px; }}
QToolButton[tg="1"]:hover {{ color: {text}; }}
QToolButton[tg="1"]:checked {{ background: {accent}; border-color: {accent}; color: {accent_t}; }}
QToolButton[seg="1"] {{ border: 1px solid {line2}; color: {dim}; padding: 3px 11px; border-radius: 0; }}
QToolButton[seg="1"]:checked {{ background: {accent}; border-color: {accent}; color: {accent_t}; }}
QToolButton[dd="1"] {{ border: 1px solid {line2}; padding: 3px 9px; font-weight: bold; }}
QToolButton[dd="1"]::menu-indicator {{ image: none; }}
QToolButton[tool="1"] {{ padding: 6px; border-radius: 5px; }}
QToolButton[vbtn="1"] {{ border: 1px solid {line2}; background: {ctrl}; font-family: monospace; font-size: 11px; padding: 2px 4px; }}
QToolButton[vbtn="1"]:hover {{ background: {accent}; color: {accent_t}; }}
QToolButton[sec="1"] {{ background: {panel_hd}; border: none; border-bottom: 1px solid {line2}; border-radius: 0; padding: 6px 8px; font-weight: bold; text-align: left; }}
QToolButton[sw] {{ border: 2px solid {line2}; border-radius: 8px; padding: 0; min-width: 12px; max-width: 12px; min-height: 12px; max-height: 12px; }}
QToolButton[sw="light"] {{ background: #e4e4e4; }}
QToolButton[sw="medium"] {{ background: #535353; }}
QToolButton[sw="dark"] {{ background: #323232; }}
QToolButton[sw]:checked {{ border-color: {accent}; }}
QPushButton {{ background: {ctrl}; border: 1px solid {line2}; border-radius: 4px; padding: 4px 10px; color: {text}; }}
QPushButton:hover {{ background: {ctrl_h}; }}
QPushButton:disabled {{ color: {dim}; }}
QPushButton[primary="1"] {{ background: {accent}; border-color: {accent}; color: {accent_t}; }}
QPushButton[primary="1"]:hover {{ background: {accent_h}; }}
QPushButton[primary="1"]:disabled {{ background: {ctrl}; border-color: {line2}; color: {dim}; }}
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {{ background: {input}; border: 1px solid {line2}; border-radius: 4px; padding: 2px 5px; color: {text}; selection-background-color: {accent}; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {accent}; }}
QLineEdit:disabled, QSpinBox:disabled {{ color: {dim}; }}
QComboBox QAbstractItemView {{ background: {menu}; border: 1px solid {line}; selection-background-color: {accent}; selection-color: {accent_t}; }}
QTabWidget::pane {{ border: none; background: {panel}; }}
QTabBar {{ background: {panel_hd}; }}
QTabBar::tab {{ background: {panel_hd}; color: {dim}; padding: 7px 14px; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {text}; background: {panel}; border-bottom-color: {accent}; }}
QTabBar::tab:hover {{ color: {text}; }}
QTreeWidget, QListWidget {{ background: {panel}; border: none; outline: none; color: {text}; }}
QTreeWidget::item {{ height: 28px; border-bottom: 1px solid {line2}; }}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: {ctrl}; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: {sel}; color: {sel_t}; }}
#pfoot {{ background: {panel_hd}; border-top: 1px solid {line}; }}
#props, #propsScroll {{ background: {panel}; border: none; }}
#keyinfo {{ background: {panel_hd}; color: {dim}; border-top: 1px solid {line}; padding: 6px 10px; }}
QLabel[dim="1"] {{ color: {dim}; }}
QLabel[note="1"] {{ color: {dim}; font-size: 11px; }}
QLabel[pill="1"] {{ color: {dim}; border: 1px solid {line2}; border-radius: 9px; padding: 1px 8px; font-size: 11px; }}
QLabel[stack="1"] {{ font-weight: bold; }}
QStatusBar {{ background: {panel_hd}; color: {dim}; border-top: 1px solid {line}; }}
QStatusBar QLabel {{ color: {dim}; padding: 0 6px; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: {app}; border-top: 1px solid {line}; border-bottom: 1px solid {line}; }}
QSplitter::handle:hover {{ background: {accent}; }}
QFrame[sep="1"] {{ background: {line2}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle {{ background: {line2}; border-radius: 4px; min-height: 24px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QToolTip {{ background: {menu}; color: {text}; border: 1px solid {line}; padding: 4px; }}
QTextBrowser {{ background: {panel}; border: none; color: {text}; }}
'''


def apply_ui_theme(app, name):
    c = UI_THEMES.get(name, UI_THEMES['dark'])
    pal = QPalette()
    for role, key in ((QPalette.ColorRole.Window, 'panel'), (QPalette.ColorRole.WindowText, 'text'), (QPalette.ColorRole.Base, 'input'),
                      (QPalette.ColorRole.AlternateBase, 'panel_hd'), (QPalette.ColorRole.Text, 'text'), (QPalette.ColorRole.Button, 'ctrl'),
                      (QPalette.ColorRole.ButtonText, 'text'), (QPalette.ColorRole.Highlight, 'accent'),
                      (QPalette.ColorRole.HighlightedText, 'accent_t'), (QPalette.ColorRole.ToolTipBase, 'menu'),
                      (QPalette.ColorRole.ToolTipText, 'text'), (QPalette.ColorRole.PlaceholderText, 'dim'),
                      (QPalette.ColorRole.Mid, 'line2'), (QPalette.ColorRole.Dark, 'line'), (QPalette.ColorRole.Link, 'accent')):
        pal.setColor(role, QColor(c[key]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(c['dim']))
    app.setPalette(pal)
    app.setStyleSheet(QSS.format(**c))
    return c


# ======================================================================
# Canvas: the preview, with selection, handles, drawing of new elements, rotation
# ======================================================================

def handles(r):
    x, y, w, h = r
    return [(x, y), (x + w / 2, y), (x + w, y), (x + w, y + h / 2), (x + w, y + h), (x + w / 2, y + h), (x, y + h), (x, y + h / 2)]


HANDLE_DIR = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]
HANDLE_CURSOR = [Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeBDiagCursor, Qt.CursorShape.SizeHorCursor,
                 Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeBDiagCursor, Qt.CursorShape.SizeHorCursor]


class Canvas(QWidget):
    def __init__(self, ed):
        super().__init__()
        self.ed = ed
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.drawer = SceneDrawer(ed.media)
        self.scale = 1.0
        self.bw, self.bh = 1280, 720
        self.drag = None
        self.rot_pending = None   # rotation released but the rotated copy is not ready yet
        self.last_click = {'x': -1, 'y': -1, 'list': [], 'idx': 0}
        self.pan = None
        self.rev = 0              # changes on every render(): the cached CRT frames are made again
        self._cache = None        # (rev, size, scene QImage, field frame QImage)
        self.field_parity = 0
        self.field_timer = QTimer(self)
        self.field_timer.setInterval(16)
        self.field_timer.timeout.connect(self._next_field)
        self.anim_timer = QTimer(self)
        self.anim_timer.setSingleShot(True)
        self.anim_timer.timeout.connect(self.update)
        self.rotate_cursor = QCursor(svg_pixmap(ROTATE_SVG, 24, 24), 12, 12)

    # ---- geometry
    def relayout(self):
        th = self.ed.theme()
        if not th:
            return
        self.bw, self.bh = parse_base(th['global'].get('base'))
        vp = self.ed.stage.viewport()
        self.scale = self.ed.S['zoom'] or max(0.1, min((vp.width() - 56) / self.bw, (vp.height() - 56) / self.bh))
        self.setFixedSize(max(1, round(self.bw * self.scale)), max(1, round(self.bh * self.scale)))
        self.parentWidget().adjustSize()

    def to_base(self, pos):
        return pos.x() / self.scale, pos.y() / self.scale

    def rot_state(self, el):
        if self.drag and self.drag['mode'] == 'rotate' and self.drag['el'] is el:
            return self.drag['ang']
        if self.rot_pending and self.rot_pending['el'] is el:
            return self.rot_pending['ang']
        return None

    # ---- drawing
    def _scene(self, p, now_ms):
        ed = self.ed
        self.drawer.draw(p, ed.theme(), ed.sample_vars(), ed.files, text_layout=ed.S['opt']['text'],
                         animate=ed.S['opt']['anim'], now_ms=now_ms, rot=self.rot_state)

    def paintEvent(self, ev):
        ed = self.ed
        th = ed.theme()
        if not th:
            return
        p = QPainter(self)
        now_ms = int(time.monotonic() * 1000)
        opt = ed.S['opt']
        if opt['crt'] or opt['crti']:
            dpr = self.devicePixelRatioF()
            W, H = max(1, round(self.width() * dpr)), max(1, round(self.height() * dpr))
            key = (self.rev, W, H, opt['crt'], opt['crti'])
            if not self._cache or self._cache[0] != key or self.drawer.animating:
                img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
                img.fill(QColor(0, 0, 0))
                ip = QPainter(img)
                ip.scale(self.scale * dpr, self.scale * dpr)
                self._scene(ip, now_ms)
                ip.end()
                field = None
                if opt['crt']:
                    # 240p: lines averaged in pairs and doubled, as on the CRT
                    small = img.scaled(640, 240, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    img = small.scaled(W, H, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
                else:
                    field = img.scaled(640, 480, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self._cache = (key, img, field)
            _, img, field = self._cache
            if field is not None:
                # 240i: one field at a time (even lines, then odd lines), the previous one fading like the phosphor
                p.fillRect(self.rect(), QColor(0, 0, 0))
                for par, alpha in ((1 - self.field_parity, 0.3), (self.field_parity, 1.0)):
                    p.setOpacity(alpha)
                    for y in range(par, 480, 2):
                        y0, y1 = y * self.height() / 480, (y + 1) * self.height() / 480
                        p.drawImage(QRectF(0, y0, self.width(), max(1 / dpr, y1 - y0)), field, QRectF(0, y, 640, 1))
                p.setOpacity(1)
                if not self.field_timer.isActive():
                    self.field_timer.start()
            else:
                p.drawImage(QRectF(0, 0, self.width(), self.height()), img)
                self.field_timer.stop()
        else:
            self.field_timer.stop()
            self._cache = None
            p.save()
            p.scale(self.scale, self.scale)
            p.setClipRect(QRectF(0, 0, self.bw, self.bh))
            self._scene(p, now_ms)
            p.restore()
        p.scale(self.scale, self.scale)
        self._overlays(p)
        p.end()
        if self.drawer.animating and opt['anim'] and not self.anim_timer.isActive():
            self.anim_timer.start(70)

    def _next_field(self):
        if not self.ed.S['opt']['crti'] or not self.ed.theme():
            self.field_timer.stop()
            return
        self.field_parity ^= 1
        self.update()

    def _overlays(self, p):
        """Grid, selection, rectangle being drawn (above the CRT filters)."""
        s = self.scale
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if self.ed.S['opt']['grid'] and s >= 0.5:
            pen = QPen(QColor(255, 255, 255, 18), 1)
            pen.setCosmetic(True)
            p.setPen(pen)
            for x in range(0, self.bw + 1, 32):
                p.drawLine(QPointF(x, 0), QPointF(x, self.bh))
            for y in range(0, self.bh + 1, 32):
                p.drawLine(QPointF(0, y), QPointF(self.bw, y))
        el = self.ed.selected()
        p.setBrush(Qt.BrushStyle.NoBrush)
        if el:
            r = parse_rect(el['props'].get('rect'))
            ang = self.rot_state(el)
            p.save()
            if ang:
                cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
                p.translate(cx, cy)
                p.rotate(ang)
                p.translate(-cx, -cy)
            rect = QRectF(r[0], r[1], r[2], r[3])
            pen = QPen(QColor(0, 0, 0, 140), 3)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.drawRect(rect)
            pen = QPen(QColor('#ffb000'), 1.5)
            pen.setCosmetic(True)
            pen.setDashPattern([4, 2.7])
            p.setPen(pen)
            p.drawRect(rect)
            for hx, hy in handles(r):
                p.fillRect(QRectF(hx - 5 / s, hy - 5 / s, 10 / s, 10 / s), QColor(0, 0, 0))
                p.fillRect(QRectF(hx - 4 / s, hy - 4 / s, 8 / s, 8 / s), QColor('#ffb000'))
            p.restore()
        d = self.drag
        if d and d['mode'] == 'create':
            x, y = min(d['start'][0], d['cur'][0]), min(d['start'][1], d['cur'][1])
            w, h = abs(d['cur'][0] - d['start'][0]), abs(d['cur'][1] - d['start'][1])
            p.fillRect(QRectF(x, y, w, h), QColor(255, 176, 0, 36))
            pen = QPen(QColor('#ffb000'), 1.5)
            pen.setCosmetic(True)
            pen.setDashPattern([4, 2.7])
            p.setPen(pen)
            p.drawRect(QRectF(x, y, w, h))

    # ---- hit tests
    def hit_handle(self, x, y):
        el = self.ed.selected()
        if not el:
            return -1
        tol = 7 / self.scale
        for i, (hx, hy) in enumerate(handles(parse_rect(el['props'].get('rect')))):
            if abs(hx - x) <= tol and abs(hy - y) <= tol:
                return i
        return -1

    def hit_rotate(self, x, y):
        """Just outside a corner handle of a picture that can be rotated."""
        el = self.ed.selected()
        if not self.ed.rotatable_src(el):
            return -1
        r = parse_rect(el['props'].get('rect'))
        if r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]:
            return -1
        hs, tol, far = handles(r), 7 / self.scale, 30 / self.scale
        for i in (0, 2, 4, 6):
            d = math.hypot(hs[i][0] - x, hs[i][1] - y)
            if tol < d <= far:
                return i
        return -1

    def elements_at(self, x, y):
        els, out = self.ed.theme()['elements'], []
        for i in range(len(els) - 1, -1, -1):
            if els[i].get('hid'):
                continue
            r = parse_rect(els[i]['props'].get('rect'))
            if r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]:
                out.append(i)
        return out

    def snapv(self, v, mods):
        if self.ed.S['opt']['snap'] and not (mods & Qt.KeyboardModifier.ShiftModifier):
            return int(round(v / 8)) * 8
        return int(round(v))

    # ---- mouse
    def mousePressEvent(self, ev):
        ed = self.ed
        if self.ed.space_down and ev.button() == Qt.MouseButton.LeftButton:
            sa = ed.stage
            self.pan = (ev.globalPosition().toPoint(), sa.horizontalScrollBar().value(), sa.verticalScrollBar().value())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if not ed.theme() or ev.button() != Qt.MouseButton.LeftButton:
            return
        x, y = self.to_base(ev.position())
        mods = ev.modifiers()
        if ed.S['tool'] != 'select':
            pt = [self.snapv(x, mods), self.snapv(y, mods)]
            self.drag = {'mode': 'create', 'type': ed.S['tool'], 'start': pt, 'cur': pt}
            return
        h = self.hit_handle(x, y)
        if h >= 0:
            self.drag = {'mode': 'resize', 'h': h, 'start': (x, y), 'rect': parse_rect(ed.selected()['props'].get('rect')), 'snapped': False}
            return
        if self.hit_rotate(x, y) >= 0:
            r0 = parse_rect(ed.selected()['props'].get('rect'))
            c = (r0[0] + r0[2] / 2, r0[1] + r0[3] / 2)
            self.drag = {'mode': 'rotate', 'el': ed.selected(), 'c': c, 'a0': math.atan2(y - c[1], x - c[0]), 'ang': 0}
            self.setCursor(self.rotate_cursor)
            return
        lst = self.elements_at(x, y)
        if not lst:
            ed.select(-1)
            return
        # repeated click on the same point: the element below
        lc, idx = self.last_click, 0
        if abs(lc['x'] - x) < 3 and abs(lc['y'] - y) < 3 and lst == lc['list']:
            idx = (lc['idx'] + 1) % len(lst)
        elif ed.S['sel'] in lst:
            idx = lst.index(ed.S['sel'])
        self.last_click = {'x': x, 'y': y, 'list': lst, 'idx': idx}
        ed.select(lst[idx])
        self.drag = {'mode': 'move', 'start': (x, y), 'rect': parse_rect(ed.selected()['props'].get('rect')), 'snapped': False}

    def mouseMoveEvent(self, ev):
        ed = self.ed
        if self.pan:
            g = ev.globalPosition().toPoint()
            ed.stage.horizontalScrollBar().setValue(self.pan[1] - (g.x() - self.pan[0].x()))
            ed.stage.verticalScrollBar().setValue(self.pan[2] - (g.y() - self.pan[0].y()))
            return
        if not ed.theme():
            return
        x, y = self.to_base(ev.position())
        mods = ev.modifiers()
        ed.lbl_pos.setText('x %d  y %d' % (round(x), round(y)))
        d = self.drag
        if not d:
            if ed.space_down:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            elif ed.S['tool'] != 'select':
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                h = self.hit_handle(x, y)
                if h >= 0:
                    self.setCursor(HANDLE_CURSOR[h])
                elif self.hit_rotate(x, y) >= 0:
                    self.setCursor(self.rotate_cursor)
                elif self.elements_at(x, y):
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if d['mode'] == 'create':
            d['cur'] = [self.snapv(x, mods), self.snapv(y, mods)]
            self.update()
            return
        if d['mode'] == 'rotate':
            a = (math.atan2(y - d['c'][1], x - d['c'][0]) - d['a0']) * 180 / math.pi
            a = ((a % 360) + 540) % 360 - 180
            d['ang'] = round(a / 15) * 15 if mods & Qt.KeyboardModifier.ShiftModifier else round(a)   # Shift: steps of 15 degrees
            self.update()
            ed.lbl_sel.setText(tx('Rotation {0}°  (release to apply, Shift = steps of 15°)', d['ang']))
            return
        dx, dy = x - d['start'][0], y - d['start'][1]
        if not d['snapped']:
            if dx * dx + dy * dy < 1:   # a plain click only selects
                return
            ed.snapshot()
            d['snapped'] = True
        rx, ry, rw, rh = d['rect']
        if d['mode'] == 'move':
            rx, ry = self.snapv(rx + dx, mods), self.snapv(ry + dy, mods)
        else:
            hx, hy = HANDLE_DIR[d['h']]
            if hx < 0:
                nx = self.snapv(rx + dx, mods)
                rw, rx = rw + (rx - nx), nx
            if hx > 0:
                rw = self.snapv(rx + rw + dx, mods) - rx
            if hy < 0:
                ny = self.snapv(ry + dy, mods)
                rh, ry = rh + (ry - ny), ny
            if hy > 0:
                rh = self.snapv(ry + rh + dy, mods) - ry
            rw, rh = max(1, rw), max(1, rh)
        ed.selected()['props']['rect'] = join_rect([rx, ry, rw, rh])
        ed.render()
        ed.update_rect_fields()

    def mouseReleaseEvent(self, ev):
        ed = self.ed
        if self.pan:
            self.pan = None
            self.setCursor(Qt.CursorShape.OpenHandCursor if ed.space_down else Qt.CursorShape.ArrowCursor)
            return
        d, self.drag = self.drag, None
        if d and d['mode'] == 'rotate':
            if abs(d['ang']) >= 1:
                self.rot_pending = d
                try:
                    ed.bake_rotation(d['el'], d['ang'])
                finally:
                    self.rot_pending = None
            ed.render()
            return
        if d and d['mode'] == 'create':
            x, y = min(d['start'][0], d['cur'][0]), min(d['start'][1], d['cur'][1])
            w, h = abs(d['cur'][0] - d['start'][0]), abs(d['cur'][1] - d['start'][1])
            if w < 8 or h < 8:
                w, h = DEFAULT_SIZE.get(d['type'], (200, 120))
            ed.create_element(d['type'], [x, y, w, h])
            ed.set_tool('select')

    def wheelEvent(self, ev):
        if ev.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
            self.ed.zoom_by(1 if ev.angleDelta().y() > 0 else -1)
            ev.accept()
        else:
            ev.ignore()

    def leaveEvent(self, ev):
        self.ed.lbl_pos.setText('')


# ======================================================================
# Help and news
# ======================================================================

HELP = {
    'en': '''
<h3>How to use it</h3>
<p>A theme is a folder in <code>/media/fat/frontier/themes/&lt;name&gt;/</code> with <code>theme.ini</code> (16:9), optionally <code>theme_43.ini</code> (CRT and 4:3 screens), <code>detail.ini</code> / <code>detail_43.ini</code> (detail screen), <code>screensaver.ini</code> / <code>screensaver_43.ini</code> (screensaver: random games after some time without keys), <code>loading.ini</code> / <code>loading_43.ini</code> (loading screen, while a core loads the game: <code>${progress}</code>, <code>type=bar</code>; without them the ones of the simple theme are used), pictures and TTF fonts. The active theme is chosen in <code>/media/fat/frontier/frontier.ini</code> (<code>theme=&lt;name&gt;</code>).</p>
<ul>
<li><b>New theme…</b> asks for the folder of the new theme (choose the theme folder itself, not the folder that contains all the themes) and creates its theme.ini there. <b>Open folder…</b> opens an existing theme (you can also drop a folder on the window). <b>Save</b> writes the .ini files straight into the folder. <b>Save as ZIP…</b> makes one ZIP with the whole theme, to share it.</li>
<li>In the top bar <b>16:9 | 4:3</b> chooses the format and the <b>screen</b> menu chooses what you edit: game list (theme.ini), detail (detail.ini, opened with X on the pad), screensaver (screensaver.ini) or loading (loading.ini). Each combination is its own file (e.g. detail_43.ini) and the preview changes at once. A missing file is made on the spot: 4:3 from the 16:9 one (x and widths ×0.75), detail from the game list, screensaver from the detail. <b>Make 4:3</b> in the bar (and Make 4:3, Make detail, Make screensaver in the Variant menu) does the same from the file you are editing. The 4:3 file is a copy made once: if you change the 16:9 one later, the 4:3 does not follow.</li>
<li><b>Toolbox</b>: pick a shape tool and drag on the canvas to draw a new element; a simple click makes one of default size.</li>
<li><b>Rotating a picture</b>: select it and drag just outside a corner handle (Shift = steps of 15°), or use the <b>rotate</b> field in Transform. The editor saves a rotated copy <code>name_rot.png</code> next to the original and the element uses it (the theme format has no rotation key).</li>
<li><b>Layers</b>: top = drawn above. Drag to reorder, double-click a name to rename, the eye hides it in the editor only (it is still saved). <b>Theme settings</b> at the bottom are the global <code>[theme]</code> keys.</li>
<li><b>Visibility</b>: in the properties of an element, "Show this element" decides when it appears: always, only if a variable has a value (e.g. the box picture exists), or only if it is empty. "Visible in" restricts it to the picture layout or to the text layout. The line at the bottom tells you if it is shown in the preview right now.</li>
<li><b>Assets</b>: double-click a picture to apply it to the selected element (or to the background if nothing is selected); double-click a font to apply it. <b>Picture</b>, <b>Video</b> and <b>Font</b> (also in the File menu) copy the files you pick into the theme folder (<code>img/</code>, <code>video/</code> and <code>fonts/</code>), so the theme carries everything it needs to the MiSTer. Fonts of another theme (e.g. <code>../simple/fonts/</code>) are shown in the preview when that theme is next to this one, as on the MiSTer.</li>
<li><b>Load .ini</b> brings .ini files of a theme into the editor (e.g. those of another theme, into the open folder whose pictures and fonts are used): <code>theme.ini</code>, <code>theme_43.ini</code>, <code>detail.ini</code>, … by their name, any other name into the current variant.</li>
<li>Coordinates in "base" units (e.g. 1280×720), scaled to the real screen. <code>size</code> of the texts = font height in base px.</li>
<li>The preview is approximate: to see it for real copy the theme folder to <code>/media/fat/frontier/themes/</code> on the MiSTer, set <code>theme=&lt;name&gt;</code> in <code>frontier.ini</code> and press F5 in Frontier. Animations (fades, scrolling, frames, video) are not animated here; animated GIFs are.</li>
<li>Unsaved work is kept: after a crash the start screen offers <b>Restore unsaved work</b>.</li>
</ul>
<h4>Shortcuts</h4>
<table cellspacing="4">
<tr><td><kbd>V</kbd> <kbd>U</kbd> <kbd>P</kbd> <kbd>T</kbd> <kbd>L</kbd> <kbd>M</kbd> <kbd>B</kbd></td><td>Select, Rectangle, Picture, Text, List, Video, Bar</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd></td><td>Undo / Redo</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>D</kbd> · <kbd>Del</kbd></td><td>Duplicate · Delete</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>]</kbd> · <kbd>Ctrl</kbd>+<kbd>[</kbd></td><td>Bring forward · Send backward</td></tr>
<tr><td>Arrows · <kbd>Shift</kbd>+arrows</td><td>Move 1 px · 10 px</td></tr>
<tr><td><kbd>Shift</kbd> while dragging</td><td>No snap to the grid</td></tr>
<tr><td><kbd>Space</kbd>+drag · <kbd>Ctrl</kbd>+wheel</td><td>Pan · Zoom</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>0</kbd> · <kbd>Ctrl</kbd>+<kbd>1</kbd></td><td>Fit · 100%</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>O</kbd> · <kbd>Ctrl</kbd>+<kbd>S</kbd></td><td>Open folder · Save</td></tr>
<tr><td><kbd>Shift</kbd>+<kbd>F1</kbd> · <kbd>Shift</kbd>+<kbd>F2</kbd></td><td>Interface darker · lighter</td></tr>
<tr><td>Click on the canvas, again</td><td>Picks the elements below</td></tr>
</table>
''',
    'it': '''
<h3>Come si usa</h3>
<p>Un tema è una cartella in <code>/media/fat/frontier/themes/&lt;nome&gt;/</code> con <code>theme.ini</code> (16:9) e, se serve, <code>theme_43.ini</code> (CRT e schermi 4:3), <code>detail.ini</code> / <code>detail_43.ini</code> (schermata di dettaglio), <code>screensaver.ini</code> / <code>screensaver_43.ini</code> (screensaver: giochi a caso dopo un po' senza tasti), <code>loading.ini</code> / <code>loading_43.ini</code> (schermata di caricamento, mentre un core carica il gioco: <code>${progress}</code>, <code>type=bar</code>; senza di essi si usano quelli del tema semplice), immagini e font TTF. Il tema attivo si sceglie in <code>/media/fat/frontier/frontier.ini</code> (<code>theme=&lt;nome&gt;</code>).</p>
<ul>
<li><b>Nuovo tema…</b> chiede la cartella del nuovo tema (scegli la cartella del tema stessa, non quella che contiene tutti i temi) e ci crea dentro il theme.ini. <b>Apri cartella…</b> apre un tema esistente (puoi anche trascinare una cartella sulla finestra). <b>Salva</b> scrive i file .ini direttamente nella cartella. <b>Salva come ZIP…</b> crea un solo ZIP con tutto il tema, per condividerlo.</li>
<li>Nella barra in alto <b>16:9 | 4:3</b> sceglie il formato e il menu <b>schermata</b> sceglie cosa modifichi: lista giochi (theme.ini), dettaglio (detail.ini, si apre con X sul pad), screensaver (screensaver.ini) o caricamento (loading.ini). Ogni combinazione è un file a sé (per esempio detail_43.ini) e l'anteprima cambia subito. Un file che manca viene creato al momento: il 4:3 dal 16:9 (x e larghezze ×0,75), il dettaglio dalla lista giochi, lo screensaver dal dettaglio. <b>Crea 4:3</b> nella barra (e Crea 4:3, Crea dettaglio, Crea screensaver nel menu Variante) fa lo stesso dal file che stai modificando. Il file 4:3 è una copia fatta una volta sola: se poi cambi il 16:9, il 4:3 non lo segue.</li>
<li><b>Strumenti</b>: scegli una forma e trascina sulla tela per disegnare un nuovo elemento; un click semplice ne crea uno di dimensione standard.</li>
<li><b>Ruotare un'immagine</b>: selezionala e trascina appena fuori da una maniglia d'angolo (Maiusc = scatti di 15°), oppure usa il campo <b>ruota</b> in Trasformazione. L'editor salva una copia ruotata <code>nome_rot.png</code> accanto all'originale e l'elemento usa quella (il formato del tema non ha una chiave per la rotazione).</li>
<li><b>Livelli</b>: in alto = disegnato sopra. Trascina per riordinare, doppio click su un nome per rinominare; l'occhio nasconde l'elemento solo nell'editor (nel file resta). <b>Impostazioni tema</b> in fondo sono le chiavi globali <code>[theme]</code>.</li>
<li><b>Visibilità</b>: nelle proprietà di un elemento, "Mostra questo elemento" decide quando compare: sempre, solo se una variabile ha un valore (per esempio esiste l'immagine della scatola) oppure solo se è vuota. "Visibile in" lo limita al layout con immagini o a quello testuale. La riga in fondo ti dice se in questo momento è visibile nell'anteprima.</li>
<li><b>Risorse</b>: doppio click su un'immagine per applicarla all'elemento selezionato (o allo sfondo se non c'è selezione); doppio click su un font per applicarlo. <b>Immagine</b>, <b>Video</b> e <b>Font</b> (anche nel menu File) copiano i file scelti nella cartella del tema (<code>img/</code>, <code>video/</code> e <code>fonts/</code>), così il tema porta sul MiSTer tutto quello che gli serve. I font di un altro tema (per esempio <code>../simple/fonts/</code>) si vedono nell'anteprima quando quel tema è accanto a questo, come sul MiSTer.</li>
<li><b>Carica .ini</b> porta nell'editor i file .ini di un tema (per esempio quelli di un altro tema, nella cartella aperta di cui si usano immagini e font): <code>theme.ini</code>, <code>theme_43.ini</code>, <code>detail.ini</code>, … in base al nome, qualsiasi altro nome va nella variante corrente.</li>
<li>Coordinate in unità "base" (es. 1280×720), scalate sullo schermo reale. <code>size</code> dei testi = altezza del font in px base.</li>
<li>L'anteprima è approssimata: per vederla davvero copia la cartella del tema in <code>/media/fat/frontier/themes/</code> sul MiSTer, imposta <code>theme=&lt;nome&gt;</code> in <code>frontier.ini</code> e premi F5 in Frontier. Dissolvenze, scorrimenti, fotogrammi e video qui non sono animati; le GIF animate sì.</li>
<li>Il lavoro non salvato viene conservato: dopo un blocco la schermata iniziale propone <b>Recupera il lavoro non salvato</b>.</li>
</ul>
<h4>Scorciatoie</h4>
<table cellspacing="4">
<tr><td><kbd>V</kbd> <kbd>U</kbd> <kbd>P</kbd> <kbd>T</kbd> <kbd>L</kbd> <kbd>M</kbd> <kbd>B</kbd></td><td>Selezione, Rettangolo, Immagine, Testo, Lista, Video, Barra</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd></td><td>Annulla / Ripristina</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>D</kbd> · <kbd>Canc</kbd></td><td>Duplica · Elimina</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>]</kbd> · <kbd>Ctrl</kbd>+<kbd>[</kbd></td><td>Porta avanti · Porta indietro</td></tr>
<tr><td>Frecce · <kbd>Shift</kbd>+frecce</td><td>Sposta di 1 px · 10 px</td></tr>
<tr><td><kbd>Shift</kbd> mentre trascini</td><td>Senza aggancio alla griglia</td></tr>
<tr><td><kbd>Spazio</kbd>+trascina · <kbd>Ctrl</kbd>+rotella</td><td>Sposta la vista · Zoom</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>0</kbd> · <kbd>Ctrl</kbd>+<kbd>1</kbd></td><td>Adatta · 100%</td></tr>
<tr><td><kbd>Ctrl</kbd>+<kbd>O</kbd> · <kbd>Ctrl</kbd>+<kbd>S</kbd></td><td>Apri cartella · Salva</td></tr>
<tr><td><kbd>Shift</kbd>+<kbd>F1</kbd> · <kbd>Shift</kbd>+<kbd>F2</kbd></td><td>Interfaccia più scura · più chiara</td></tr>
<tr><td>Click sulla tela, di nuovo</td><td>Seleziona gli elementi sotto</td></tr>
</table>
''',
}

NEWS = {
    'en': '''
<h3>What's new in version %s</h3>
<h4>0.3.2</h4>
<ul>
<li>On macOS the menus (File, Edit, View, Variant, Help) are in the system menu bar at the top of the screen, with the usual Cmd shortcuts; before, they were missing there.</li>
</ul>
<h4>0.3.1</h4>
<ul>
<li><b>Make 4:3</b> in the top bar, and <b>Make 4:3</b>, <b>Make detail</b>, <b>Make screensaver</b> in the Variant menu, as in the web editor: they make the missing file from the one you are editing.</li>
<li>Also as a program for Windows, macOS and Linux with nothing to install, on the Releases page of FrontierMr.</li>
</ul>
<h4>0.3.0</h4>
<ul>
<li><b>The editor is now a program</b> (Python and Qt) instead of a web page: it runs the same on Windows, macOS and Linux and works on the theme folder directly. Save always writes into the folder, in every system; pictures, videos and fonts you add are copied into it at once.</li>
<li>Fonts and pictures of another theme next to this one (<code>../simple/fonts/</code>) are shown in the preview, as on the MiSTer.</li>
<li>Everything else is as in the web editor 0.2.7: same reading and writing of the .ini files, preview, variants, layers, assets, rotation, 240p and 240i previews, text layout, light / medium / dark interface, Italian and English.</li>
</ul>
<p>The web editor (theme_editor.html, versions 0.1.0 to 0.2.7) came before.</p>
''',
    'it': '''
<h3>Novità della versione %s</h3>
<h4>0.3.2</h4>
<ul>
<li>Su macOS i menu (File, Modifica, Vista, Variante, Aiuto) sono nella barra dei menu di sistema in alto sullo schermo, con le solite scorciatoie Cmd; prima lì mancavano.</li>
</ul>
<h4>0.3.1</h4>
<ul>
<li><b>Crea 4:3</b> nella barra in alto, e <b>Crea 4:3</b>, <b>Crea dettaglio</b>, <b>Crea screensaver</b> nel menu Variante, come nell'editor web: creano il file che manca da quello che stai modificando.</li>
<li>Anche come programma per Windows, macOS e Linux senza niente da installare, nella pagina Releases di FrontierMr.</li>
</ul>
<h4>0.3.0</h4>
<ul>
<li><b>L'editor ora è un programma</b> (Python e Qt) invece di una pagina web: funziona allo stesso modo su Windows, macOS e Linux e lavora direttamente sulla cartella del tema. Salva scrive sempre nella cartella, con qualsiasi sistema; immagini, video e font che aggiungi vengono copiati subito lì dentro.</li>
<li>I font e le immagini di un altro tema accanto a questo (<code>../simple/fonts/</code>) si vedono nell'anteprima, come sul MiSTer.</li>
<li>Tutto il resto è come nell'editor web 0.2.7: stessa lettura e scrittura dei file .ini, anteprima, varianti, livelli, risorse, rotazione, anteprime 240p e 240i, layout testuale, interfaccia chiara / media / scura, italiano e inglese.</li>
</ul>
<p>Prima c'era l'editor web (theme_editor.html, versioni dalla 0.1.0 alla 0.2.7).</p>
''',
}

HTML_STYLE = '''<style>
h3 {{ font-size: 14px; margin: 0 0 8px; }} h4 {{ font-size: 11px; color: {dim}; margin: 14px 0 6px; text-transform: uppercase; }}
code, kbd {{ background: {input}; font-family: monospace; }} li {{ margin-bottom: 4px; }} td {{ padding-right: 14px; }}
</style>'''


# Frontier MRTE logo (light and dark interface)
LOGO_LIGHT = (
    'iVBORw0KGgoAAAANSUhEUgAAAfcAAABKCAYAAACmVh04AAAACXBIWXMAAC4jAAAuIwF4pT92AAAXWElEQVR4nO2de5BkdXXHvwcbtRJlB9HEP6R21oQyMYkM'
    'GB6CZgdNrARQ7qaFhiawQ2mCGoXBF0aIDIpECY+hJIiPhFkrNHSk4RJdUjzizkKhCERmjYkxIWE2Kc2rkNmQCEjLSZ3l9Np7t+/7133v7T6fqq5dlpnf/d37'
    'u/07v/MmZoYriOh5AN4H4O+ZeStKDhHtB+CjAO5k5q8VPR/DMAzDcIEINycQ0W8BuA/AZQAOQgVg5mcB/AaAbUR0LRG9oug5GYZhGEbhwp2Ifo6IbgBwO4Cj'
    '9J+fQXX4PwDPB/AuAA8S0dlE9MKiJ2UYhmEYIxfuRDRFRJ8E8E0ATVQX6vv7ywFcB+AbRHRCgXMyDMMwjNEJd/GrE9E7ADwA4HwAB6DaDAo6eA2ArxDRLUR0'
    'eAFzMgzDMIzRCHciOgbA3QA+D+AQjD+bJI6AiC4hopcWPRnDMAzDcCbcieiVRLQFwD0AZjFZiP/9AnE/qD++34xvGIZhGNUS7kR0ABGdB+B+AGcCkFS3SeVg'
    '9cffRUTHFT0ZwzAMw0gt3InobQAk9/tKAC9DOtwlzw+ftHN9E4CvEtEXxaIxpDkZhmEYhjvhTkRHEFEHwJcA/FLGcSfBdH2GWDSI6AIienHRkzEMwzCMfYQ7'
    'ER1MRFepX/23kY8qae55EIvGJSrkT9WKd4ZhGIZRKPsR0fOJaF4KuACQP62AS3peDeBGNdcfXfRkDMMwjMlGNM07AYjG/rMoOR3fb3Z8/0WOh3VpZdgIYJmI'
    'pNqdYRiGYRQm3CV3vSpcAeDeju97KC8vAHBE0ZMwDMMwJlu4P4nq8ASAGQC3dny/0/H9Q1FOni56AoZhGMbkUrUAsH4TugT93d/x/cs7vp82VW/SIvsNwzCM'
    'CWJYwn1Y0fJBQSzBf++XYMCO75/T8f39M4w5KZH9hmEYxoRQZc29n/UArpZo9Y7vnzTiORmGYRhGqagNadyiTN2vl0/H96W//Kfqnve3Bc2j9BBRUT0CVpl5'
    'taBrG44homlNoZVYGMEHsMTMawVPrTR0fF+ezVSGX12te56T70rH96f61igVdc9b7htH1ls+eVmre94KHNFsdIvsebLWatf23Euz0XX1jPKwMizhXrSp+3QA'
    'b+34vmjzi3XPe6zg+ZQKIloEcG5Bl9+VcaMzSgYRibCQjX9dIB10Tg6PJuD3CPaHM/76doeNuuY05Tk1so/WPW9eBftKYL0z0/HlHLibnXKQ0Xdpuf8wkYRm'
    'ozuf9d5c0Wx0N7XaNV8Fu7NnlIPbqmaWT4OUhL0QwEMd3397x/ctcO4nZDrBO6Lol95wx2LIekoWi2y4Rr6D7EYVqC6Yd7BfTA/p+7teD4UXAdjW8f21ju8v'
    'qLUhCWVQFmaG/IzSMiXCfdyFnjzsL8gpuOP7syOyMoz7MzXG07ye9udlQw6jzLUoqsS8I+uBCNCqsE4F/WrInm0kYL8SmNBHxRsA3N3x/es6vi/tWw3D+Imb'
    '5lEiWkrxa3GHgbLWoKgaLg5JVbWirFNN3g6KGRiW5l5Wc7/0oz9bfGAd3/9wx/d/aohBhYZRelSg9+IvEmvvzLycwF9s5Gd9HuGmpu2qC8clh+6JiWEoQnjD'
    'hvf+DMrNQQD+CMBdAH6AyWPiA52MPYJ9c44hJGA1DLEGGG6+axIMlxXPgQ94reB9Q+a/gGqwhpLgWmv9JoA/OPqIKy5rNrqHAPhYq137L5QX8UWdCODbAD4A'
    '4ABMBnMDguoWI0ypOzKY9maKjmA1BkNEos0t5zWdM/O8jrU5kA0xz8x7QqEnGUn36vj+YYGgr7mUh6qTRAOve97aiEzyxwX+eyXiXoRtEWNtEc17wL9P932S'
    'HEA2d3x/PuUz2BFx/1n3u6h7haTENRvd4DOK2wvDnlESQu/DlXD/HoBr5QaY+clmo3slgN+Xl7LZ6EpgRKvVrj2F8vEUMz8O4ONEdCuAPwRw8rgHxGmK0l5m'
    'VSKK+tKsJTDD7gXRWD9CTLpg78HMkva22LeZrVgK3N4E87kzBonNpbWGqCk79TpHpaINyk3vS2kLy9WP3TtEcCdQBryUQnCt1a4NvHaz0V3L+HuxF+3PeU/4'
    'O6th14sj6j7ymuVl1p8FcCQzXyqCXf/9x/rnKwD8qdSAbza6x6PEMPO3mbkB4M0y36LnYxhDYsZ1sBszi0Bf1o8J9uEwP86BdHXPW1QNNgrzu6cgj3C/HcAb'
    'mfmdzPz9mJ+VzWRrs9FtNRvdV6HEMPPdmuJzDoB/K3o+hmEYGlg3M0JffRHEWSYsLW7Iwv0RAGcy8wnMfG/K3z0NwDfEVN9sdLME3Y0kbY+Zf8TMnxaLhAYN'
    'xdtijInL9TZGzwSskcQs5NbENcI+zI8tFeFKh8tytEY6n7u8dH8M4DpmfsxB5OPbm43uxQD+rNWulTLXnpn/Q75QRCS16j+sbWaTYA7nGIhoPmFlKV/MvoHf'
    'ndJTvGgywbrdYiKO3QSJaK5vjEMHxArs6pXDzFIrnYhkc02qaS0Gx9fa/7MD7m950DOJmctMXzpUlHCcJqKFsLnpc5/Pek9p0WfoxayRPAdfn8nqkNZI3ql9'
    'HMt9axSsJS73PZfx/vtTE4N4KQLr5mI0ZAt2HXOSCHdWX8hlzPwdh9c+WCvHnd5sdD/SatdK6+dm5gflYElEb5NsAACHx/3KiKZWZlZDcp3XVLAn3Vz2HAJU'
    'a1uIiTTeGCaA+oTTfILoXPn/J+nnKiKS78BCCgEiAZppWOib31xERbHdZTqJSJ6tl1CALMZUk+sh15QA2H76DwYieNJ0XcyUvqQHjKRrtFE/V+kzmU9y8NED'
    'T+I1IqLDZNwU79B8xvuPEu7rkgSVaSBd1Dr5ZRTuCQINreHUvoS9C0txwl0E7keYOTL8P6dwk7SLe5qN7k2aOidm/1LCzDcT0VbNBBAh/5Ki51RWVAgO/LIO'
    '0A6jWNenaYfVMo9FtaylHGU45UDhydyZ2XkOdwqB1kMEmgibmSEHsU2Nqoa3Clw/xxrJM3mYiK5OYL1Jey9TDuYXi6ab7YgIepxLEDEepbXfJp3mYiLciyJu'
    'zcxsH6DVri2FvQ9hFeoe1RdkNoNgz2KW3h/AGQAeaDa6FzYbXakcV0okI4CZLwdwBIA/CfHHm1neISrYr88h2GXT2OZgU16nGmLWnNQwLtJP2vuT+3E9lyLX'
    '+GFHgvNcIlpWLdsVvQ54o6jRvpizmUyUcC/l+yKNYhJYhTKli00qtYCW/UNNXfs4M/93jnGzmqUPlGsDOKXZ6F7Qate+jJLCzP8C4D1E1AZwqfaSN4aDCPY8'
    'GnHQ1JyXzeL3lRxvFM9Jqr2vjMHhzSUbVRi46oA4SjO2H/M8em6BMNN22AFkZ93zRq2yT0eY22dTFLHZERFwJ/c0O6KDzFkhhye/jML9p/Xvu4u4MPPfoXh+'
    'BcBfNhtd0bbOb7Vr4vMupUYsGQNEtFEzAUSIHKKWiHFiRjShFD+fJ6DIGRow5Vqw9wt4Ke5Thlxi2WzKMI+s7hLXgr3HoVJgpyRrlBgJmOv4/paI2BJ5r8Pu'
    'KerAWYQA2pyzxHGP+ZiiMbNFm8FzMNdsdLPMf0nnEyrc/wrAp5n5DpQP8cff12x0PwfgE/XT8HyUEGZ+FsAN6o9/D1DOeeagF7iUxYwZtsmk8S+nTiVSk2ya'
    'L6H4Odf65r4uqfk3pNRqlN80KZKytJrg2cdppysZ1q/HUuDvWcfZB12jJAJnh5qq5VmvBjIA4t4jWSOJpF8e8ExcrFEYeS0pUXX/dzeTCWrh2iRm8xjW+9+S'
    'pMpdhVmfw90TuseJz31rSQV7j/01gO0SAL8XV9u3SFRTvRHAd4ueS5nRimZTzEz9n5TD7NAaBJJOuUkPgsf1CbokwXe79PcPZGYxbc/qZ0rHlGvEMXDD1PH6'
    '7y1YrztuThuYeVrmI3+Pqd4VKdxFc004j+3BNWHmPZuH/D1wTzLPPCwkWKPz9FnKtVcD79CCmnW3pN0A5bsaXCO9p+0pD19b9Dmc1fcOSmR9Li1ZhVlUPvog'
    'DT2q+9t2CaRDNQV7GdxflUOE+zVE9C01YbpiGKlgL6h7nnRx+3UA7wLwjygRRHQgEckB5FtawtYYDttV8M2o0JLo9d2amX5WNWUuzhQogntGf38f94GOORPT'
    '+UxYrz5jF4iQEIG+V8qd/j0qw2AYFpCholp7WMpXj7PiMhNUSM/FCHiXawQVupv08DWn67XU9w66in9YimsmE/i3+aoF0sVwsQn2fML9h+rjvpWIblRzV16G'
    '4Rt/Vk+0z9Y97zoAxwCQqPUnUCBE9DwiEn/71wBcAEAi/cvYJGccuE016zgNxEuwOScZZ7fWm0DA521HuVO1vYEHDZ1HFbWuKOYSrHVigaQCPkrrdqW87NRD'
    '4Sj814lT3rQ0bZiLYVfd86ok3OWgtqHueVVp81pa4d6vZZ8K4OtEdBkRvTTHuEMv4lL3vMfqnvdBAEcBuAUFQERywJBa9C0Av1DEHCYIMVcnPcXH/VyqYD8V'
    '8DtiNMM8h+KlKke7ZyRujeYdj3mSo9S4kQWKqhn9toTPqGyBdFnZJNp6RV0IpWJQEZsXAhCheRoRfVLLzfa6vJWOuudJ1bx6x/eletz5AH512NckIvGByqmy'
    '6bBtbpnplflMimx+roWVn2JTPTTGr5wlOKeXKx+G+MYnTUDnIWqNdmgp3Cx15KOC5GZzCrqdGd+dPPgR+d+7m8loilhcudmiCPYqn43JYJmv2GHEBb3A2bRE'
    'WmOiBJO0a70GQIOIPqbd0ook0tRf97ybO77/FQDv1sPJy51PgOgADer7EICXTVD5WQleKroj00qK1Cq43uhkUyeinRFRra7yqceeBGt06JACZ/MK95Ef3sSc'
    '3vH9qODQ+Y7vL0f8/6j88FEQ7Oe+3PH9yPLKkhc/5tHxg1LaForoCvcGAHdJ8xQieiWKI1Zg1j3vqbrnXam13z/T11c+Nxpw+HVtnhMl2I3h4GqDWh7SHMa9'
    'W9k4kPcAVpSQjNLQvBJr7WHECTLztY+45auYoB8goo9KZDhGT+Igvbrn/Xvd80SDf53m8We/KNERRHSLFvl5ddJfy3NNYyBO/Jw5/aVmdq82Q62NX5Bwj6tB'
    'UToTtwb3RaX57dbeRzilsSStv/ggTdc5Q8t63jRCf3xqgVn3PKlsd3zH9xvSAAfAaxJfjEi61r0fwDslDS/lpcfNLF84ExhwZrgnb8GaQkzFCZrJROWIF1ol'
    'MoKFmMqEYo2YJNN8ZkKq262k0dz7+XkAfw7gr4noWIyGzAKz7nlS//1YPZhIj/ZQiGh/IpKiOQ9pHm5awW6UmJwR02Z6rzZJihKVlSzm9TKnv/m9apIhbE7Q'
    'IGfiaTa6ixqfEvzEtnxN1JyBiD4P4EpmfmSImmsuU3fd8/5XTosd379ehfzpAF681wWI3qKtXMWcb4wneYKqokyFZdWQqkgwwtoVVbb+xDWTGdQkZrnk9fMX'
    'YyLnRbu3IjbZ4kimXKRx1bRinETVf0Ii7E875ZkXoaTUPU98PXMd35fudx+QfyOiV0kveelGV/T8jHxoVDtiApD8jBHe68dUcJRtjaRITGkFUxEkaCZTJa29'
    'x2JMbwDR3hcs5z0bWc3yg3gJgCukUtuuXd+VL+bTKDF1z7u37nlS2EIE/P0m2MeK7THd3LJETcdF8JYucKnCJnLp5pY5oErWV5rF5BmjpKQR2KUX7hoPEOdu'
    'sMj5Egj3Hq+9/Y5fvkf7m9+O8vOWIUTRWkBdscQJ2qU0vncimo+JSJbiJqa5pyNO+GRK4errBiiFX7ZJ1z7HdeULI0EzmR63VUjbjVtn872XSLgLz7TatYda'
    '7doJAE7U4LSy8uQQxrRUuHILDok6lk1/OqFgvyrn9Yz0BzDR3pcyCPblQFS5HMquJ6LVMdHkkzyTyryPqr3HdfUz7T2jv3yoWmarXdvabHSlup1EoF8o7TWH'
    'eT0jGQM2uihNdir482X2iUouOxFdHdN1TATAChGJ5rAYzH/X+11I0L98V0kLhWRBSr5O6fMT18XUsNZZu/fF+ZA36wFM6rlHaqK6XksRcRHrdT1HLuBV8+w/'
    'SIYeKgP53VLdLXjfSzFBaNIkZp+DU5q88eDP9gfmDbiXOKYD460NqJi3EPcedHxf7mkt5tmkSRebivjxqeDPt9q1xN+DZqMbfEZxbsDpkHS2JExFaZj/E4wa'
    'd8CpzCzpZ3vRbHQ3aOe0M7VPexparXZNItydQkRS5OY3HQ/7WWaW/PhSogItrt1mHFdrQ5Us15eXPapkZlK2aDewQdeQl341xTX6/fTTMcFz/Ujrz302UyJa'
    'yZFXvUuDyvbavIgozUFc2qUuhQjBbVmesZq300RsR74vKddIDgLynFfFBaJCXz5yP1HlTIO94RcjtHxnaxUQhisZ3/XdYweFmAq6sHrzV9c9b6/n3PH9JNan'
    'KHaPmfNegs1h9vrOdHx/KUWwYOiziUgXOxf5uLrVrs0nFOwunlFetg/LLD+QVrv2aKtde4eLynElp+w+95mCx/Acvfyhm4Fq4ml8rRv7PutTCL4w83IeoSHP'
    'Jq+fMeze0/pi++cx5/J9SblGm7VK5MN6yHlUDykXJVwvWat+C0tUi1SXazWd410PGzvKpTHIipQ3pmjGwb0MGi+P6T3Nd2Qm5dh5xnD1jJy3fB0JrXbtb1rt'
    '2vHaYraXG18U5h8fU1TwnjXEaO9MlosiUQ0zSVDWOKxRrIWnimj51kEFYLZXKJAubXtbIyUj1dyDtNo1Md0foUVlHityLsZ4oqZp18JDTPizo+rrPQT8CVij'
    'sRTsMUFzlQmkC2FcYlfGWrgn1oZb7dqatrt7LYAvuhjTMAYIj+McaawXS/vbCgt2YSGm9GdRa3SYQ6vCLo2HGEfBPkiQ7yrboS0tGrgXVaPCqIrm3k+rXdvZ'
    'atfEr/YmANLwpWp+7CqxVvAYrgRjYgGlUd8zaiXKItjEZLiBmUeVljPoGe1y8Yz1YDKbQZAOdc0lUI6Zp1WLzyrkd+oaT0fEQySaTwrWhnidgb+vEef9hYD8'
    'ITaJ6Y3ravyocdJ8v9ZKuN+toSS4KD/rlFa79tVmoytNXn5HU+eK7CE/rsw58BdnNqFJYJOWH80b6JNKU1GhtqDZAp5+ZiMCYLbrNfy4VKwBbMoRyLMSUhRn'
    'Vuece310fEl9m9Mxg2uxrPPwHb03iym1eCk01Fuf2Zjgtx063+UYgd5/DYm4z7NGcWvV39Et63VWBqSNBQXhfILnm9fcvejgXvpT4RajtPeO75+XYG+IezaF'
    '7Hetdm2l2ei6eK/y4g8rFe40Zr4p7yDNRvdAbeQiaQx3tto1qSbnFCK6A8CbHQ/7OWY+2/GYxhAJ5PHLhl2aE7jxHJq+1r9p2joZRoTmXhrTfJBWu/Y4gA81'
    'G90vAfhFVIcfFT0BIx1lLspjPIcKclsnw0go3MX0dalGrZeSVrv2YIgf3gUuffk/BnAtgE85HNMwDMMwUrEfM0tp2F8D8F4A/4rJw1UU/laJyGbmc5j5e47G'
    'NAzDMIzU7DbJM/NTzHwNgCOlzB6ALiaHvML9n6SXPTOfyMz3OpqTYRiGYWRmL387M/+n1n8+BsCXsw9bqZz0rGb5x7VO/tHM/BeO52QYhmEYmRkYTMfMDzLz'
    'WwGcXPJ2rUUgfvUvADiKmS9l5h8UPSHDMAzD6CcyUp6ZbwbwegAfTFkedlwLztwnjUWY+XeZWczxhmEYhlE6YtPgmPlpZr5cNFUAn0noj6+SWT7JXB/RqllS'
    'dlQEvGEYhmGUlsQ57sz8z8z8bgBvBHAPJoMntA+ymOCXmHmSAg0NwzCMipK6gI1GhM9qedii27W6IMyFIIVzjmTm95lf3TAMw6gSmarT8XPcIJHiAC4rW4ep'
    'nGZ5KZZzMjOfwsz/UNCcDMMwDCMzuUrPMvNjzHw+gNcBuKmiPvf99c/vA5CGBcdqIKFhGIZhVBIndeWZ+TvMfJr640XzfRbVYU0DBQ+XbmXM/EzREzIMwzAM'
    '5OD/AXB4z9hKrf6gAAAAAElFTkSuQmCC'
)
LOGO_DARK = (
    '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'
)


# ======================================================================
# Small widgets
# ======================================================================

class LayerTree(QTreeWidget):
    """Layers panel: top = drawn above; drag to reorder."""

    def __init__(self, ed):
        super().__init__()
        self.ed = ed
        self.setColumnCount(3)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setUniformRowHeights(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        h = self.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, h.ResizeMode.Fixed)
        h.setSectionResizeMode(1, h.ResizeMode.Stretch)
        h.setSectionResizeMode(2, h.ResizeMode.ResizeToContents)
        self.setColumnWidth(0, 30)

    def dragMoveEvent(self, ev):
        ev.acceptProposedAction()

    def dropEvent(self, ev):
        ev.setDropAction(Qt.DropAction.IgnoreAction)
        ev.accept()
        src = self.selectedItems()
        if not src:
            return
        a = src[0].data(0, Qt.ItemDataRole.UserRole)
        it = self.itemAt(ev.position().toPoint())
        if a is None or a < 0:
            return
        if it is None or it.data(0, Qt.ItemDataRole.UserRole) < 0:
            self.ed.reorder(a, 0, False)   # below the last layer
            return
        r = self.visualItemRect(it)
        self.ed.reorder(a, it.data(0, Qt.ItemDataRole.UserRole), ev.position().y() < r.center().y())


class CommitText(QPlainTextEdit):
    """A text box that commits when it loses the focus (the 'change' of a web textarea)."""
    committed = Signal()

    def __init__(self, text=''):
        super().__init__(text)
        self._orig = text

    def focusOutEvent(self, ev):
        super().focusOutEvent(ev)
        if self.toPlainText() != self._orig:
            self._orig = self.toPlainText()
            self.committed.emit()


class AlphaEdit(QLineEdit):
    stepped = Signal(int)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = (1 if ev.modifiers() & Qt.KeyboardModifier.ShiftModifier else 5) * (1 if ev.key() == Qt.Key.Key_Up else -1)
            self.stepped.emit(step)
            return
        super().keyPressEvent(ev)


def hsep():
    f = QFrame()
    f.setProperty('sep', '1')
    f.setFixedWidth(1)
    f.setFixedHeight(20)
    return f


def clear_layout(lay):
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.hide()
            w.deleteLater()
        elif it.layout() is not None:
            clear_layout(it.layout())


TOOLS = [
    ('select', 'v', 'Select', 'Select / move  (V)'),
    None,
    ('rect', 'u', 'Rectangle', 'Rectangle  (U): drag to draw'),
    ('image', 'p', 'Picture', 'Picture  (P): drag to draw'),
    ('text', 't', 'Text', 'Text  (T): drag to draw'),
    ('list', 'l', 'List', 'List  (L): drag to draw'),
    ('video', 'm', 'Video', 'Video  (M): drag to draw'),
    ('bar', 'b', 'Bar', 'Progress bar  (B): drag to draw'),
]
ZOOMS = [0.25, 0.5, 0.75, 1, 1.5, 2, 3]
VAR_KEYS = {'text', 'if', 'ifnot', 'src', 'value'}
VAR_REPLACE = {'if', 'ifnot', 'value'}   # a single variable: replaces the value
SIMPLE_VAR = re.compile(r'^\$\{([^}]+)\}$')


def config_dir():
    d = os.environ.get('FRONTIER_THEME_EDITOR_HOME') or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation) \
        or os.path.join(os.path.expanduser('~'), '.frontier_theme_editor')
    os.makedirs(d, exist_ok=True)
    return d


# ======================================================================
# Main window
# ======================================================================

class Editor(QMainWindow):
    def __init__(self):
        super().__init__()
        global LANG
        self.cfg = QSettings(os.path.join(config_dir(), 'settings.ini'), QSettings.Format.IniFormat)
        self.lang_pref = self.cfg.value('lang', 'auto')
        LANG = resolve_lang(self.lang_pref)
        self.media = Media()
        self.media.changed.connect(self._media_changed)
        self.files = ThemeFiles()
        self.S = {
            'variants': {}, 'headers': {}, 'cur': '', 'sel': -1, 'undo': [], 'redo': [], 'dirty': False,
            'tool': 'select', 'zoom': 0, 'folder_name': '',
            'opt': {'grid': True, 'snap': True, 'crt': False, 'crti': False, 'text': False, 'anim': True},
            'collapsed': {'Effects', 'Scrolling', 'Other keys', 'Advanced conditions'},
        }
        self.space_down = False
        self.flashing = False
        self.colors = UI_THEMES['dark']
        self.ui_name = 'dark'
        self._tr = []            # (function) that set the texts of the static interface in the current language
        self._icons = []         # (button, icon name, transform) recolored with the interface theme
        self.rect_inputs = []
        self.images_list, self.fonts_list = [], []
        self.tmpdir = tempfile.mkdtemp(prefix='frontier_theme_')
        self.session_path = os.path.join(config_dir(), 'session.json')
        self.last_session = None
        self._sess_sig = ''
        self.confirm = self._confirm   # replaced by the tests
        self.alert = self._alert

        self.setWindowTitle('Frontier MRTE[*]')
        self.resize(1440, 900)
        self.setAcceptDrops(True)
        self._build()
        self.set_ui(self.cfg.value('ui', 'dark'), persist=False)
        self.retranslate()
        self.refresh_all()
        self._load_last()

        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(True)
        self.flash_timer.timeout.connect(self._end_flash)
        self.session_timer = QTimer(self)
        self.session_timer.timeout.connect(self.session_tick)
        self.session_timer.start(4000)
        QApplication.instance().focusChanged.connect(self._focus_changed)

    # ------------------------------------------------------------------
    # small helpers
    def T(self, setter, text, *a):
        """Sets a text of the static interface now and every time the language changes."""
        f = lambda: setter(tx(text, *a))
        self._tr.append(f)
        f()

    def ico(self, button, name, transform=None):
        self._icons.append((button, name, transform))
        button.setIcon(make_icon(name, self.colors['text'], self.colors['accent_t'], transform=transform))

    def theme(self):
        return self.S['variants'].get(self.S['cur'])

    def selected(self):
        th = self.theme()
        return th['elements'][self.S['sel']] if th and 0 <= self.S['sel'] < len(th['elements']) else None

    def sample_vars(self):
        return parse_sample(self.sample.toPlainText())

    def _confirm(self, msg):
        return QMessageBox.question(self, 'Frontier MRTE', msg) == QMessageBox.StandardButton.Yes

    def _alert(self, msg):
        QMessageBox.warning(self, 'Frontier MRTE', msg)

    def discard_ok(self):
        return not (self.theme() and self.S['dirty']) or self.confirm(tx('Discard the changes?'))

    # ------------------------------------------------------------------
    # interface
    def _build(self):
        # menu bar: logo, menus, theme name, where Save writes, Open, Save
        top = QWidget()
        top.setObjectName('menubar')
        top.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(8, 2, 8, 2)
        tl.setSpacing(6)
        self.logo = QLabel()
        self.logo.setContentsMargins(0, 0, 8, 0)
        tl.addWidget(self.logo)
        # menus: on macOS in the system menu bar (a QMenuBar without a parent is the one of the
        # application), elsewhere buttons with a menu in the top bar
        self.menus = {}
        self.native_mb = QMenuBar() if IS_MAC else None
        for name in ('File', 'Edit', 'View', 'Variant', 'Help'):
            m = QMenu(self)
            m.aboutToShow.connect(lambda m=m, n=name: self._fill_menu(m, n))
            self.menus[name] = m
            if IS_MAC:
                self.native_mb.addMenu(m)
                self.T(m.setTitle, name)
                continue
            b = QToolButton()
            b.setObjectName('menubtn')
            b.setMenu(m)
            b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.T(b.setText, name)
            tl.addWidget(b)
        tl.addStretch(1)
        self.doc_title = QLabel()
        self.save_mode = QLabel()
        self.save_mode.setProperty('pill', '1')
        self.btn_open = QPushButton()
        self.T(self.btn_open.setText, 'Open folder')
        self.T(self.btn_open.setToolTip, 'Open a theme folder (theme.ini, pictures, fonts)  Ctrl+O')
        self.ico(self.btn_open, 'folder')
        self.btn_open.clicked.connect(self.open_folder)
        self.btn_save = QPushButton()
        self.btn_save.setProperty('primary', '1')
        self.T(self.btn_save.setText, 'Save')
        self.ico(self.btn_save, 'save')
        self.btn_save.clicked.connect(self.smart_save)
        for w in (self.doc_title, self.save_mode, self.btn_open, self.btn_save):
            tl.addWidget(w)
        self.setMenuWidget(top)

        # actions with shortcuts (also in the menus)
        def act(text, fn, *keys):
            a = QAction(self)
            a.triggered.connect(fn)
            if keys:
                a.setShortcuts([QKeySequence(k) for k in keys])
            a.setData(text)
            self.addAction(a)
            return a
        self.A = {
            'open': act('Open folder…', self.open_folder, 'Ctrl+O'),
            'save': act('Save', self.smart_save, 'Ctrl+S'),
            'undo': act('Undo', self.undo, 'Ctrl+Z'),
            'redo': act('Redo', self.redo, 'Ctrl+Shift+Z', 'Ctrl+Y'),
            'dup': act('Duplicate layer', self.duplicate, 'Ctrl+D'),
            'fwd': act('Bring forward', lambda: self.move(1), 'Ctrl+]'),
            'back': act('Send backward', lambda: self.move(-1), 'Ctrl+['),
            'zin': act('Zoom in', lambda: self.zoom_by(1), 'Ctrl++', 'Ctrl+='),
            'zout': act('Zoom out', lambda: self.zoom_by(-1), 'Ctrl+-'),
            'fit': act('Fit on screen', lambda: self.set_zoom(0), 'Ctrl+0'),
            'z100': act('100%', lambda: self.set_zoom(1), 'Ctrl+1'),
            'grid': act('Show grid', lambda: self.set_opt('grid', not self.S['opt']['grid']), "Ctrl+'"),
        }

        if IS_MAC:
            # an empty menu is not shown in the system bar: filled now, again when it opens
            for n, m in self.menus.items():
                self._fill_menu(m, n)

        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # options bar
        ob = QWidget()
        ob.setObjectName('optbar')
        ob.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        ob.setFixedHeight(36)
        ol = QHBoxLayout(ob)
        ol.setContentsMargins(10, 0, 10, 0)
        ol.setSpacing(4)
        self.tool_icon = QLabel()
        self.tool_name = QLabel()
        self.tool_name.setMinimumWidth(80)
        self.tool_name.setStyleSheet('font-weight: bold')
        ol.addWidget(self.tool_icon)
        ol.addWidget(self.tool_name)
        ol.addWidget(hsep())
        seg = QWidget()
        sl = QHBoxLayout(seg)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        self.fmt_btns = {}
        for f43, label, tip in ((False, '16:9', '16:9 screens: theme.ini, detail.ini, screensaver.ini'),
                                (True, '4:3', '4:3 screens (CRT): theme_43.ini, detail_43.ini, screensaver_43.ini. If the file does not exist yet it is made from the 16:9 one')):
            b = QToolButton()
            b.setText(label)
            b.setProperty('seg', '1')
            b.setCheckable(True)
            self.T(b.setToolTip, tip)
            b.clicked.connect(lambda _=False, f=f43: self._fmt_clicked(f))
            sl.addWidget(b)
            self.fmt_btns[f43] = b
        ol.addWidget(seg)
        self.btn_screen = QToolButton()
        self.btn_screen.setProperty('dd', '1')
        self.btn_screen.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.T(self.btn_screen.setToolTip, 'Which screen of the theme you are editing: game list, detail, screensaver')
        sm = QMenu(self.btn_screen)
        sm.aboutToShow.connect(lambda: self._fill_items(sm, self.screen_items()))
        self.btn_screen.setMenu(sm)
        ol.addWidget(self.btn_screen)
        self.cur_file = QLabel()
        self.cur_file.setProperty('dim', '1')
        ol.addWidget(self.cur_file)
        self.btn_make43 = QToolButton()
        self.T(self.btn_make43.setText, 'Make 4:3')
        self.T(self.btn_make43.setToolTip, 'Makes the 4:3 variant (theme_43.ini, detail_43.ini...) adapting the current 16:9 one: x and widths ×0.75')
        self.btn_make43.clicked.connect(self.make_43)
        ol.addWidget(self.btn_make43)
        ol.addWidget(hsep())
        lbl = QLabel()
        lbl.setProperty('dim', '1')
        self.T(lbl.setText, 'Align to canvas')
        ol.addWidget(lbl)
        self.align_btns = []
        flip, rot90, rotm90 = QTransform().scale(-1, 1), QTransform().rotate(90), QTransform().rotate(-90)
        for mode, icon, tr, tip in (('l', 'al', None, 'Align left'), ('c', 'ac', None, 'Center horizontally'), ('r', 'al', flip, 'Align right'),
                                    ('t', 'al', rot90, 'Align top'), ('m', 'ac', rot90, 'Center vertically'), ('b', 'al', rotm90, 'Align bottom')):
            b = QToolButton()
            self.ico(b, icon, tr)
            self.T(b.setToolTip, tip)
            b.clicked.connect(lambda _=False, m=mode: self.align_to(m))
            ol.addWidget(b)
            self.align_btns.append(b)
        ol.addWidget(hsep())
        self.opt_btns = {}
        for key, label, tip in (('grid', 'Grid', "Show the 32 px grid  Ctrl+'"), ('snap', 'Snap 8', 'Snap to an 8 px grid (Shift while dragging = off)'),
                                ('crt', '240p preview', 'Shows it as on a 240p CRT: lines halved and doubled'),
                                ('crti', '240i preview', 'Shows it as on a 240i CRT: 480 lines drawn as two alternating fields, so thin horizontal lines flicker'),
                                ('anim', 'Animate GIF', 'Plays the animated GIFs in the preview (off = first frame, lighter on the computer)'),
                                ('text', 'Text layout', 'As with Frontier Settings > Themes > Text layout ON: elements with layout=text instead of layout=media')):
            b = QToolButton()
            b.setProperty('tg', '1')
            b.setCheckable(True)
            self.T(b.setText, label)
            self.T(b.setToolTip, tip)
            b.clicked.connect(lambda _=False, k=key: self.set_opt(k, not self.S['opt'][k]))
            ol.addWidget(b)
            self.opt_btns[key] = b
        ol.addStretch(1)
        self.btn_undo, self.btn_redo, self.btn_help = QToolButton(), QToolButton(), QToolButton()
        self.ico(self.btn_undo, 'undo')
        self.ico(self.btn_redo, 'undo', flip)
        self.T(self.btn_undo.setToolTip, 'Undo  Ctrl+Z')
        self.T(self.btn_redo.setToolTip, 'Redo  Ctrl+Shift+Z')
        self.btn_help.setText('?')
        self.btn_help.setStyleSheet('font-weight: bold')
        self.T(self.btn_help.setToolTip, 'Help and shortcuts')
        self.btn_undo.clicked.connect(self.undo)
        self.btn_redo.clicked.connect(self.redo)
        self.btn_help.clicked.connect(lambda: self.show_html('help'))
        for b in (self.btn_undo, self.btn_redo, self.btn_help):
            ol.addWidget(b)
        v.addWidget(ob)

        # work area: toolbox | canvas | panels
        work = QSplitter(Qt.Orientation.Horizontal)
        work.setHandleWidth(1)
        tools = QWidget()
        tools.setObjectName('tools')
        tools.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tools.setFixedWidth(44)
        tl = QVBoxLayout(tools)
        tl.setContentsMargins(5, 8, 5, 8)
        tl.setSpacing(4)
        self.tool_btns = {}
        for t in TOOLS:
            if t is None:
                tl.addWidget(QFrame(), 0)
                continue
            b = QToolButton()
            b.setProperty('tool', '1')
            b.setCheckable(True)
            b.setIconSize(QSize(18, 18))
            self.ico(b, t[0])
            self.T(b.setToolTip, t[3])
            b.clicked.connect(lambda _=False, n=t[0]: self.set_tool(n))
            tl.addWidget(b)
            self.tool_btns[t[0]] = b
        tl.addStretch(1)

        center = QWidget()
        cv = QVBoxLayout(center)
        cv.setContentsMargins(0, 0, 0, 0)
        self.center_stack = QStackedWidget()
        cv.addWidget(self.center_stack)
        # welcome page
        wel = QWidget()
        wel.setObjectName('welcome')
        wel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        wl = QVBoxLayout(wel)
        wl.addStretch(1)
        h2 = QLabel()
        h2.setStyleSheet('font-size: 20px; font-weight: 600')
        h2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.T(h2.setText, 'No theme open')
        wl.addWidget(h2)
        p1 = QLabel()
        p1.setProperty('dim', '1')
        p1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p1.setWordWrap(True)
        self.T(p1.setText, 'Start a new theme, open the folder of one you already have, or look at the example.')
        wl.addWidget(p1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.w_new, self.w_open, self.w_last, self.w_session, self.w_example = (QPushButton() for _ in range(5))
        self.w_new.setProperty('primary', '1')
        self.T(self.w_new.setText, 'New theme…')
        self.T(self.w_open.setText, 'Open folder…')
        self.T(self.w_example.setText, 'Example theme')
        self.w_new.clicked.connect(self.new_theme_in_folder)
        self.w_open.clicked.connect(self.open_folder)
        self.w_last.clicked.connect(self.reopen_last)
        self.w_session.clicked.connect(self.restore_session)
        self.w_example.clicked.connect(self.open_example)
        for b in (self.w_new, self.w_open, self.w_last, self.w_session, self.w_example):
            btns.addWidget(b)
        btns.addStretch(1)
        wl.addSpacing(14)
        wl.addLayout(btns)
        wl.addSpacing(14)
        p2 = QLabel()
        p2.setProperty('dim', '1')
        p2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.T(p2.setText, 'You can also drop a theme folder here.')
        wl.addWidget(p2)
        wl.addStretch(2)
        self.center_stack.addWidget(wel)
        # stage
        self.stage = QScrollArea()
        self.stage.setObjectName('stage')
        self.stage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stage.setWidgetResizable(False)
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(26, 26, 26, 26)
        self.canvas = Canvas(self)
        hl.addWidget(self.canvas)
        self.stage.setWidget(holder)
        self.stage.viewport().installEventFilter(self)
        self.center_stack.addWidget(self.stage)
        self.drop_label = QLabel(center)
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.T(self.drop_label.setText, 'Drop the theme folder here')
        self.drop_label.hide()

        # panels
        right = QSplitter(Qt.Orientation.Vertical)
        right.setObjectName('right')
        right.setHandleWidth(6)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        # layers
        lp = QWidget()
        ll = QVBoxLayout(lp)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        self.layers = LayerTree(self)
        self.layers.itemClicked.connect(self._layer_clicked)
        self.layers.itemDoubleClicked.connect(self._layer_dblclicked)
        self.layers.itemChanged.connect(self._layer_renamed)
        ll.addWidget(self.layers)
        lf = QWidget()
        lf.setObjectName('pfoot')
        lf.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lfl = QHBoxLayout(lf)
        lfl.setContentsMargins(6, 3, 6, 3)
        self.b_add, self.b_dup, self.b_up, self.b_down, self.b_del = (QToolButton() for _ in range(5))
        for b, icon, tip, fn in ((self.b_add, 'plus', 'New layer', self._add_menu), (self.b_dup, 'dup', 'Duplicate  Ctrl+D', self.duplicate),
                                 (self.b_up, 'up', 'Bring forward  Ctrl+]', lambda: self.move(1)), (self.b_down, 'down', 'Send backward  Ctrl+[', lambda: self.move(-1)),
                                 (self.b_del, 'trash', 'Delete  Del', self.remove)):
            self.ico(b, icon)
            self.T(b.setToolTip, tip)
            b.clicked.connect(fn)
            lfl.addWidget(b)
            if b is self.b_down:
                lfl.addStretch(1)
        ll.addWidget(lf)
        self.tabs.addTab(lp, '')
        # assets
        ap = QWidget()
        al = QVBoxLayout(ap)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(0)
        self.img_hint = QLabel()
        self.img_hint.setProperty('dim', '1')
        self.img_hint.setWordWrap(True)
        self.img_hint.setContentsMargins(10, 8, 10, 4)
        al.addWidget(self.img_hint)
        self.assets = QListWidget()
        self.assets.setIconSize(QSize(64, 48))
        self.assets.itemDoubleClicked.connect(self._asset_dblclicked)
        al.addWidget(self.assets)
        af = QWidget()
        af.setObjectName('pfoot')
        af.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        afl = QHBoxLayout(af)
        afl.setContentsMargins(6, 3, 6, 3)
        for label, tip, kind in (('Picture', 'Copies pictures to the img/ folder of the theme', 'img'),
                                 ('Video', 'Copies videos (.mp4, .mkv, .webm...) to the video/ folder of the theme', 'video'),
                                 ('Font', 'Copies fonts (.ttf, .otf) to the fonts/ folder of the theme', 'fonts')):
            b = QPushButton()
            self.ico(b, 'plus')
            self.T(b.setText, label)
            self.T(b.setToolTip, tip)
            b.clicked.connect(lambda _=False, k=kind: self.pick_assets(k))
            afl.addWidget(b)
        afl.addStretch(1)
        al.addWidget(af)
        self.tabs.addTab(ap, '')
        # sample data
        sp = QWidget()
        spl = QVBoxLayout(sp)
        spl.setContentsMargins(8, 6, 8, 8)
        sh = QLabel()
        sh.setProperty('dim', '1')
        sh.setWordWrap(True)
        self.T(sh.setText, 'Variables for the preview (name=value). The media @snap, @box… are placeholders; empty = missing media.')
        spl.addWidget(sh)
        self.sample = QPlainTextEdit(DEFAULT_SAMPLE)
        self.sample.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.sample.setFont(mono)
        self.sample.textChanged.connect(lambda: (self.render(), self.refresh_list()))
        spl.addWidget(self.sample)
        self.tabs.addTab(sp, '')
        self._tr.append(lambda: [self.tabs.setTabText(1, tx('Assets')), self.tabs.setTabText(2, tx('Sample data'))])
        right.addWidget(self.tabs)
        # properties
        bot = QWidget()
        bl = QVBoxLayout(bot)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        ph = QTabWidget()
        ph.setDocumentMode(True)
        self.props_scroll = QScrollArea()
        self.props_scroll.setObjectName('propsScroll')
        self.props_scroll.setWidgetResizable(True)
        self.props_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ph.addTab(self.props_scroll, '')
        self._tr.append(lambda: ph.setTabText(0, tx('Properties')))
        bl.addWidget(ph)
        self.keyinfo = QLabel()
        self.keyinfo.setObjectName('keyinfo')
        self.keyinfo.setWordWrap(True)
        self.keyinfo.setMinimumHeight(34)
        bl.addWidget(self.keyinfo)
        right.addWidget(bot)
        right.setSizes([330, 520])

        work.addWidget(tools)
        work.addWidget(center)
        work.addWidget(right)
        work.setStretchFactor(1, 1)
        work.setCollapsible(0, False)
        work.setSizes([44, 1060, 336])
        v.addWidget(work, 1)

        # status bar
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.lbl_status = QLabel()
        self.lbl_pos = QLabel()
        self.lbl_sel = QLabel()
        sb.addWidget(self.lbl_status, 1)
        sb.addWidget(self.lbl_pos)
        sb.addWidget(self.lbl_sel)
        zw = QWidget()
        zl = QHBoxLayout(zw)
        zl.setContentsMargins(0, 0, 0, 0)
        zl.setSpacing(2)
        bzo, bzi = QToolButton(), QToolButton()
        bzo.setText('−')
        bzi.setText('+')
        self.T(bzo.setToolTip, 'Zoom out  Ctrl+-')
        self.T(bzi.setToolTip, 'Zoom in  Ctrl++')
        bzo.clicked.connect(lambda: self.zoom_by(-1))
        bzi.clicked.connect(lambda: self.zoom_by(1))
        self.zoom_box = QComboBox()
        for z in [0] + ZOOMS:
            self.zoom_box.addItem('', z)
        self._tr.append(lambda: [self.zoom_box.setItemText(i, tx('Fit') if z == 0 else '%d%%' % round(z * 100)) for i, z in enumerate([0] + ZOOMS)])
        self.zoom_box.activated.connect(lambda i: self.set_zoom(self.zoom_box.itemData(i)))
        self.zoom_pct = QLabel()
        self.zoom_pct.setMinimumWidth(42)
        for w in (bzo, self.zoom_box, bzi, self.zoom_pct):
            zl.addWidget(w)
        sb.addPermanentWidget(zw)
        sw = QWidget()
        swl = QHBoxLayout(sw)
        swl.setContentsMargins(6, 0, 6, 0)
        swl.setSpacing(6)
        self.sw_btns = {}
        for n, tip in (('light', 'Light'), ('medium', 'Medium gray'), ('dark', 'Dark gray')):
            b = QToolButton()
            b.setProperty('sw', n)
            b.setCheckable(True)
            self.T(b.setToolTip, tip)
            b.clicked.connect(lambda _=False, n=n: self.set_ui(n))
            swl.addWidget(b)
            self.sw_btns[n] = b
        self.T(sw.setToolTip, 'Interface theme (Shift+F1 darker, Shift+F2 lighter)')
        sb.addPermanentWidget(sw)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        c = self.drop_label.parentWidget()
        self.drop_label.setGeometry(0, 0, c.width(), c.height())

    def eventFilter(self, obj, ev):
        if obj is self.stage.viewport() and ev.type() == QEvent.Type.Resize and self.S['zoom'] == 0:
            QTimer.singleShot(0, self.render)
        return False

    def retranslate(self):
        for f in self._tr:
            f()
        self.setWindowTitle(tx('Frontier MRTE: theme editor') + '[*]')
        self.build_tools()

    def set_lang(self, pref):
        global LANG
        self.lang_pref = pref
        self.cfg.setValue('lang', pref)
        LANG = resolve_lang(pref)
        self.retranslate()
        self.refresh_all()

    def set_ui(self, name, persist=True):
        if name not in UI_THEMES:
            name = 'dark'
        self.ui_name = name
        self.colors = apply_ui_theme(QApplication.instance(), name)
        for n, b in self.sw_btns.items():
            b.setChecked(n == name)
        for b, icon, tr in self._icons:
            b.setIcon(make_icon(icon, self.colors['text'], self.colors['accent_t'], transform=tr))
        logo = LOGO_LIGHT if name == 'light' else LOGO_DARK
        pm = QPixmap()
        pm.loadFromData(QByteArray.fromBase64(logo.encode()))
        self.logo.setPixmap(pm.scaledToHeight(22, Qt.TransformationMode.SmoothTransformation))
        self.logo.setToolTip('Frontier MRTE theme editor ' + APP_VERSION)
        self.drop_label.setStyleSheet('background: rgba(47,134,235,0.22); border: 2px dashed %s; font-size: 18px;' % self.colors['accent'])
        if persist:
            self.cfg.setValue('ui', name)
        if hasattr(self, 'tool_icon'):
            self.set_tool(self.S['tool'])
            self.refresh_list()
            self.refresh_assets()

    def cycle_ui(self, d):
        i = UI_ORDER.index(self.ui_name)
        self.set_ui(UI_ORDER[max(0, min(len(UI_ORDER) - 1, i + d))])

    # ---- menus
    def _fill_items(self, menu, items):
        menu.clear()
        for it in items:
            if it == '-':
                menu.addSeparator()
                continue
            if 'head' in it:
                a = menu.addAction(tx(it['head']))
                a.setEnabled(False)
                f = a.font()
                f.setBold(True)
                a.setFont(f)
                continue
            if 'action' in it:
                a = it['action']
                a.setText(tx(a.data()) + (('\t' + it['key']) if it.get('key') and not IS_MAC else ''))
                a.setEnabled(not it.get('disabled'))
                menu.addAction(a)
                continue
            text = it['label'] + (('\t' + it['key']) if it.get('key') and not IS_MAC else '')
            a = menu.addAction(text)
            if it.get('check') is not None:
                a.setCheckable(True)
                a.setChecked(bool(it['check']))
            a.setEnabled(not it.get('disabled'))
            a.triggered.connect(it['run'])

    def _fill_menu(self, menu, name):
        S, A = self.S, self.A
        if name == 'File':
            last = self.cfg.value('lastDir', '')
            items = [{'label': tx('New theme…'), 'run': lambda: self.discard_ok() and self.new_theme_in_folder(ask=False)},
                     {'action': A['open'], 'key': 'Ctrl+O'}]
            if last and os.path.isfile(os.path.join(last, 'theme.ini')):
                items.append({'label': tx('Reopen "{0}"', os.path.basename(last)), 'run': self.reopen_last})
            if self.last_session:
                items.append({'label': tx('Restore unsaved work'), 'run': self.restore_session})
            items += [{'label': tx('Example theme'), 'run': self.open_example},
                      {'label': tx('Load .ini…'), 'run': self.pick_ini}, '-',
                      {'action': A['save'], 'key': 'Ctrl+S', 'disabled': not self.theme()},
                      {'label': tx('Save as ZIP…'), 'run': self.save_zip, 'disabled': not self.theme()}, '-',
                      {'label': tx('Add pictures…'), 'run': lambda: self.pick_assets('img'), 'disabled': not self.theme()},
                      {'label': tx('Add videos…'), 'run': lambda: self.pick_assets('video'), 'disabled': not self.theme()},
                      {'label': tx('Add fonts…'), 'run': lambda: self.pick_assets('fonts'), 'disabled': not self.theme()}]
        elif name == 'Edit':
            items = [{'action': A['undo'], 'key': 'Ctrl+Z', 'disabled': not S['undo']},
                     {'action': A['redo'], 'key': 'Ctrl+Shift+Z', 'disabled': not S['redo']}, '-',
                     {'action': A['dup'], 'key': 'Ctrl+D', 'disabled': S['sel'] < 0},
                     {'label': tx('Delete layer'), 'run': self.remove, 'key': 'Del', 'disabled': S['sel'] < 0}, '-',
                     {'action': A['fwd'], 'key': 'Ctrl+]', 'disabled': S['sel'] < 0},
                     {'action': A['back'], 'key': 'Ctrl+[', 'disabled': S['sel'] < 0}, '-',
                     {'label': tx('Deselect'), 'run': lambda: self.select(-1), 'key': 'Esc', 'disabled': S['sel'] < 0}]
        elif name == 'View':
            o = S['opt']
            items = [{'action': A['zin'], 'key': 'Ctrl++'}, {'action': A['zout'], 'key': 'Ctrl+-'},
                     {'action': A['fit'], 'key': 'Ctrl+0'}, {'action': A['z100'], 'key': 'Ctrl+1'}, '-',
                     {'label': tx('Show grid'), 'run': lambda: self.set_opt('grid', not o['grid']), 'check': o['grid'], 'key': "Ctrl+'"},
                     {'label': tx('Snap to grid (8 px)'), 'run': lambda: self.set_opt('snap', not o['snap']), 'check': o['snap']},
                     {'label': tx('240p CRT preview'), 'run': lambda: self.set_opt('crt', not o['crt']), 'check': o['crt']},
                     {'label': tx('240i CRT preview'), 'run': lambda: self.set_opt('crti', not o['crti']), 'check': o['crti']},
                     {'label': tx('Text layout'), 'run': lambda: self.set_opt('text', not o['text']), 'check': o['text']},
                     {'label': tx('Animate GIFs'), 'run': lambda: self.set_opt('anim', not o['anim']), 'check': o['anim']}, '-',
                     {'label': tx('Interface: Light'), 'run': lambda: self.set_ui('light'), 'check': self.ui_name == 'light'},
                     {'label': tx('Interface: Medium gray'), 'run': lambda: self.set_ui('medium'), 'check': self.ui_name == 'medium'},
                     {'label': tx('Interface: Dark gray'), 'run': lambda: self.set_ui('dark'), 'check': self.ui_name == 'dark'}, '-',
                     {'head': 'Language'},
                     {'label': tx('Auto (follows the system)'), 'run': lambda: self.set_lang('auto'), 'check': self.lang_pref == 'auto'},
                     {'label': 'Italiano', 'run': lambda: self.set_lang('it'), 'check': self.lang_pref == 'it'},
                     {'label': 'English', 'run': lambda: self.set_lang('en'), 'check': self.lang_pref == 'en'}]
        elif name == 'Variant':
            items = self.variant_menu()
        else:
            items = [{'label': tx('How to use it and shortcuts'), 'run': lambda: self.show_html('help')},
                     {'label': tx("What's new"), 'run': lambda: self.show_html('news')}]
        self._fill_items(menu, items)

    def show_html(self, which):
        lang = LANG if LANG in HELP else 'en'
        body = HELP[lang] if which == 'help' else NEWS[lang] % APP_VERSION
        dlg = QDialog(self)
        dlg.setWindowTitle(tx('How to use it and shortcuts') if which == 'help' else tx("What's new"))
        dlg.resize(720, 640)
        lay = QVBoxLayout(dlg)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml(HTML_STYLE.format(**self.colors) + body)
        lay.addWidget(tb)
        row = QHBoxLayout()
        row.addStretch(1)
        b = QPushButton(tx('Close'))
        b.clicked.connect(dlg.accept)
        row.addWidget(b)
        lay.addLayout(row)
        dlg.open()
        self._dlg = dlg

    # ---- tools and options
    def build_tools(self):
        for t in TOOLS:
            if t:
                self.tool_btns[t[0]].setToolTip(tx(t[3]))
        self.set_tool(self.S['tool'] or 'select')

    def set_tool(self, t):
        self.S['tool'] = t
        for n, b in self.tool_btns.items():
            b.setChecked(n == t)
        d = next((x for x in TOOLS if x and x[0] == t), None)
        self.tool_icon.setPixmap(icon_pixmap(t, self.colors['text']))
        self.tool_name.setText(tx(d[2]) if d else t)
        self.canvas.setCursor(Qt.CursorShape.ArrowCursor if t == 'select' else Qt.CursorShape.CrossCursor)

    def align_to(self, mode):
        el = self.selected()
        if not el:
            return
        self.snapshot()
        x, y, w, h = parse_rect(el['props'].get('rect'))
        bw, bh = self.canvas.bw, self.canvas.bh
        if mode == 'l':
            x = 0
        elif mode == 'c':
            x = round((bw - w) / 2)
        elif mode == 'r':
            x = bw - w
        elif mode == 't':
            y = 0
        elif mode == 'm':
            y = round((bh - h) / 2)
        elif mode == 'b':
            y = bh - h
        el['props']['rect'] = join_rect([x, y, w, h])
        self.render()
        self.update_rect_fields()

    def set_opt(self, k, v):
        o = self.S['opt']
        o[k] = v
        if v and k == 'crt':   # 240p and 240i exclude each other
            o['crti'] = False
        if v and k == 'crti':
            o['crt'] = False
        self.sync_toggles()
        self.render()
        if k == 'text':
            self.refresh_list()
            self.refresh_props()

    def sync_toggles(self):
        for k, b in self.opt_btns.items():
            b.setChecked(bool(self.S['opt'][k]))
        for b in self.align_btns:
            b.setEnabled(self.S['sel'] >= 0)

    # ---- zoom
    def set_zoom(self, z):
        self.S['zoom'] = z
        self.render()

    def zoom_by(self, d):
        cur = self.canvas.scale
        if d > 0:
            nxt = next((z for z in ZOOMS if z > cur + 0.001), ZOOMS[-1])
        else:
            nxt = next((z for z in reversed(ZOOMS) if z < cur - 0.001), ZOOMS[0])
        self.set_zoom(nxt)

    def update_zoom_ui(self):
        i = self.zoom_box.findData(self.S['zoom'])
        self.zoom_box.setCurrentIndex(i if i >= 0 else 0)
        self.zoom_pct.setText('%d%%' % round(self.canvas.scale * 100))

    # ------------------------------------------------------------------
    # undo
    def state_string(self):
        S = self.S
        return json.dumps({'variants': S['variants'], 'cur': S['cur'], 'sel': S['sel']})

    def snapshot(self):
        S = self.S
        S['undo'].append(self.state_string())
        if len(S['undo']) > 100:
            S['undo'].pop(0)
        S['redo'] = []
        S['dirty'] = True

    def _restore(self, s):
        o = json.loads(s)
        self.S.update(variants=o['variants'], cur=o['cur'], sel=o['sel'])
        self.refresh_all()

    def undo(self):
        if self.S['undo']:
            s = self.S['undo'].pop()
            self.S['redo'].append(self.state_string())
            self._restore(s)

    def redo(self):
        if self.S['redo']:
            s = self.S['redo'].pop()
            self.S['undo'].append(self.state_string())
            self._restore(s)

    # ------------------------------------------------------------------
    # refresh
    def render(self):
        th = self.theme()
        self.center_stack.setCurrentIndex(1 if th else 0)
        if th:
            self.canvas.relayout()
            self.canvas.rev += 1
            self.canvas.update()
        else:
            self.update_welcome()
        self.update_status()
        self.update_zoom_ui()

    def refresh_all(self):
        self.refresh_variants()
        self.refresh_datalists()
        self.refresh_assets()
        self.refresh_list()
        self.refresh_props()
        self.sync_toggles()
        self.render()

    def _media_changed(self):
        self.render()
        self.refresh_assets()

    def update_status(self):
        th, S = self.theme(), self.S
        self.save_mode.setVisible(bool(th))
        folder = self.files.folder
        if th:
            dot = '<span style="color:%s">●</span> ' % ('#3fb950' if folder else '#e5a000')
            self.save_mode.setText(dot + (tx('Writing in the theme folder') if folder else tx('Not in a folder yet')))
            self.save_mode.setToolTip(tx('Save writes straight into the theme folder, and pictures, videos and fonts are copied into it.') if folder
                                      else tx('Save asks for the folder of the theme and writes the .ini files, pictures, videos and fonts into it.'))
        if not th:
            self.lbl_status.setText(tx('No theme open'))
            self.doc_title.setText('')
            self.lbl_sel.setText('')
        else:
            if not self.flashing:
                self.lbl_status.setText('%s · %s · base %d×%d' % (S['folder_name'] or tx('new theme'), S['cur'], self.canvas.bw, self.canvas.bh)
                                        + (' · ' + tx('modified') if S['dirty'] else ''))
            self.doc_title.setText((S['folder_name'] or tx('untitled theme')) + (' •' if S['dirty'] else ''))
            el = self.selected()
            if not (self.canvas.drag and self.canvas.drag['mode'] == 'rotate'):
                self.lbl_sel.setText('[%s] %s %s' % (el['name'], el['props'].get('type') or 'rect', ', '.join(map(str, parse_rect(el['props'].get('rect'))))) if el else '')
        self.btn_save.setToolTip(tx('Writes all the .ini files in the theme folder  Ctrl+S') if folder else tx('Asks for the folder of the theme, then writes everything into it  Ctrl+S'))
        self.btn_save.setEnabled(bool(th))
        self.btn_undo.setEnabled(bool(S['undo']))
        self.btn_redo.setEnabled(bool(S['redo']))
        self.setWindowModified(bool(th) and S['dirty'])

    def flash(self, msg, *a):
        self.flashing = True
        self.lbl_status.setText(tx(msg, *a))
        self.flash_timer.start(2800)

    def _end_flash(self):
        self.flashing = False
        self.update_status()

    def update_welcome(self):
        last = self.cfg.value('lastDir', '')
        ok = bool(last) and os.path.isfile(os.path.join(last, 'theme.ini'))
        self.w_last.setVisible(ok)
        if ok:
            self.w_last.setText(tx('Reopen "{0}"', os.path.basename(last)))
        self.w_session.setVisible(bool(self.last_session))
        if self.last_session:
            r = self.last_session
            name = r.get('name') or (r['variants'].get('theme.ini') or {'global': {}})['global'].get('name') or 'theme'
            self.w_session.setText(tx('Restore unsaved work: "{0}" ({1})', name, time.strftime('%Y-%m-%d %H:%M', time.localtime(r.get('when', 0)))))

    # ---- layers
    def select(self, i):
        self.S['sel'] = i
        self.refresh_list()
        self.refresh_props()
        self.sync_toggles()
        self.render()

    def refresh_list(self):
        tree = self.layers
        tree.blockSignals(True)
        tree.clear()
        th = self.theme()
        n = len(th['elements']) if th else 0
        self.tabs.setTabText(0, tx('Layers') + ('  %d' % n if th else ''))
        if not th:
            tree.blockSignals(False)
            return
        variables = self.sample_vars()
        c = self.colors
        cur = None
        for i in range(n - 1, -1, -1):
            el = th['elements'][i]
            t = (el['props'].get('type') or 'rect').lower()
            badge = el['props'].get('layout') or ('if' if el['props'].get('if') or el['props'].get('ifnot') else '')
            it = QTreeWidgetItem(['', el['name'], badge])
            it.setData(0, Qt.ItemDataRole.UserRole, i)
            it.setIcon(0, make_icon('eyeoff' if el.get('hid') else 'eye', c['text'], c['sel_t']))
            it.setToolTip(0, tx('Show / hide in the editor (it is still saved)'))
            it.setIcon(1, make_icon(t if t in TYPES else 'rect', c['dim'] if el.get('hid') else c['text'], c['sel_t']))
            it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDragEnabled)
            if el.get('hid') or not visible(el['props'], variables, self.S['opt']['text']):
                it.setForeground(1, QColor(c['dim']))
            if badge:
                it.setForeground(2, QColor(c['dim']))
            tree.addTopLevelItem(it)
            if i == self.S['sel']:
                cur = it
        g = QTreeWidgetItem(['', tx('Theme settings'), '[theme]'])
        g.setData(0, Qt.ItemDataRole.UserRole, -1)
        g.setIcon(0, make_icon('lock', c['dim'], c['sel_t']))
        g.setForeground(2, QColor(c['dim']))
        g.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        tree.addTopLevelItem(g)
        if self.S['sel'] == -1:
            cur = g
        if cur is not None:
            tree.setCurrentItem(cur)
            cur.setSelected(True)
        tree.blockSignals(False)

    def _layer_clicked(self, item, col):
        i = item.data(0, Qt.ItemDataRole.UserRole)
        if col == 0 and i is not None and i >= 0:
            el = self.theme()['elements'][i]
            el['hid'] = not el.get('hid')
            self.refresh_list()
            self.render()
            return
        self.select(i)

    def _layer_dblclicked(self, item, col):
        i = item.data(0, Qt.ItemDataRole.UserRole)
        if i is not None and i >= 0 and col != 0:
            self.layers.editItem(item, 1)

    def _layer_renamed(self, item, col):
        i = item.data(0, Qt.ItemDataRole.UserRole)
        if col != 1 or i is None or i < 0:
            return
        el = self.theme()['elements'][i]
        v = re.sub(r'[\[\]]', '', item.text(1)).strip()
        if v and v != el['name']:
            if any(e is not el and e['name'] == v for e in self.theme()['elements']):
                self.flash('Name already used by another element')
            else:
                self.snapshot()
                el['name'] = v
        QTimer.singleShot(0, lambda: (self.refresh_list(), self.refresh_props(), self.update_status()))

    def reorder(self, a, b, upper_half):
        els = self.theme()['elements']
        to = b + 1 if upper_half else b
        if a == b or a == to:
            return
        self.snapshot()
        item = els.pop(a)
        if a < to:
            to -= 1
        els.insert(to, item)
        self.select(to)

    def _add_menu(self):
        if not self.theme():
            return
        m = QMenu(self)
        for t in TYPES:
            m.addAction(make_icon(t, self.colors['text']), tx(TYPE_NAMES[t])).triggered.connect(lambda _=False, t=t: self.add_element(t))
        m.exec(self.b_add.mapToGlobal(QPoint(0, -m.sizeHint().height())))

    # ---- properties
    def _section(self, box, title):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        head = QToolButton()
        head.setProperty('sec', '1')
        head.setText(tx(title))
        head.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        head.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(10, 8, 10, 4)
        bl.setSpacing(6)
        collapsed = title in self.S['collapsed']
        head.setIcon(QIcon(icon_pixmap('chev' if collapsed else 'chevdown', self.colors['text'], 12)))

        def toggle():
            now = body.isVisible()
            body.setVisible(not now)
            (self.S['collapsed'].add if now else self.S['collapsed'].discard)(title)
            head.setIcon(QIcon(icon_pixmap('chev' if now else 'chevdown', self.colors['text'], 12)))
        head.clicked.connect(toggle)
        v.addWidget(head)
        v.addWidget(body)
        box.addWidget(w)
        if collapsed:
            body.hide()
        return bl

    def _row(self, layout, key, label=None, tip=''):
        row = QWidget()
        row.setProperty('key', key)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        lab = QLabel(label if label is not None else key)
        lab.setProperty('dim', '1')
        lab.setFixedWidth(96)
        lab.setToolTip(tip or tx(KEY_INFO.get(key, key)))
        h.addWidget(lab)
        layout.addWidget(row)
        return row, h

    def field(self, layout, key, value, onchange, color=False, placeholder=''):
        row, h = self._row(layout, key)
        snapped = [False]

        def begin():
            if not snapped[0]:
                self.snapshot()
                snapped[0] = True
        is_color = key in COLOR_KEYS or (key == 'background' and color)
        tip = tx(KEY_INFO[key]) if key in KEY_INFO else ''
        if key in CHOICES:
            inp = self._combo()
            ch = CHOICES[key]
            opts = ch if value in ch or value is None or value == '' else [value] + ch
            vals = [''] + [x for x in opts if x != '']
            for c in vals:
                inp.addItem(c or tx('(default)'), c)
            inp.setCurrentIndex(max(0, vals.index(value) if value in vals else 0))
            inp.activated.connect(lambda i: (self.snapshot(), onchange(inp.itemData(i), False)))
        else:
            inp = QLineEdit(value or '')
            inp.setPlaceholderText(placeholder)
            if (key in FILE_KEYS and not color) or key in FONT_KEYS:
                comp = QCompleter(self.fonts_list if key in FONT_KEYS else self.images_list, inp)
                comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                comp.setFilterMode(Qt.MatchFlag.MatchContains)
                inp.setCompleter(comp)
            edited = [False]

            def on_edit(t):
                begin()
                edited[0] = True
                onchange(t, True)

            def on_done():
                snapped[0] = False
                if edited[0]:
                    edited[0] = False
                    onchange(inp.text(), False)
            inp.textEdited.connect(on_edit)
            inp.editingFinished.connect(on_done)
            inp._on_edit = on_edit
            inp._on_done = on_done
        inp.setToolTip(tip)
        inp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        inp.setMinimumWidth(40)
        h.addWidget(inp, 1)
        if key in VAR_KEYS and isinstance(inp, QLineEdit):
            vb = QToolButton()
            vb.setProperty('vbtn', '1')
            vb.setText('${}')
            vb.setToolTip(tx('Insert a variable'))
            vb.clicked.connect(lambda: self._var_menu(vb, inp, key))
            h.addWidget(vb)
        if is_color:
            cb = QToolButton()
            cb.setFixedSize(28, 22)
            cb.setToolTip(tx('Choose the color'))
            al = AlphaEdit()
            al.setFixedWidth(52)
            al.setAlignment(Qt.AlignmentFlag.AlignRight)
            al.setToolTip(tx('Opacity: 100% solid, 0% invisible (saved as the AA of #RRGGBBAA)'))

            def hex_of():
                return re.match(r'^#?([0-9a-f]{6})([0-9a-f]{2})?$', inp.text().strip(), re.I)

            def sync():
                m = hex_of()
                al.setEnabled(bool(m))
                al.setText('%d%%' % round((int(m.group(2), 16) if m.group(2) else 255) / 255 * 100) if m else '')
                cb.setStyleSheet('QToolButton { background: %s; border: 1px solid %s; border-radius: 4px; }'
                                 % ('#' + m.group(1) if m else 'transparent', self.colors['line2']))

            def set_alpha(commit):
                m = hex_of()
                if not m:
                    return
                pct = max(0, min(100, js_int(al.text()) or 0))
                base = '#' + m.group(1).upper()
                inp.setText(base if pct >= 100 else base + ('%02X' % round(pct * 2.55)))
                onchange(inp.text(), not commit)

            def pick():
                m = hex_of()
                old = inp.text()
                began = [False]
                dlg = QColorDialog(QColor('#' + m.group(1)) if m else QColor(255, 255, 255), self)

                def live(c):
                    if not c.isValid():
                        return
                    if not began[0]:
                        self.snapshot()
                        began[0] = True
                    mm = hex_of()
                    a = mm.group(2) if mm and mm.group(2) else ''
                    inp.setText(c.name().upper() + a.upper())
                    onchange(inp.text(), True)
                    sync()
                dlg.currentColorChanged.connect(live)
                if dlg.exec():
                    live(dlg.selectedColor())
                    onchange(inp.text(), False)
                elif began[0]:
                    inp.setText(old)
                    onchange(old, False)
                    self.S['undo'].pop()
                sync()
            cb.clicked.connect(pick)
            al.textEdited.connect(lambda _: (begin(), set_alpha(False)))
            al.editingFinished.connect(lambda: (snapped.__setitem__(0, False), set_alpha(True), sync()))
            al.stepped.connect(lambda st: (al.setText('%d%%' % max(0, min(100, (js_int(al.text()) or 0) + st))), begin(), set_alpha(False)))
            if isinstance(inp, QLineEdit):
                inp.textChanged.connect(lambda _: sync())
            sync()
            h.addWidget(cb)
            h.addWidget(al)
        return inp

    def _var_menu(self, button, inp, key):
        variables = self.sample_vars()
        groups = {'General': [], 'Game': [], 'Media': []}
        for k in variables:
            groups['Game' if k.startswith('game.') else 'Media' if k.startswith('media.') else 'General'].append(k)
        m = QMenu(self)
        for g in (['Media'] if key == 'src' else list(groups)):
            if not groups[g]:
                continue
            a = m.addAction(tx(g))
            a.setEnabled(False)
            f = a.font()
            f.setBold(True)
            a.setFont(f)
            for name in groups[g]:
                v = variables[name]
                v = tx('(empty)') if v == '' else tx('picture') if v.startswith('@') else v
                m.addAction('${%s}\t%s' % (name, v[:25] + '…' if len(v) > 26 else v)).triggered.connect(
                    lambda _=False, n=name: self.insert_variable(inp, key, n))
        if key == 'src':
            m.addSeparator()
            m.addAction(tx('Theme file… (type img/name.png)')).triggered.connect(lambda: inp.setFocus())
        m.exec(button.mapToGlobal(QPoint(button.width() - m.sizeHint().width(), button.height())))

    def insert_variable(self, inp, key, name):
        tok = '${' + name + '}'
        val = inp.text()
        if key in VAR_REPLACE:
            new, cur = tok, len(tok)
        elif key == 'src':
            new = (val + ('' if val.endswith('|') else '|') + tok) if val.strip() else tok   # | = fallback
            cur = len(new)
        else:
            a, b = inp.selectionStart(), inp.selectionStart() + len(inp.selectedText())
            if a < 0:
                a = b = inp.cursorPosition()
            new, cur = val[:a] + tok + val[b:], a + len(tok)
        inp.setText(new)
        inp.setCursorPosition(cur)
        inp._on_edit(new)
        inp._on_done()
        inp.setFocus()

    def update_rect_fields(self):
        el = self.selected()
        if not el:
            return
        r = parse_rect(el['props'].get('rect'))
        for i, sp in enumerate(self.rect_inputs):
            if not sp.hasFocus():
                sp.blockSignals(True)
                sp.setValue(r[i])
                sp.blockSignals(False)
        self.update_status()

    def refresh_props(self):
        old = self.props_scroll.takeWidget()
        if old is not None:
            old.hide()
            old.deleteLater()
        self.rect_inputs = []
        box_w = QWidget()
        box_w.setObjectName('props')
        box = QVBoxLayout(box_w)
        box.setContentsMargins(0, 0, 0, 8)
        box.setSpacing(0)
        try:
            self._fill_props(box)
        finally:
            box.addStretch(1)
            self.props_scroll.setWidget(box_w)

    def _fill_props(self, box):
        th = self.theme()
        if not th:
            n = QLabel(tx('Open a theme folder or make a new theme.'))
            n.setProperty('dim', '1')
            n.setContentsMargins(10, 10, 10, 10)
            n.setWordWrap(True)
            box.addWidget(n)
            return

        def setter(obj, key):
            def f(v, live=False):
                if v == '':
                    obj.pop(key, None)
                else:
                    obj[key] = v
                self.render()
                if not live:
                    self.refresh_list()
            return f

        el = self.selected()
        if not el:
            n = QLabel(tx('Nothing selected: these are the global settings of the theme.'))
            n.setProperty('dim', '1')
            n.setWordWrap(True)
            n.setContentsMargins(10, 10, 10, 10)
            box.addWidget(n)
            for title, keys in GROUPS['global']:
                b = self._section(box, title)
                for k in keys:
                    self.field(b, k, th['global'].get(k), setter(th['global'], k), color=(k == 'background_color'))
            # "background" is a picture here, so it gets no color picker
            self._extra_keys(box, th['global'], KEYS['global'])
            return

        p = el['props']
        t = (p.get('type') or 'rect').lower()
        bl = self._section(box, 'Layer')

        def rename(v, live=False):
            if live:
                return
            nv = re.sub(r'[\[\]]', '', v).strip()
            if not nv or nv == el['name']:
                QTimer.singleShot(0, self.refresh_props)
                return
            if any(e is not el and e['name'] == nv for e in self.theme()['elements']):
                self.flash('Name already used by another element')
                QTimer.singleShot(0, self.refresh_props)
                return
            el['name'] = nv
            self.refresh_list()
            self.update_status()
        self.field(bl, 'name', el['name'], rename).setToolTip(tx('Name of the [name] section in the file'))

        def set_type(v, live=False):
            p['type'] = v or 'rect'
            self.render()
            self.refresh_list()
            QTimer.singleShot(0, self.refresh_props)
        self.field(bl, 'type', p.get('type') or 'rect', set_type)

        # rect as 4 numbers
        bt = self._section(box, 'Transform')
        grid = QWidget()
        grid.setProperty('key', 'rect')
        gl = QHBoxLayout(grid)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(6)
        r = parse_rect(p.get('rect'))
        for i, (n, tip) in enumerate((('X', 'x'), ('Y', 'y'), ('W', 'width'), ('H', 'height'))):
            lab = QLabel(n)
            lab.setProperty('dim', '1')
            sp = QSpinBox()
            sp.setRange(-99999, 99999)
            sp.setValue(r[i])
            sp.setToolTip(tx(tip))
            sp.setMinimumWidth(52)
            snapped = [False]

            def changed(val, i=i, snapped=snapped):
                if not snapped[0]:
                    self.snapshot()
                    snapped[0] = True
                cur = parse_rect(el['props'].get('rect'))
                cur[i] = val
                el['props']['rect'] = join_rect(cur)
                self.render()
            sp.valueChanged.connect(changed)
            sp.editingFinished.connect(lambda snapped=snapped: snapped.__setitem__(0, False))
            gl.addWidget(lab)
            gl.addWidget(sp, 1)
            self.rect_inputs.append(sp)
        bt.addWidget(grid)
        if t == 'image':
            row, h = self._row(bt, 'rotate', tx('rotate'), tx('Turns the picture: makes a rotated copy (the original stays in the folder) and uses it. You can also drag just outside a corner handle.'))
            ok = bool(self.rotatable_src(el))
            deg = QSpinBox()
            deg.setRange(-360, 360)
            deg.setSuffix('°')
            deg.setFixedWidth(78)
            deg.setEnabled(ok)
            go = QPushButton(tx('Rotate'))
            go.setEnabled(ok)
            go.clicked.connect(lambda: deg.value() and self.bake_rotation(el, deg.value()))
            h.addWidget(deg)
            h.addWidget(go)
            h.addStretch(1)
            if not ok:
                self._note(bt, 'Rotation needs a picture of the theme (PNG or JPG) in src, not a ${variable}.')

        self._visibility(box, el)
        for title, keys in GROUPS.get(t, []):
            b = self._section(box, title)
            for k in keys:
                self.field(b, k, p.get(k), setter(p, k), color=(t == 'bar' and k == 'background'))
            if title in ('Picture', 'Video') and re.search(r'\.gif\b', p.get('src') or '', re.I):
                self._note(b, 'GIF: it is animated only in this preview. Make sure your version of Frontier can read GIF files on the MiSTer; otherwise use a sequence of frames (src with *) and fps.')
        self._extra_keys(box, p, KEYS['common'] + KEYS.get(t, []))

    @staticmethod
    def _combo():
        cb = QComboBox()
        cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        cb.setMinimumContentsLength(6)
        return cb

    def _note(self, layout, text, *a):
        n = QLabel(tx(text, *a))
        n.setProperty('note', '1')
        n.setWordWrap(True)
        layout.addWidget(n)
        return n

    def _visibility(self, box, el):
        """The conditions (if / ifnot / layout) in plain words."""
        p = el['props']
        vb = self._section(box, 'Visibility')
        adv = self._section(box, 'Advanced conditions')

        def changed():
            self.render()
            self.refresh_list()
            QTimer.singleShot(0, fill)

        def plain_row(label):
            lab = QLabel(tx(label))
            lab.setProperty('stack', '1')
            vb.addWidget(lab)

        def fill():
            clear_layout(vb)
            i, n = (p.get('if') or '').strip(), (p.get('ifnot') or '').strip()
            if not i and not n:
                mode, var = 'always', None
            elif i and not n and SIMPLE_VAR.match(i):
                mode, var = 'if', SIMPLE_VAR.match(i).group(1)
            elif n and not i and SIMPLE_VAR.match(n):
                mode, var = 'ifnot', SIMPLE_VAR.match(n).group(1)
            else:
                mode, var = 'custom', None
            variables = self.sample_vars()
            groups = {'General': [], 'Game': [], 'Media': []}
            for k in variables:
                groups['Game' if k.startswith('game.') else 'Media' if k.startswith('media.') else 'General'].append(k)
            # 1. when is it shown
            plain_row('Show this element')
            modes = [('always', tx('Always')), ('if', tx('Only if a variable has a value')), ('ifnot', tx('Only if a variable is empty'))]
            if mode == 'custom':
                modes.append(('custom', tx('Custom condition (see Advanced conditions)')))
            cb = self._combo()
            for v, label in modes:
                cb.addItem(label, v)
            cb.setCurrentIndex([m[0] for m in modes].index(mode))

            def set_mode(ix):
                m = cb.itemData(ix)
                if m == 'custom' or m == mode:
                    return
                self.snapshot()
                v = var or ('media.snap' if 'media.snap' in variables else (groups['General'][0] if groups['General'] else 'title'))
                p.pop('if', None)
                p.pop('ifnot', None)
                if m == 'if':
                    p['if'] = '${' + v + '}'
                if m == 'ifnot':
                    p['ifnot'] = '${' + v + '}'
                changed()
            cb.activated.connect(set_mode)
            vb.addWidget(cb)
            # 2. which variable
            if mode in ('if', 'ifnot'):
                plain_row('Variable')
                sel = self._combo()
                known = []
                for g, names in groups.items():
                    if not names:
                        continue
                    sel.addItem('— ' + tx(g) + ' —', None)
                    sel.model().item(sel.count() - 1).setEnabled(False)
                    for name in names:
                        ex = variables.get(name, '')
                        ex = tx('(empty)') if ex == '' else tx('picture') if ex.startswith('@') else ex
                        sel.addItem('${%s}  —  %s' % (name, ex[:21] + '…' if len(ex) > 22 else ex), name)
                        known.append(name)
                if var not in known:
                    sel.addItem('${%s}' % var, var)
                sel.setCurrentIndex(sel.findData(var))

                def set_var(ix):
                    nm = sel.itemData(ix)
                    if not nm:
                        return
                    self.snapshot()
                    p[mode] = '${' + nm + '}'
                    changed()
                sel.activated.connect(set_var)
                vb.addWidget(sel)
                self._note(vb, 'Visible only when {0} has a value (is not empty).' if mode == 'if' else 'Visible only when {0} is empty.', '${' + var + '}')
            elif mode == 'custom':
                self._note(vb, 'This element has a custom condition: edit it in "Advanced conditions" below.')
            # 3. which layout
            plain_row('Visible in')
            lc = self._combo()
            for v, label in (('', tx('Both layouts')), ('media', tx('Picture layout only')), ('text', tx('Text layout only'))):
                lc.addItem(label, v)
            lc.setCurrentIndex(max(0, lc.findData(p.get('layout') or '')))

            def set_layout(ix):
                v = lc.itemData(ix)
                self.snapshot()
                if v:
                    p['layout'] = v
                else:
                    p.pop('layout', None)
                changed()
            lc.activated.connect(set_layout)
            vb.addWidget(lc)
            self._note(vb, 'Text layout shows descriptions instead of pictures (a Frontier setting). Use "Text layout" in the top bar to preview it.')
            # 4. what happens right now in the preview
            layout_hidden = (p.get('layout') or '').lower() == ('media' if self.S['opt']['text'] else 'text')
            shown = visible(p, variables, self.S['opt']['text'])
            st = QLabel('<span style="color:%s">●</span>  %s' % ('#3fb950' if shown else '#d29922', tx(
                'Now in the preview: shown' if shown else 'Now in the preview: hidden by the layout' if layout_hidden else 'Now in the preview: hidden by the condition')))
            vb.addWidget(st)
        fill()

        # advanced: the raw keys
        self._note(adv, 'Raw if / ifnot. "if" = visible if the text is not empty, "ifnot" = visible if it is empty. You can mix variables, e.g. ${a}${b}.')

        def raw(key):
            def f(v, live=False):
                if v == '':
                    p.pop(key, None)
                else:
                    p[key] = v
                self.render()
                if not live:
                    self.refresh_list()
                    fill()
            return f
        self.field(adv, 'if', p.get('if'), raw('if'), placeholder='${media.snap}')
        self.field(adv, 'ifnot', p.get('ifnot'), raw('ifnot'))

    def _extra_keys(self, box, obj, known):
        """Unknown keys: editable as text."""
        extra = [k for k in obj if k not in known]
        b = self._section(box, 'Other keys')
        ta = CommitText('\n'.join(k + '=' + obj[k] for k in extra))
        ta.setPlaceholderText('key=value')
        ta.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        ta.setFixedHeight(max(2, len(extra) + 1) * 18 + 12)
        ta.setProperty('key', 'other')

        def commit():
            self.snapshot()
            for k in extra:
                obj.pop(k, None)
            for line in ta.toPlainText().split('\n'):
                eq = line.find('=')
                if eq > 0:
                    obj[line[:eq].strip().lower()] = line[eq + 1:].strip()
            self.render()
            QTimer.singleShot(0, self.refresh_props)
        ta.committed.connect(commit)
        b.addWidget(ta)

    def _focus_changed(self, old, new):
        w = new
        while w is not None and w is not self:
            k = w.property('key')
            if k:
                self.keyinfo.setText(k + ': ' + tx(KEY_INFO.get(k, '')) if k in KEY_INFO else k)
                return
            w = w.parentWidget()
        if new is not None and self.props_scroll.isAncestorOf(new):
            self.keyinfo.setText('')

    # ---- assets
    def refresh_datalists(self):
        keys = sorted(self.files.files)
        self.images_list = ['${media.system}|${media.snap}|${media.title}', '${media.box}', '${media.marquee}', '${media.fanart}', '${media.video}'] + \
            [k for k in keys if IMAGE_RE.search(k) or VIDEO_RE.search(k)]
        self.fonts_list = [k for k in keys if FONT_RE.search(k)]

    def _thumb(self, img, w=64, h=48):
        pm = QPixmap(w, h)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        for y in range(0, h, 6):   # checkerboard behind transparent pictures
            for x in range(0, w, 6):
                if (x // 6 + y // 6) % 2:
                    p.fillRect(x, y, 6, 6, QColor(127, 127, 127, 56))
        if img is not None:
            s = img.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            p.drawImage((w - s.width()) // 2, (h - s.height()) // 2, s)
        p.end()
        return QIcon(pm)

    def refresh_assets(self):
        lw = self.assets
        lw.clear()
        keys = sorted(self.files.files)
        imgs = [k for k in keys if IMAGE_RE.search(k)]
        fonts = [k for k in keys if FONT_RE.search(k)]
        vids = [k for k in keys if VIDEO_RE.search(k)]
        self.img_hint.setText(tx('{0} pictures, {1} videos, {2} fonts in "{3}". Double-click to apply to the selection.', len(imgs), len(vids), len(fonts), self.S['folder_name'] or '…')
                              if self.files.files else tx('Open a folder to see pictures and fonts.'))

        def head(text, empty, n):
            it = QListWidgetItem(tx(text).upper())
            f = it.font()
            f.setBold(True)
            f.setPointSizeF(max(7.0, f.pointSizeF() * 0.85))
            it.setFont(f)
            it.setForeground(QColor(self.colors['dim']))
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            lw.addItem(it)
            if not n:
                e = QListWidgetItem(tx(empty))
                e.setForeground(QColor(self.colors['dim']))
                e.setFlags(Qt.ItemFlag.NoItemFlags)
                lw.addItem(e)
        head('Pictures', 'No pictures.', len(imgs))
        for k in imgs:
            it = QListWidgetItem(self._thumb(self.media.image(self.files.files[k])), (k[4:] if k.startswith('img/') else k) + ('  ·  GIF' if k.lower().endswith('.gif') else ''))
            it.setData(Qt.ItemDataRole.UserRole, k)
            it.setToolTip(k + '\n' + tx('Double-click: apply to the selection'))
            lw.addItem(it)
        head('Videos', 'No videos.', len(vids))
        for k in vids:
            rec = self.media.video(self.files.files[k])
            mm = '  ·  %d:%02d' % (rec['dur'] // 60, round(rec['dur'] % 60)) if rec['dur'] else ''
            it = QListWidgetItem(self._thumb(rec['still']), (k[6:] if k.startswith('video/') else k) + mm + ('  ⚠' if rec['failed'] else ''))
            it.setData(Qt.ItemDataRole.UserRole, k)
            tip = k + '\n' + tx('Double-click: apply to the selection')
            if rec['failed']:
                tip += '\n' + tx('Cannot show the first frame of this video (the file is copied anyway)')
            it.setToolTip(tip)
            lw.addItem(it)
        head('Fonts', 'No fonts.', len(fonts))
        for k in fonts:
            pm = QPixmap(64, 48)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            p.setFont(self.media.qfont(self.files.files[k], 26))
            p.setPen(QColor(self.colors['text']))
            p.drawText(QRectF(0, 0, 64, 48), Qt.AlignmentFlag.AlignCenter, 'Aa')
            p.end()
            it = QListWidgetItem(QIcon(pm), k)
            it.setData(Qt.ItemDataRole.UserRole, k)
            it.setToolTip(k + '\n' + tx('Double-click: apply to the selection (or as the theme font)'))
            lw.addItem(it)

    def _asset_dblclicked(self, item):
        k = item.data(Qt.ItemDataRole.UserRole)
        if not k:
            return
        if FONT_RE.search(k):
            self.apply_font(k)
        else:
            self.apply_asset(k)

    def apply_asset(self, path):
        if not self.theme():
            return
        el = self.selected()
        if VIDEO_RE.search(path):   # a video goes into a video element, never into a picture or the background
            if el and (el['props'].get('type') or '').lower() == 'video':
                self.snapshot()
                el['props']['src'] = path
                self.flash(el['name'] + ': src = ' + path)
                self.refresh_props()
                self.refresh_list()
                self.render()
            else:
                self.create_element('video', [64, 64, 320, 200], {'src': path})
            return
        if not el:
            self.snapshot()
            self.theme()['global']['background'] = path
            self.flash('Background = {0}', path)
        else:
            t = (el['props'].get('type') or 'rect').lower()
            if t in ('image', 'video'):
                self.snapshot()
                el['props']['src'] = path
                self.flash(el['name'] + ': src = ' + path)
            elif t == 'list':
                self.snapshot()
                el['props']['sel_image'] = path
                self.flash(el['name'] + ': sel_image = ' + path)
            else:
                self.create_element('image', [64, 64, 240, 160], {'src': path})
                return
        self.refresh_props()
        self.refresh_list()
        self.render()

    def apply_font(self, path):
        if not self.theme():
            return
        el = self.selected()
        t = (el['props'].get('type') or 'rect').lower() if el else ''
        self.snapshot()
        if el and t in ('text', 'list'):
            el['props']['font'] = path
            self.flash(el['name'] + ': font = ' + path)
        else:
            self.theme()['global']['font'] = path
            self.flash('Theme font = {0}', path)
        self.refresh_props()
        self.render()

    # ------------------------------------------------------------------
    # variants
    def cur_parts(self):
        m = re.match(r'^(theme|detail|screensaver|loading)(_43)?\.ini$', self.S['cur'] or '')
        return (m.group(1), bool(m.group(2))) if m else None

    def source_for(self, scr, f43):
        """How a missing file could be made: scaled from the 16:9 one, or copied from the screen it derives from."""
        V = self.S['variants']
        if f43 and file_of(scr, False) in V:
            return 'scale', file_of(scr, False)
        if scr == 'detail' and file_of('theme', f43) in V:
            return 'copy', file_of('theme', f43)
        if scr == 'screensaver' and file_of('detail', f43) in V:
            return 'copy', file_of('detail', f43)
        return None

    def create_variant(self, scr, f43):
        dst, src = file_of(scr, f43), self.source_for(scr, f43)
        if dst in self.S['variants'] or not src:
            return False
        self.snapshot()
        how, frm = src
        t, header = make_variant(self.S['variants'][frm], how, scr)
        self.S['headers'][dst] = header
        self.S['variants'][dst] = t
        self.S['cur'], self.S['sel'] = dst, -1
        self.refresh_all()
        if how == 'scale':
            self.flash('{0} made from {1}: x and widths scaled to 4:3, check the layout', dst, frm)
        elif scr == 'detail':
            self.flash('{0} made from a copy of {1}: change the list into the versions, add the description', dst, frm)
        else:
            self.flash('{0} made from a copy of {1} without the versions: make the description bigger, help "Start: play"', dst, frm)
        return True

    def go_screen(self, scr, f43, ask):
        dst = file_of(scr, f43)
        if dst not in self.S['variants']:
            src = self.source_for(scr, f43)
            if not src:
                self.flash('{0} does not exist and there is nothing to make it from', dst)
                return
            if ask and not self.confirm(tx('{0} does not exist yet. Make it from {1}?', dst, src[1])):
                self.refresh_variants()
                return
            self.create_variant(scr, f43)
            return
        self.S['cur'], self.S['sel'] = dst, -1
        self.refresh_all()

    def _fmt_clicked(self, f43):
        p = self.cur_parts()
        self.go_screen(p[0] if p else 'theme', f43, True)
        self.refresh_variants()

    def screen_items(self):
        p = self.cur_parts()
        f43 = p[1] if p else False
        items = []
        V = self.S['variants']
        for scr in SCREENS:
            if scr == 'loading' and 'loading.ini' not in V and 'loading_43.ini' not in V:
                continue
            dst = file_of(scr, f43)
            have = dst in V
            can = have or bool(self.source_for(scr, f43))
            parent = 'theme' if scr == 'detail' else 'detail' if scr == 'screensaver' else None
            items.append({'label': tx(SCREEN_NAMES[scr]), 'check': bool(p) and p[0] == scr, 'disabled': not can,
                          'key': dst if have else tx('+ make {0}', dst) if can else tx('needs {0}', file_of(parent, f43) if parent else file_of(scr, False)),
                          'run': (lambda s=scr: self.go_screen(s, f43, False)) if can else (lambda: None)})
        others = [v for v in V if v not in VARIANTS]
        if others:
            items += ['-', {'head': 'Other files'}]
            for v in others:
                items.append({'label': v, 'check': v == self.S['cur'], 'run': lambda v=v: (self.S.update(cur=v, sel=-1), self.refresh_all())})
        return items

    def variant_menu(self):
        p = self.cur_parts()
        fmt = lambda f43: {'label': '4:3' if f43 else '16:9', 'check': bool(p) and p[1] == f43,
                           'run': lambda: self.go_screen(p[0] if p else 'theme', f43, True)}
        return [fmt(False), fmt(True), '-',
                {'label': tx('Make 4:3'), 'run': self.make_43, 'disabled': not self.can_make('43')},
                {'label': tx('Make detail'), 'run': lambda: self.make_screen('detail'), 'disabled': not self.can_make('detail')},
                {'label': tx('Make screensaver'), 'run': lambda: self.make_screen('screensaver'), 'disabled': not self.can_make('screensaver')},
                '-'] + self.screen_items()

    def can_make(self, what):
        """As the Make buttons of the web editor: the 4:3 file of the current 16:9 one, detail from the game
        list, screensaver from the detail; only when it does not exist yet"""
        p, V = self.cur_parts(), self.S['variants']
        if not p:
            return False
        if what == '43':
            return not p[1] and file_of(p[0], True) not in V
        parent = 'theme' if what == 'detail' else 'detail'
        return p[0] == parent and file_of(what, p[1]) not in V

    def make_43(self):
        if self.can_make('43'):
            self.create_variant(self.cur_parts()[0], True)

    def make_screen(self, what):
        if self.can_make(what):
            self.create_variant(what, self.cur_parts()[1])

    def refresh_variants(self):
        p, has = self.cur_parts(), bool(self.theme())
        for f43, b in self.fmt_btns.items():
            b.setChecked(bool(p) and p[1] == f43)
            b.setEnabled(has)
        self.btn_screen.setEnabled(has)
        self.btn_make43.setEnabled(has and self.can_make('43'))
        self.btn_screen.setText((tx(SCREEN_NAMES[p[0]]) if p else (self.S['cur'] or tx('Screen'))) + '  ▾')
        self.cur_file.setText(self.S['cur'] if has else '')

    # ------------------------------------------------------------------
    # elements
    def unique_name(self, base):
        names = {e['name'] for e in self.theme()['elements']}
        n, i = base, 2
        while n in names:
            n = '%s_%d' % (base, i)
            i += 1
        return n

    def create_element(self, t, rect, extra=None):
        if not self.theme():
            return
        self.snapshot()
        props = {'type': t, 'rect': join_rect(rect)}
        props.update(NEW_PROPS.get(t, {}))
        props.update(extra or {})
        el = {'name': self.unique_name(t), 'props': props}
        at = self.S['sel'] + 1 if self.S['sel'] >= 0 else len(self.theme()['elements'])
        self.theme()['elements'].insert(at, el)
        self.select(at)

    def add_element(self, t):
        bw, bh = parse_base(self.theme()['global'].get('base'))
        self.create_element(t, [round(bw / 4), round(bh / 4), round(bw / 3), round(bh / 4)])

    def move(self, d):
        if not self.theme():
            return
        els, i = self.theme()['elements'], self.S['sel']
        j = i + d
        if i < 0 or j < 0 or j >= len(els):
            return
        self.snapshot()
        els[i], els[j] = els[j], els[i]
        self.select(j)

    def duplicate(self):
        el = self.selected()
        if not el:
            return
        self.snapshot()
        c = copy.deepcopy(el)
        c['name'] = self.unique_name(el['name'])
        r = parse_rect(c['props'].get('rect'))
        c['props']['rect'] = join_rect([r[0] + 16, r[1] + 16, r[2], r[3]])
        self.theme()['elements'].insert(self.S['sel'] + 1, c)
        self.select(self.S['sel'] + 1)

    def remove(self):
        if self.S['sel'] < 0 or not self.theme():
            return
        self.snapshot()
        self.theme()['elements'].pop(self.S['sel'])
        self.select(min(self.S['sel'], len(self.theme()['elements']) - 1))

    # ---- rotation: the theme format has no rotation key, so a picture is turned by baking it into a copy of the file
    def rotatable_src(self, el):
        """Path of the picture file when the element can be rotated (a PNG or JPG of the theme), else ''."""
        if not el or (el['props'].get('type') or '').lower() != 'image':
            return ''
        src = (el['props'].get('src') or '').strip()
        if not src or re.search(r'[$@|*]', src):
            return ''
        path = norm_path(src)
        return path if re.search(r'\.(png|jpe?g)$', path, re.I) and self.files.has(path) else ''

    def bake_rotation(self, el, deg):
        """The picture as it is shown in its rectangle is turned by deg (clockwise) into a new PNG next to the original;
        the element takes the new file and the bounding box of the turned rectangle (same center)."""
        path = self.rotatable_src(el)
        if not path:
            self.flash('Rotation needs a picture of the theme (PNG or JPG) in src')
            self.render()
            return
        src = QImage(self.files.files[path])
        if src.isNull():
            self.alert(tx('Cannot read {0}', path))
            self.render()
            return
        p = el['props']
        x, y, w, h = parse_rect(p.get('rect'))
        if w < 1 or h < 1:
            return
        sx, sy, sw, sh, dw, dh = fit_rect(src.width(), src.height(), 0, 0, w, h, (p.get('fit') or 'contain').lower())
        dx, dy = (w - dw) * align_num(p.get('align'), 'center') / 2, (h - dh) * align_num(p.get('valign'), 'middle') / 2
        k = max(0.25, min(3, max(sw / dw, sh / dh)))   # keep the pixels of the original (up to 3x the base size)
        th = math.radians(deg)
        c, s = abs(math.cos(th)), abs(math.sin(th))
        nw, nh = w * c + h * s, w * s + h * c
        base = QImage(max(1, round(w * k)), max(1, round(h * k)), QImage.Format.Format_ARGB32_Premultiplied)
        base.fill(Qt.GlobalColor.transparent)
        bp = QPainter(base)
        bp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        bp.drawImage(QRectF(dx * k, dy * k, dw * k, dh * k), src, QRectF(sx, sy, sw, sh))
        bp.end()
        out = QImage(max(1, round(nw * k)), max(1, round(nh * k)), QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(Qt.GlobalColor.transparent)
        op = QPainter(out)
        op.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing)
        op.translate(out.width() / 2, out.height() / 2)
        op.rotate(deg)
        op.drawImage(QPointF(-base.width() / 2, -base.height() / 2), base)
        op.end()
        # name: picture_rot.png, picture_rot2.png ... (never over an existing file)
        d = path[:path.rfind('/') + 1]
        stem = re.sub(r'_rot\d*$', '', re.sub(r'\.[^.]+$', '', path[len(d):]))
        np_, n = d + stem + '_rot.png', 2
        while np_ in self.files.files or (self.files.folder and os.path.exists(os.path.join(self.files.folder, np_))):
            np_ = d + stem + '_rot%d.png' % n
            n += 1
        target = os.path.join(self.files.folder, *np_.split('/')) if self.files.folder else os.path.join(self.tmpdir, *np_.split('/'))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if not out.save(target, 'PNG'):
            self.alert(tx('Copy failed: {0}', target))
            return
        self.files.files[np_] = target
        self.snapshot()
        W, H, cx, cy = round(nw), round(nh), x + w / 2, y + h / 2
        p['src'] = np_
        p['rect'] = join_rect([round(cx - W / 2), round(cy - H / 2), W, H])
        p['fit'] = 'stretch'
        p.pop('align', None)
        p.pop('valign', None)
        self.refresh_datalists()
        self.refresh_assets()
        self.refresh_props()
        self.refresh_list()
        self.render()
        self.flash('Picture rotated {0}°: the original is untouched, the rotated copy is {1}' if self.files.folder
                   else 'Picture rotated {0}°: the rotated copy is {1} (Save puts it in the theme folder)', round(deg), np_)

    # ------------------------------------------------------------------
    # files: open, new, save
    def _start_dir(self):
        last = self.cfg.value('lastDir', '')
        return os.path.dirname(last) if last else os.path.expanduser('~')

    def open_folder(self):
        if not self.discard_ok():
            return
        d = QFileDialog.getExistingDirectory(self, tx('Open a theme folder (theme.ini, pictures, fonts)  Ctrl+O').split('  ')[0], self._start_dir())
        if d:
            self.load_folder(d)

    def load_folder(self, folder):
        """Opens the theme in folder. Returns False and changes nothing when the folder has no theme.ini
        (the open theme is never replaced by a default one)."""
        folder = os.path.abspath(folder)
        name = os.path.basename(folder.rstrip('/\\')) or folder
        files = ThemeFiles.scan(folder)
        found = [v for v in VARIANTS if v in files]
        if not found:   # no theme.ini: maybe the .ini files were renamed by a browser when downloaded
            loose = [k for k in files if '/' not in k and k.lower().endswith('.ini')]
            mp = [(k, guess_variant(k, True)) for k in loose]
            if mp and len({m[1] for m in mp}) == len(mp) and self.confirm(tx(
                    'There is no theme.ini in "{0}", but there are these .ini files: {1}. Open them as the theme, using these names?',
                    name, ', '.join(a + ' → ' + b for a, b in mp))):
                for a, b in mp:
                    files[b] = files.pop(a)
                found = [v for v in VARIANTS if v in files]
        if not found:
            subs = sorted({k.split('/')[0] for k in files if re.match(r'^[^/]+/theme\.ini$', k, re.I)})
            self.alert(tx('There is no theme.ini directly in "{0}", but there is one in: {1}. Choose that folder instead.', name, ', '.join(subs)) if subs
                       else tx('There is no theme.ini in the folder "{0}": nothing was opened. Choose the folder that contains theme.ini.', name))
            return False
        self.files = ThemeFiles(folder, files)
        self.media.clear()
        S = self.S
        S['folder_name'] = name
        S['variants'], S['headers'] = {}, {}
        for v in found:
            with open(files[v], encoding='utf-8', errors='replace') as f:
                text = f.read()
            S['variants'][v] = parse_ini(text)
            S['headers'][v] = ini_header(text)
        S['cur'] = 'theme.ini' if 'theme.ini' in S['variants'] else found[0]
        S.update(sel=-1, undo=[], redo=[], dirty=False)
        self.cfg.setValue('lastDir', folder)
        self.refresh_all()
        self.flash('Opened "{0}"', name)
        return True

    def reopen_last(self):
        last = self.cfg.value('lastDir', '')
        if last and self.discard_ok():
            self.load_folder(last)

    def new_theme(self, keep_files=False):
        if not keep_files:
            self.files = ThemeFiles()
            self.media.clear()
            self.S['folder_name'] = ''
        self.S.update(variants={'theme.ini': parse_ini(NEW_THEME_INI)}, headers={}, cur='theme.ini', sel=-1, undo=[], redo=[], dirty=True)
        self.refresh_all()

    def open_example(self):
        if not self.discard_ok():
            return
        self.new_theme(False)
        self.theme()['global']['name'] = 'Example theme'
        self.S['dirty'] = False
        self.update_status()

    def new_theme_in_folder(self, ask=True, folder=None):
        """New theme: choose the (empty) folder of the new theme and create its theme.ini there."""
        if ask and not self.discard_ok():
            return
        d = folder or QFileDialog.getExistingDirectory(self, tx('Choose the folder of the new theme'), self._start_dir())
        if not d:
            return
        d = os.path.abspath(d)
        name = os.path.basename(d.rstrip('/\\')) or d
        if os.path.isfile(os.path.join(d, 'theme.ini')):
            if self.confirm(tx('The folder "{0}" already contains a theme.ini. Open it instead of creating a new one?', name)):
                self.load_folder(d)
            return
        self.new_theme(False)
        self.files = ThemeFiles(d, ThemeFiles.scan(d))   # pictures and fonts that are already there
        self.S['folder_name'] = name
        self.theme()['global']['name'] = name
        self.cfg.setValue('lastDir', d)
        if self.save_folder():
            self.refresh_all()
            self.flash('New theme created in {0}', name)

    def save_folder(self):
        folder = self.files.folder
        if not folder:
            return False
        try:
            # files picked elsewhere or rotated copies go into the folder first
            for rel in self.files.outside():
                dst = os.path.join(folder, *rel.split('/'))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(self.files.files[rel], dst)
                self.files.files[rel] = dst
            for v, t in self.S['variants'].items():
                with open(os.path.join(folder, v), 'w', encoding='utf-8', newline='\n') as f:
                    f.write(serialize_ini(t, header_for(self.S['headers'], v)))
                self.files.files[v] = os.path.join(folder, v)
        except OSError as e:
            self.alert(tx('Saving failed: {0}', e))
            return False
        self.S['dirty'] = False
        self.update_status()
        self._drop_session()
        self.flash('Saved in the folder "{0}": {1}', self.S['folder_name'], ', '.join(self.S['variants']))
        return True

    def smart_save(self):
        """Save: into the theme folder; a theme without a folder asks for one first."""
        if not self.theme():
            return
        if self.files.folder:
            self.save_folder()
            return
        d = QFileDialog.getExistingDirectory(self, tx('Choose the folder of the theme'), self._start_dir())
        if d:
            self.save_to(d)

    def save_to(self, d):
        d = os.path.abspath(d)
        name = os.path.basename(d.rstrip('/\\')) or d
        if os.path.isfile(os.path.join(d, 'theme.ini')) and not self.confirm(tx('The folder "{0}" already contains a theme.ini. Replace it with this theme?', name)):
            return False
        mine = dict(self.files.files)
        self.files = ThemeFiles(d, ThemeFiles.scan(d))
        self.files.files.update(mine)
        self.S['folder_name'] = name
        self.cfg.setValue('lastDir', d)
        ok = self.save_folder()
        self.refresh_all()
        return ok

    def save_zip(self, path=None):
        """One ZIP with the whole theme (.ini, img/, fonts/, video/), to share it."""
        if not self.theme():
            return ''
        base = re.sub(r'[\\/:*?"<>|]+', '_', self.S['folder_name'] or self.theme()['global'].get('name') or 'theme').strip() or 'theme'
        if not path:
            start = os.path.join(os.path.dirname(self.files.folder) if self.files.folder else self._start_dir(), base + '.zip')
            path, _ = QFileDialog.getSaveFileName(self, tx('Save the theme as ZIP'), start, 'ZIP (*.zip)')
            if not path:
                return ''
        try:
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
                for v, t in self.S['variants'].items():
                    z.writestr(v, serialize_ini(t, header_for(self.S['headers'], v)))
                for rel, full in sorted(self.files.files.items()):
                    if rel not in self.S['variants'] and not re.search(r'(^|/)\.', rel) and os.path.isfile(full):
                        z.write(full, rel, zipfile.ZIP_STORED if not rel.lower().endswith('.ini') else zipfile.ZIP_DEFLATED)
        except OSError as e:
            self.alert(tx('Saving failed: {0}', e))
            return ''
        self.flash('{0} saved: it holds the whole theme (.ini, img/, fonts/, video/)', os.path.basename(path))
        return path

    # ---- unsaved work is kept, so a crash does not lose it
    def session_tick(self):
        if not self.theme() or not self.S['dirty']:
            return
        sig = self.state_string() + '|' + json.dumps(self.files.files, sort_keys=True)
        if sig == self._sess_sig:
            return
        self._sess_sig = sig
        try:
            with open(self.session_path, 'w', encoding='utf-8') as f:
                json.dump({'when': time.time(), 'name': self.S['folder_name'], 'folder': self.files.folder, 'variants': self.S['variants'],
                           'headers': self.S['headers'], 'cur': self.S['cur'], 'files': self.files.files}, f)
        except OSError:
            pass

    def _drop_session(self):
        self.last_session = None
        self._sess_sig = ''
        try:
            os.remove(self.session_path)
        except OSError:
            pass

    def _load_last(self):
        try:
            with open(self.session_path, encoding='utf-8') as f:
                r = json.load(f)
            if r.get('variants'):
                self.last_session = r
        except (OSError, ValueError):
            pass
        if not self.theme():
            self.update_welcome()

    def restore_session(self):
        r = self.last_session
        if not r or not self.discard_ok():
            return
        folder = r.get('folder') if r.get('folder') and os.path.isdir(r['folder']) else None
        files = {k: v for k, v in (r.get('files') or {}).items() if os.path.isfile(v)}
        self.files = ThemeFiles(folder, files)
        self.media.clear()
        S = self.S
        S['variants'], S['headers'] = r['variants'], r.get('headers') or {}
        S['cur'] = r['cur'] if r.get('cur') in r['variants'] else next(iter(r['variants']))
        S.update(sel=-1, undo=[], redo=[], dirty=True, folder_name=r.get('name') or '')
        self.refresh_all()
        self.flash('Work restored: "{0}"', r.get('name') or 'theme')

    # ---- import of .ini files and pictures
    def pick_ini(self):
        paths, _ = QFileDialog.getOpenFileNames(self, tx('Load .ini files'), self.files.folder or self._start_dir(), tx('Theme files') + ' (*.ini)')
        if paths:
            self.import_ini(paths)

    def import_ini(self, paths):
        if not paths:
            return
        names = [os.path.basename(p) for p in paths]
        other = [n for n in names if not guess_variant(n)]
        if len(other) > 1:
            self.alert(tx('Only one file with another name at a time: it goes into the current variant ({0}).', self.S['cur']))
            return
        # a file with an unrecognised name goes to the current variant, or to theme.ini when no theme is open or it comes with others
        target = lambda n: guess_variant(n) or (self.S['cur'] if self.theme() and len(paths) == 1 else 'theme.ini')
        into = [target(n) for n in names]
        repl = [v for v in into if v in self.S['variants']]
        if repl and not self.confirm(tx('Replace {0} with the imported file?', ', '.join(repl))):
            return
        if self.theme():
            self.snapshot()
        for pth, v in zip(paths, into):
            with open(pth, encoding='utf-8', errors='replace') as f:
                text = f.read()
            self.S['variants'][v] = parse_ini(text)
            self.S['headers'][v] = ini_header(text)
        self.S.update(cur=into[0], sel=-1, dirty=True)
        self.refresh_all()
        self.flash('{0} imported' if self.files.files else '{0} imported: open the theme folder for its pictures and fonts',
                   ', '.join(n + ('' if n.lower() == v else ' → ' + v) for n, v in zip(names, into)))

    def pick_assets(self, kind):
        if not self.theme():
            return
        filt = {'img': tx('Pictures') + ' (*.png *.jpg *.jpeg *.gif)', 'video': tx('Videos') + ' (*.mp4 *.m4v *.mov *.mkv *.webm *.avi *.mpg *.mpeg *.ogv)',
                'fonts': tx('Fonts') + ' (*.ttf *.otf)'}[kind]
        title = {'img': 'Add pictures', 'video': 'Add videos', 'fonts': 'Add fonts'}[kind]
        paths, _ = QFileDialog.getOpenFileNames(self, tx(title), os.path.expanduser('~'), filt)
        if paths:
            self.add_assets(paths, kind)

    def add_assets(self, paths, kind):
        """Pictures go to img/, videos to video/ and fonts to fonts/ of the theme folder, so the theme stays self-contained."""
        is_font, is_video = kind == 'fonts', kind == 'video'
        ok_re = FONT_RE if is_font else VIDEO_RE if is_video else IMAGE_RE
        good = [p for p in paths if ok_re.search(p)]
        n, otf, kept = 0, False, []
        for src in good:
            fname = os.path.basename(src)
            rel = kind + '/' + fname
            old = self.files.files.get(rel)
            if is_font and old:   # a loaded font family cannot be swapped
                kept.append(fname)
                continue
            if not is_font and old and os.path.getsize(old) != os.path.getsize(src) and \
                    not self.confirm(tx('{0} already exists in {1}/ and is different. Replace it?', fname, kind)):
                continue
            target = src
            if self.files.folder:
                target = os.path.join(self.files.folder, kind, fname)
                try:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    if os.path.abspath(src) != os.path.abspath(target):
                        shutil.copy2(src, target)
                except OSError as e:
                    self.alert(tx('Copy failed: {0}', e))
                    continue
            self.files.files[rel] = target
            self.media.images.pop(target, None)
            self.media.gifs.pop(target, None)
            self.media.videos.pop(target, None)
            if is_font and fname.lower().endswith('.otf'):
                otf = True
            n += 1
        self.refresh_datalists()
        self.refresh_assets()
        if n and not self.files.folder:
            self.S['dirty'] = True
        if not n and kept:
            self.flash('{0} is already in fonts/: not replaced (rename the file if it is another font)', ', '.join(kept))
        elif not n:
            self.flash('Fonts must be .ttf or .otf files' if is_font else 'Videos must be .mp4, .mkv, .webm, .avi, .mov or .mpg files' if is_video else 'Pictures must be PNG, JPG or GIF files')
        elif is_font:
            self.flash('{0} fonts copied to fonts/' if self.files.folder else '{0} fonts added: Save copies them to fonts/', n)
        elif is_video:
            self.flash('{0} videos copied to video/' if self.files.folder else '{0} videos added: Save copies them to video/', n)
        else:
            self.flash('{0} pictures copied to img/' if self.files.folder else '{0} pictures added: Save copies them to img/', n)
        if otf:
            QTimer.singleShot(3000, lambda: self.flash('.otf font: the Frontier guide speaks of TTF, if it does not show on the MiSTer convert it to .ttf'))
        self.render()

    # ------------------------------------------------------------------
    # window events: drop a folder, close
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()
            self.drop_label.show()
            self.drop_label.raise_()

    def dragLeaveEvent(self, ev):
        self.drop_label.hide()

    def dropEvent(self, ev):
        self.drop_label.hide()
        for u in ev.mimeData().urls():
            p = u.toLocalFile()
            if p and os.path.isdir(p):
                if self.discard_ok():
                    self.load_folder(p)
                return
            if p and p.lower().endswith('.ini'):
                self.import_ini([x.toLocalFile() for x in ev.mimeData().urls() if x.toLocalFile().lower().endswith('.ini')])
                return

    def closeEvent(self, ev):
        self.session_tick()
        if not self.discard_ok():
            ev.ignore()
            return
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        ev.accept()


class KeyFilter(QObject):
    """The keys of the editor, as in the web version: tools, arrows, Delete, Space, Escape, Shift+F1/F2."""

    def __init__(self, ed):
        super().__init__()
        self.ed = ed

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return False
        ed = self.ed
        app = QApplication.instance()
        if app.activeModalWidget() or app.activePopupWidget() or app.activeWindow() is not ed:
            return False
        if t == QEvent.Type.KeyRelease:
            if ev.key() == Qt.Key.Key_Space and not ev.isAutoRepeat() and ed.space_down:
                ed.space_down = False
                ed.canvas.setCursor(Qt.CursorShape.ArrowCursor)
            return False
        fw = app.focusWidget()
        typing = isinstance(fw, (QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox, QComboBox))
        key, mods = ev.key(), ev.modifiers()
        if key == Qt.Key.Key_Escape:
            if not typing:
                if ed.S['tool'] != 'select':
                    ed.set_tool('select')
                elif ed.S['sel'] >= 0:
                    ed.select(-1)
                return True
            return False
        if typing:
            return False
        if key == Qt.Key.Key_Space:
            if not ev.isAutoRepeat():
                ed.space_down = True
                ed.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
            return True
        if mods & Qt.KeyboardModifier.ShiftModifier and key in (Qt.Key.Key_F1, Qt.Key.Key_F2):
            ed.cycle_ui(1 if key == Qt.Key.Key_F1 else -1)
            return True
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.AltModifier):
            return False
        txt = ev.text().lower()
        tool = next((x for x in TOOLS if x and x[1] == txt), None) if txt else None
        if tool:
            ed.set_tool(tool[0])
            return True
        el = ed.selected()
        if not el:
            return False
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            ed.remove()
            return True
        step = 10 if mods & Qt.KeyboardModifier.ShiftModifier else 1
        d = {Qt.Key.Key_Left: (-step, 0), Qt.Key.Key_Right: (step, 0), Qt.Key.Key_Up: (0, -step), Qt.Key.Key_Down: (0, step)}.get(key)
        if d:
            ed.snapshot()
            r = parse_rect(el['props'].get('rect'))
            el['props']['rect'] = join_rect([r[0] + d[0], r[1] + d[1], r[2], r[3]])
            ed.render()
            ed.update_rect_fields()
            return True
        return False


def main(argv=None):
    argv = sys.argv if argv is None else argv
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName('Frontier MRTE theme editor')
    app.setOrganizationName('Frontier')
    app.setStyle('Fusion')
    ed = Editor()
    kf = KeyFilter(ed)
    app.installEventFilter(kf)
    ed._key_filter = kf
    ed.show()
    args = [a for a in argv[1:] if not a.startswith('-')]
    if args and os.path.isdir(args[0]):
        ed.load_folder(args[0])
    if ed.cfg.value('seen', '') != APP_VERSION:   # the first time a new version is opened, show what is new
        ed.cfg.setValue('seen', APP_VERSION)
        QTimer.singleShot(300, lambda: ed.show_html('news'))
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
