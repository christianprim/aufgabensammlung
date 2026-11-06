# Aufgabensammlung

Grundgerüst für eine Aufgabensammlung in [typst](https://typst.app)

Tipp: Für eine optionale Bedienung per App nutzt diese Aufgabensammlung git. Daher bietet es sich an, dieses Repository in github zu forken und in den Settings auf `privat` zu stellen, damit keine SuS die Aufgabensammlung einsehen können. Dafür ist ein Konto bei github (oder anderem git-Anbieter) nötig. Für eine sichere Verbindung den eigenen, öffentlichen SSH-Schlüssel in git hinterlegen. Die mitgelieferte App setzt Schreibrechte auf das Repository voraus.

## Installation (für Linux, sinngemäss für andere OS)

Das geforkte, private Repository mit Schreibrechten nach beispielsweise `~/Dokumente/typst/pruefung` clonen (mit hinterlegtem SSH-Schlüssel) und die Umgebungsvariable `TYPST_ROOT` setzen:

```bash
mkdir -p ~/Dokumente/typst
cd ~/Dokumente/typst
git clone git@github.com:<github-benutzer>/aufgabensammlung.git pruefung
echo "export TYPST_ROOT=$HOME/Dokumente/typst" >> ~/.bashrc
source ~/.bashrc
```
Falls die App nicht gewünscht wird, können die unbenötigten Dateien gelöscht werden:

```bash
rm -Rf app.py requirements.txt linux
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
`PRUEFUNG_ROOT` vorbelegen.

## Installation

```bash
cd $TYPST_ROOT/pruefung

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

`app.py` und `requirements.txt` müssen im Projektordner liegen oder von dort
aus erreichbar sein. Die App kann auch aus einem anderen Verzeichnis gestartet
werden; der Projektordner wird in der Seitenleiste eingestellt.

## Starten

### Manuell

```bash
streamlit run app.py
```

Streamlit öffnet normalerweise automatisch `http://localhost:8501` im Browser.
Falls nicht, die angezeigte URL manuell öffnen.


### Schnellstart über die Shell oder Desktop (Linux)

Für Linux-Systeme liegen im Ordner `linux` zwei Dateien vor, die einen schnelleren 
Start über die grafische Oberfläche oder die Shell erlauben.

Diese Dateien ins Benutzerverzeichnis kopieren (und sicherstellen, dass `pruefung` 
ausführbar ist: `chmod +x ~/.local/bin/pruefung`):

- `linux/pruefung` → `~/.local/bin/pruefung`
- `linux/physikpruefung.desktop` → `~/.local/share/applications/physikpruefung.desktop`

Im Desktop-/App-Menü heisst der Eintrag **Physikprüfung**. Er startet die App im
Hintergrund und öffnet den Browser. Über das Kontextmenü des Eintrags lässt
sich der Hintergrundserver auch wieder beenden.


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

- **`tinymist`-Vorschau startet nicht:** Port `23625` ist belegt. Alten
  Prozess beenden, z. B. `pkill -f "tinymist preview"`.
- **Kompilierfehler:** Die vollständige Fehlermeldung erscheint im Bereich
  „PDF-Ergebnisse“. Häufig liegt ein Fehler in einer importierten
  Aufgabendatei vor.
- **Git-Commit schlägt fehl:** Prüfen, ob der Projektordner ein Git-Repository
  ist und `user.name`/`user.email` konfiguriert sind.
- **Falscher Projektordner:** In der Seitenleiste den Pfad korrigieren und
  **Projekt neu einlesen** klicken.
