# Aufgabensammlung

Grundgerüst für eine Aufgabensammlung in [typst](https://typst.app)

Tipp: Für eine optionale Bedienung per App nutzt diese Aufgabensammlung git. Daher bietet es sich an, dieses Repository in github zu forken und in den Settings auf `privat` zu stellen, damit keine SuS die Aufgabensammlung einsehen können. Dafür ist ein Konto bei github (oder anderem git-Anbieter) nötig. Für eine sichere Verbindung den eigenen, öffentlichen SSH-Schlüssel in git hinterlegen. Die mitgelieferte App setzt Schreibrechte auf das Repository voraus.

## Installation

Das geforkte, private Repository mit Schreibrechten an einen geeigneten Ort
clonen (mit hinterlegtem SSH-Schlüssel). Die Beispiele verwenden diese Pfade:

- Linux/macOS: `~/Dokumente/typst/pruefung`
- Windows: `%USERPROFILE%\Documents\typst\pruefung`

### Linux

```bash
mkdir -p ~/Dokumente/typst
cd ~/Dokumente/typst
git clone git@github.com:<github-benutzer>/aufgabensammlung.git pruefung

# Optional: Projektwurzel für die App merken
echo 'export TYPST_ROOT="$HOME/Dokumente/typst"' >> ~/.bashrc
source ~/.bashrc
```

### macOS

macOS verwendet standardmässig `zsh`; die Einrichtung entspricht sonst Linux:

```bash
mkdir -p ~/Dokumente/typst
cd ~/Dokumente/typst
git clone git@github.com:<github-benutzer>/aufgabensammlung.git pruefung

echo 'export TYPST_ROOT="$HOME/Dokumente/typst"' >> ~/.zshrc
source ~/.zshrc
```

### Windows

In PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Documents\typst" | Out-Null
Set-Location "$env:USERPROFILE\Documents\typst"
git clone git@github.com:<github-benutzer>/aufgabensammlung.git pruefung

$typstRoot = Join-Path $env:USERPROFILE "Documents\typst"
$env:TYPST_ROOT = $typstRoot
setx TYPST_ROOT "$typstRoot"
```

Für die reine Nutzung der Aufgabensammlung sind weder Python noch `tinymist`
nötig. Wer die App nicht verwenden will, kann die unbenötigten Dateien löschen.

Linux/macOS:

```bash
rm -Rf app.py requirements.txt linux macos windows
```

Windows (PowerShell):

```powershell
Remove-Item app.py,requirements.txt,linux,macos,windows -Recurse -Force
```

# App für die vereinfachte Generierung von Physikprüfungen (optional)

Lokale Web-App zum Steuern von `auswahl.typ` in der Typst-Aufgabensammlung.
Die App liest alle Aufgabenblöcke ein, zeigt sie nach Themen gruppiert an und
schreibt die Auswahl beim Speichern zurück. Zusätzlich gibt es eine
Tinymist-Vorschau, PDF-Export und einen Git-Commit-Button.

## Voraussetzungen

- Python 3.10 oder neuer
- [`tinymist`](https://github.com/Myriad-Dreamin/tinymist) im `PATH` (für Vorschau und PDF-Export)
- Git-Repository im Projektordner (für den Commit-Button)
- Projektordner mit `auswahl.typ`, `pruefung.typ` und `loesungen.typ`

Der Standard-Projektordner ist `$TYPST_ROOT/pruefung` (z. B.
`~/Dokumente/typst/pruefung`, wenn `TYPST_ROOT=~/Dokumente/typst` gesetzt ist).
Ist `TYPST_ROOT` nicht gesetzt, wird `~/pruefung` verwendet. Der Pfad kann in
der Seitenleiste geändert und mit **Als Standard speichern** dauerhaft
gespeichert werden. Alternativ lässt er sich über die Umgebungsvariable
`PRUEFUNG_ROOT` vorbelegen. Die Startskripte setzen `PRUEFUNG_ROOT`
automatisch auf den Repository-Ordner.

## Installation

### Linux

```bash
cd ~/Dokumente/typst/pruefung
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### macOS

```bash
cd ~/Dokumente/typst/pruefung
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Python 3.10 oder neuer und Git müssen installiert sein. Git lässt sich
beispielsweise über die Xcode Command Line Tools installieren:
`xcode-select --install`. Falls `python3` älter als 3.10 ist, Python von
[python.org](https://www.python.org/downloads/) oder über Homebrew installieren.

### Windows

```powershell
Set-Location "$env:TYPST_ROOT\pruefung"
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Falls `py` nicht vorhanden ist, `python` statt `py -3` verwenden. Git für
Windows und Python 3.10 oder neuer müssen installiert und im `PATH` sein. Eine
Aktivierung der virtuellen Umgebung ist nicht nötig; die Startskripte
verwenden direkt `.venv\Scripts\python.exe`.

`tinymist` muss unter allen Betriebssystemen im `PATH` liegen. Download und
Installationshinweise stehen auf der
[Tinymist-Projektseite](https://github.com/Myriad-Dreamin/tinymist).

`app.py` und `requirements.txt` müssen im Projektordner liegen oder von dort
aus erreichbar sein. Die App kann auch aus einem anderen Verzeichnis gestartet
werden; der Projektordner wird in der Seitenleiste eingestellt.

## Starten

### Manuell

Linux/macOS:

```bash
cd ~/Dokumente/typst/pruefung
source .venv/bin/activate
streamlit run app.py
```

Windows (PowerShell):

```powershell
Set-Location "$env:TYPST_ROOT\pruefung"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit öffnet normalerweise automatisch `http://localhost:8501` im Browser.
Falls nicht, die angezeigte URL manuell öffnen.

### Schnellstart über die Shell oder den Desktop

Für alle drei Betriebssysteme liegen im Repository Startskripte bereit, die
die App im Vordergrund oder Hintergrund starten, den Browser öffnen und den
Hintergrundserver wieder beenden können.

#### Linux

Diese Dateien ins Benutzerverzeichnis kopieren (und sicherstellen, dass
`pruefung` ausführbar ist: `chmod +x ~/.local/bin/pruefung`):

- `linux/pruefung` → `~/.local/bin/pruefung`
- `linux/physikpruefung.desktop` → `~/.local/share/applications/physikpruefung.desktop`

Im Desktop-/App-Menü heisst der Eintrag **Physikprüfung**. Er startet die App
im Hintergrund und öffnet den Browser. Über das Kontextmenü des Eintrags lässt
sich der Hintergrundserver auch wieder beenden.

Der Desktop-Eintrag ruft `pruefung` über den `PATH` auf. Stelle sicher, dass
`~/.local/bin` im `PATH` liegt (bei den meisten Distributionen ist das der
Fall); andernfalls im `.desktop`-Eintrag den vollständigen Pfad eintragen.

In der Shell stehen folgende Befehle zur Verfügung:

```bash
pruefung              # Vordergrund
pruefung --background # Hintergrund
pruefung --stop       # Hintergrundserver beenden
pruefung --status     # Status anzeigen
```

#### macOS

Die Skripte liegen im Ordner `macos`. Einmal ausführbar machen:

```bash
cd ~/Dokumente/typst/pruefung
chmod +x macos/pruefung macos/Physikpruefung.command
```

Danach im Terminal:

```bash
./macos/pruefung              # Vordergrund
./macos/pruefung --background # Hintergrund
./macos/pruefung --stop       # Hintergrundserver beenden
./macos/pruefung --status     # Status anzeigen
```

Für den Doppelklick im Finder **`macos/Physikpruefung.command`** verwenden.
Das Skript startet die App im Hintergrund und öffnet den Browser. Falls macOS
den Start blockiert, die Datei mit Rechtsklick → **Öffnen** bestätigen.
`Physikpruefung.command` ruft `pruefung` im selben Ordner auf; beide Dateien
müssen daher zusammen bleiben.

#### Windows

Die Skripte liegen im Ordner `windows`. Im Explorer:

- **`windows\pruefung.cmd`** doppelklicken: Start im Vordergrund mit
  Konsolenfenster.
- **`windows\Physikpruefung.cmd`** doppelklicken: Start im Hintergrund; das
  Konsolenfenster wird minimiert und geschlossen, sobald der Server läuft.

In `cmd.exe` oder PowerShell stehen ausserdem folgende Befehle zur Verfügung:

```bat
windows\pruefung.cmd --background
windows\pruefung.cmd --stop
windows\pruefung.cmd --status
```

`Physikpruefung.cmd` lässt sich auch an das Startmenü oder die Taskleiste
anheften. Die drei Dateien im Ordner `windows` müssen zusammen bleiben, weil
die `.cmd`-Wrapper das PowerShell-Skript im selben Ordner aufrufen. Die
Logdateien liegen unter
`%LOCALAPPDATA%\pruefung\streamlit.log` und
`%LOCALAPPDATA%\pruefung\streamlit.err.log`. Der Server lässt sich zusätzlich
jederzeit über **Server beenden** in der Seitenleiste der App stoppen.

Die `.cmd`-Wrapper starten PowerShell mit `-ExecutionPolicy Bypass`; direkte
Aufrufe von `pruefung.ps1` können je nach Ausführungsrichtlinie blockiert
werden.


## Bedienung

Die App ist in drei Bereiche gegliedert, die über die feste Kopfzeile
erreichbar sind. Der Zähler „x / 5“ bleibt beim Scrollen sichtbar.

1. **Prüfungsdaten**: Projektordner prüfen, Git-Status und Remote-Abgleich
   ansehen. Falls die lokale Kopie hinter `origin` liegt, erscheint direkt
   unter der Kopfzeile ein Warnbanner mit **Jetzt von GitHub holen**
   (Fast-Forward-Pull). Danach Prüfungsart, Klasse und Prüfungsdatum eingeben
   (z. B. `Prüfung`, `M5c`, `30.10.2026`).
2. **Aufgaben**: Mit **Alle abwählen** die bisherige Auswahl zurücksetzen.
   Aufgaben filtern und ankreuzen. Die Ampel zeigt, wann eine Aufgabe zuletzt
   gestellt wurde: 🔴 dieses Semester, 🟠 letztes Semester, 🟡 vorletztes
   Semester, 🟢 sonst. Es sind höchstens **5** Aufgaben erlaubt; bei mehr als
   5 wird der Zähler rot und die Aktionsbuttons werden gesperrt. Themen mit
   ausgewählten Aufgaben sind automatisch aufgeklappt.
3. **Aktionen**:
   - **Auswahl speichern** schreibt `auswahl.typ` neu. Vorher wird
     `auswahl.typ.bak` angelegt.
   - **Vorschau starten** startet `tinymist preview` für Prüfung oder
     Musterlösung. Die Vorschau erscheint eingebettet und kann zusätzlich in
     einem neuen Tab geöffnet werden.
   - **PDFs erzeugen** kompiliert `pruefung.typ` und `loesungen.typ` mit
     Tinymist. Kompilierfehler werden in der App angezeigt; vorhandene PDFs
     werden nur bei erfolgreicher Kompilierung ersetzt.
   - **In Git committen** führt `git add auswahl.typ` und
     `git commit -m "<Prüfungsart> <Klasse> <Prüfungsdatum>"` aus. Optional kann
     nach dem Commit gepusht werden.

Vorschau, PDF-Export und Git-Commit speichern die aktuelle Auswahl vorher
automatisch, damit sie immer dem Stand der Oberfläche entsprechen.


Die App committet bewusst nur `auswahl.typ`. `app.py`, `requirements.txt` und
die `.gitignore` können separat versioniert werden.

## Optionale eingebettete PDF-Anzeige

Für die Anzeige von PDFs direkt in Streamlit kann zusätzlich installiert
werden:

```bash
pip install "streamlit[pdf]"
```

Ohne dieses Extra stehen die PDF-Dateien weiterhin zum Download bereit.

## Typische Probleme

- **`tinymist` nicht gefunden:** `tinymist` installieren und Terminal bzw.
  PowerShell neu öffnen, damit der aktualisierte `PATH` übernommen wird.
- **`tinymist`-Vorschau startet nicht:** Port `23625` ist belegt. Alten
  Prozess beenden (Linux/macOS: `pkill -f "tinymist preview"`; Windows:
  Task-Manager).
- **Kompilierfehler:** Die vollständige Fehlermeldung erscheint im Bereich
  „PDF-Ergebnisse“. Häufig liegt ein Fehler in einer importierten
  Aufgabendatei vor.
- **Git-Commit schlägt fehl:** Prüfen, ob der Projektordner ein Git-Repository
  ist und `user.name`/`user.email` konfiguriert sind.
- **Falscher Projektordner:** In der Seitenleiste den Pfad korrigieren und
  **Projekt neu einlesen** klicken.
