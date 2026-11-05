#!/usr/bin/env python3
"""
Streamlit-App zur Auswahl von Prüfungsaufgaben aus einer Typst-Aufgabensammlung.

Die App liest die Datei ``auswahl.typ``, zeigt alle Aufgabenblöcke gruppiert nach
Themen an und schreibt die Auswahl beim Speichern zurück. Zusätzlich können
Prüfung und Musterlösung mit Typst/Tinymist angesehen und als PDF erzeugt
sowie die Änderung an ``auswahl.typ`` in Git committet werden.

Starten:
    streamlit run app.py

Benötigt: Python 3.10+, Streamlit und tinymist im PATH.
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

import streamlit as st

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

APP_TITLE = "Physikprüfung"
APP_ICON = "📝"

AUSWAHL_FILENAME = "auswahl.typ"
BACKUP_SUFFIX = ".bak"
PRUEFUNG_FILENAME = "pruefung.typ"
LOESUNGEN_FILENAME = "loesungen.typ"
MAX_AUFGABEN = 5

SECTION_DATA = "Prüfungsdaten"
SECTION_TASKS = "Aufgaben"
SECTION_ACTIONS = "Aktionen"
SECTIONS = (SECTION_DATA, SECTION_TASKS, SECTION_ACTIONS)
SECTION_CLASS = {
    SECTION_DATA: "section_data",
    SECTION_TASKS: "section_tasks",
    SECTION_ACTIONS: "section_actions",
}

STICKY_HEADER_CSS = """
<style>
/* Kopfzeile: bleibt beim Scrollen oben stehen. Das Kleben muss auf dem
   Streamlit-Wrapper liegen - der innere Container ist nur so hoch wie sein
   Inhalt und hätte sonst keinen Spielraum zum Mitschrollen. */
[data-testid="stLayoutWrapper"]:has(> .st-key-sticky_header) {
    position: sticky;
    top: 3.75rem;
    z-index: 1000;
}
.st-key-sticky_header {
    /* Canvas folgt dem hellen/dunklen Streamlit-Theme; die leichte
       Transparenz lässt den Blur darunter wirken. */
    background: Canvas;
    background: color-mix(in srgb, Canvas 92%, transparent);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(128, 128, 128, 0.28);
    border-radius: 0.65rem;
    padding: 0.55rem 0.8rem;
    margin-bottom: 0.85rem;
    box-shadow: 0 3px 12px rgba(0, 0, 0, 0.12);
}
.st-key-sticky_header [data-testid="stSegmentedControl"] {
    margin-bottom: 0;
}
/* Streamlits Markdown-Container hat standardmässig -1rem unteren Rand.
   Im Kopf würde das Titel und Zähler aus der Mitte ziehen. */
.st-key-sticky_header [data-testid="stMarkdownContainer"] {
    margin-bottom: 0;
}
/* Titel links, Navigation mittig, Zähler rechts – jeweils echt zentriert. */
.st-key-sticky_header [data-testid="stHorizontalBlock"] {
    align-items: center;
}
.st-key-sticky_header [data-testid="stColumn"]:last-child {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 0;
}
.st-key-sticky_header [data-testid="stColumn"]:last-child [data-testid="stMarkdown"] {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    width: 100%;
    margin: 0;
}
.st-key-sticky_header [data-testid="stColumn"]:last-child [data-testid="stMarkdownContainer"] {
    display: flex;
    justify-content: flex-end;
    width: 100%;
    margin-bottom: 0;
}
.st-key-sticky_header [data-testid="stColumn"]:last-child [data-testid="stMarkdownContainer"] > div {
    width: auto;
    white-space: nowrap;
}
/* Auf schmalen Fenstern rutschen die drei Teile untereinander. */
@media (max-width: 640px) {
    .st-key-sticky_header [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap;
        gap: 0.4rem;
    }
    .st-key-sticky_header [data-testid="stColumn"] {
        flex: 1 1 100%;
        width: 100%;
    }
}
/* Es ist immer nur der gewaehlte Bereich sichtbar. Alle Bereiche werden
   trotzdem gerendert, damit Streamlit die Widget-Zustände nicht verwirft. */
.st-key-section_data,
.st-key-section_tasks,
.st-key-section_actions {
    display: none;
}
/* Unsichtbare Helfer-Iframes: Sidebar zuklappen und nach oben scrollen. */
.st-key-sidebar_collapse_helper,
.st-key-scroll_top_helper {
    display: none;
}
/* Der Wrapper des Helfers wuerde sonst trotz leerem Inhalt einen Abstand
   im Seitenlayout erzeugen. */
[data-testid="stLayoutWrapper"]:has(> .st-key-sidebar_collapse_helper),
[data-testid="stLayoutWrapper"]:has(> .st-key-scroll_top_helper) {
    display: none;
}
/* "Deploy" oben rechts ausblenden; das Drei-Punkte-Menue bleibt. */
[data-testid="stAppDeployButton"] {
    display: none;
}
</style>
"""

DEFAULT_ROOT = Path(
    os.environ.get(
        "PRUEFUNG_ROOT",
        Path(os.environ.get("TYPST_ROOT", Path.home())) / "pruefung",
    )
).expanduser()

PREVIEW_HOST = "127.0.0.1"
PREVIEW_PORT = 23625
PREVIEW_URL = f"http://{PREVIEW_HOST}:{PREVIEW_PORT}"

SAVE_ROOT_KEY = "save_root_checked"
SAVED_ROOT_FILE = Path(
    os.environ.get("PRUEFUNG_HOME_FILE", str(Path(os.environ["HOME"]) / ".local/state/pruefung-root"))
)

def load_saved_root() -> str | None:
    """Liest den in der App gespeicherten Standardprojektordner."""
    try:
        raw = SAVED_ROOT_FILE.read_text(encoding="utf-8")
        value = raw.strip()
        return value if value else None
    except OSError:
        return None


def save_saved_root(path: str | None) -> bool:
    """Speichert den geänderten Projektpfad. Gibt True zurück, wenn etwas gespeichert wurde."""
    try:
        path = (path or "").strip()
    except TypeError:
        return False
    if not path:
        try:
            SAVED_ROOT_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    directory = Path(os.environ["HOME"]) / ".local" / "state"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        SAVED_ROOT_FILE.write_text(f"{path}\n", encoding="utf-8")
    except OSError:
        return False
    return True


def local_basename(path: str | Path) -> str:
    """Liefert den Dateinamen eines Verzeichnispfads, z. B. aus ~/Dokumente/typst → dokustypst/pruefung."""
    value = str(path).replace("\\", "/")
    parts = value.split("/")
    while parts and parts[-1] == "":
        parts.pop()
    if len(parts) >= 2 and parts[-2] == "Dokumente":
        return "/".join(parts[-3:])
    return ".".join(p for p in parts if p) or "."


# ---------------------------------------------------------------------------
# Reguläre Ausdrücke
# ---------------------------------------------------------------------------

# Eine Kommentarzeile, optional mit einem Leerzeichen nach "//".
COMMENT_PREFIX_RE = re.compile(r"^(\s*)//\s?(.*)$")

# Aufgabenimport. Der Pfad ist eindeutig und dient als stabile ID.
IMPORT_RE = re.compile(
    r'^\s*#import\s+"(?P<path>[^"]+)"\s*:\s*'
    r"aufgabe\s*,\s*(?:lösung|loesung)\b"
)

# "// Eingesetzt:" – der Tippfehler "Eingesetz:" kommt in der echten Datei vor.
HISTORY_RE = re.compile(
    r"^\s*//\s*Eingesetz(?:t)?\s*:\s*(?P<history>.*)$",
    re.IGNORECASE,
)

UNDERLINE_THEME_RE = re.compile(r"^={3,}$")
UNDERLINE_SUBTOPIC_RE = re.compile(r"^-{3,}$")

# Für die erste, nicht unterstrichene Überschrift "GRUNDLAGEN / DICHTE".
UNMARKED_THEME_RE = re.compile(r"^[A-ZÄÖÜ0-9 /&+.\-]+$")

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Erhält die Semester-Label aus der Historie, z. B. "(HS26)" oder "(FS23)".
HISTORY_SEMESTER_RE = re.compile(r"\((HS|FS)([0-9]{2})\)")


# ---------------------------------------------------------------------------
# Fehlerklassen
# ---------------------------------------------------------------------------


class AppError(Exception):
    """Basisklasse für erwartbare Fehler der App."""


class ParseError(AppError):
    """Fehler beim Einlesen von auswahl.typ."""


class SaveError(AppError):
    """Fehler beim Zurückschreiben von auswahl.typ."""


class CommandError(AppError):
    """Fehler beim Ausführen eines externen Befehls."""


class PreviewError(AppError):
    """Fehler beim Starten der Tinymist-Vorschau."""


class GitError(AppError):
    """Fehler bei Git-Operationen."""


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------


@dataclass
class Task:
    task_id: str
    title: str
    path: str
    theme: str
    subtopic: str
    active: bool
    history: str
    title_line: int
    history_line: int | None
    import_start: int
    import_end: int
    import_lines: list[str]


@dataclass
class SelectionFile:
    path: Path
    lines: list[str]
    tasks: list[Task]
    art: str
    klasse: str
    datum: str
    raw_text: str
    newline: str
    ends_with_newline: bool
    mtime_ns: int
    size: int


@dataclass
class ExamInfo:
    art: str
    klasse: str
    datum: str
    exam_date: date
    semester: str
    history_entry: str


@dataclass
class SaveResult:
    changed: bool
    path: Path
    backup_path: Path | None
    active_count: int
    parsed: SelectionFile


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass
class PdfResult:
    label: str
    filename: str
    pdf_path: Path | None
    stdout: str
    stderr: str
    error: str | None = None


@dataclass
class GitResult:
    committed: bool
    commit_hash: str
    stdout: str
    stderr: str
    push_output: str = ""
    push_error: str = ""


# ---------------------------------------------------------------------------
# Kleine Text-Helfer
# ---------------------------------------------------------------------------


def strip_ansi(text: str) -> str:
    """Entfernt ANSI-Farbcodes aus Typst-/Git-Ausgaben."""
    return ANSI_RE.sub("", text)


def comment_text(line: str) -> str | None:
    """Liefert den Inhalt einer Typst-Kommentarzeile oder None."""
    match = COMMENT_PREFIX_RE.match(line)
    return match.group(2) if match else None


def uncomment(line: str) -> str:
    """Entfernt genau ein führendes ``//`` (mit optionalem Leerzeichen)."""
    match = COMMENT_PREFIX_RE.match(line)
    if not match:
        return line
    return match.group(1) + match.group(2)


def typst_escape(value: str) -> str:
    """Maskiert einen String für Typst."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def typst_unescape(value: str) -> str:
    """Hebt die Maskierung eines einfachen Typst-Strings auf."""
    return value.replace('\\"', '"').replace("\\\\", "\\")


def paren_delta(text: str) -> int:
    """Zählt Klammern außerhalb von Typst-Strings."""
    delta = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        else:
            if char == '"':
                in_string = True
            elif char == "(":
                delta += 1
            elif char == ")":
                delta -= 1
    return delta


def previous_content_line(lines: Sequence[str], start: int) -> int:
    """Sucht rückwärts die letzte inhaltliche Zeile (keine Leer-/Trennzeile)."""
    index = start - 1
    while index >= 0:
        stripped = lines[index].strip()
        if stripped and stripped != "//":
            return index
        index -= 1
    return -1


# ---------------------------------------------------------------------------
# Parsen von auswahl.typ
# ---------------------------------------------------------------------------


def is_unmarked_theme(text: str, lines: Sequence[str], index: int) -> bool:
    """Erkennt die erste Überschrift im Stil ``// GRUNDLAGEN / DICHTE``."""
    if " / " not in text or not UNMARKED_THEME_RE.fullmatch(text):
        return False

    next_index = index + 1
    while next_index < len(lines) and not lines[next_index].strip():
        next_index += 1
    if next_index >= len(lines):
        return False

    next_text = comment_text(lines[next_index])
    if next_text is None:
        return False
    next_text = next_text.strip()
    if UNDERLINE_THEME_RE.fullmatch(next_text) or UNDERLINE_SUBTOPIC_RE.fullmatch(next_text):
        return False
    if HISTORY_RE.match(lines[next_index]):
        return False
    if re.match(r"^\s*//?\s*#import\b", lines[next_index]):
        return False
    return True


def annotate_sections(lines: Sequence[str]) -> tuple[list[str], list[str]]:
    """
    Ordnet jeder Zeile das aktuelle Thema und Unterthema zu.

    ``// THEMA`` + ``// =====`` beginnt ein Thema,
    ``// UNTERTHEMA`` + ``// -----`` beginnt ein Unterthema.
    """
    theme = "Ohne Thema"
    subtopic = ""
    theme_at = [theme] * len(lines)
    subtopic_at = [subtopic] * len(lines)

    for index, line in enumerate(lines):
        text = comment_text(line)
        if text is not None:
            text = text.strip()
            next_text = ""
            if index + 1 < len(lines):
                following = comment_text(lines[index + 1])
                if following is not None:
                    next_text = following.strip()

            if text and UNDERLINE_THEME_RE.fullmatch(next_text):
                theme = text
                subtopic = ""
            elif text and UNDERLINE_SUBTOPIC_RE.fullmatch(next_text):
                subtopic = text
            elif text and is_unmarked_theme(text, lines, index):
                parts = re.split(r"\s+/\s+", text, maxsplit=1)
                theme = parts[0].strip()
                subtopic = parts[1].strip() if len(parts) > 1 else ""

        theme_at[index] = theme
        subtopic_at[index] = subtopic

    return theme_at, subtopic_at


def parse_header_value(lines: Sequence[str], name: str, default: str = "") -> str:
    """Liest ``#let name = "..."`` (auch auskommentiert) aus dem Kopf."""
    active_re = re.compile(rf'^\s*#let\s+{re.escape(name)}\s*=\s*"(.*)"\s*$')
    commented_re = re.compile(rf'^\s*//\s*#let\s+{re.escape(name)}\s*=\s*"(.*)"\s*$')

    for regex in (active_re, commented_re):
        for line in lines:
            match = regex.match(line)
            if match:
                return typst_unescape(match.group(1))
    return default


def find_import_end(lines: Sequence[str], start: int) -> int:
    """Findet das Ende eines (ggf. mehrzeiligen) Import-Statements."""
    balance = 0
    for index in range(start, len(lines)):
        balance += paren_delta(uncomment(lines[index]))
        if balance <= 0:
            return index
    raise ParseError(
        f"Der Import ab Zeile {start + 1} wird nicht durch eine schließende "
        "Klammer beendet."
    )


def find_task_metadata(
    lines: Sequence[str], import_start: int
) -> tuple[int, int | None, str, str]:
    """
    Sucht Titel und Historie vor einem Import.

    Rückgabe: (title_line, history_line, title, history)
    """
    index = previous_content_line(lines, import_start)

    history_line: int | None = None
    if index >= 0:
        history_match = HISTORY_RE.match(lines[index])
        if history_match:
            history_line = index
            index = previous_content_line(lines, index)

    title_line = index
    if title_line < 0:
        raise ParseError(
            f"Vor dem Import in Zeile {import_start + 1} wurde kein Titel gefunden."
        )

    title_text = comment_text(lines[title_line])
    if title_text is None:
        raise ParseError(
            f"Der Titel vor dem Import in Zeile {import_start + 1} ist keine "
            "Kommentarzeile."
        )

    title = title_text.strip()
    if not title:
        raise ParseError(
            f"Der Titel vor dem Import in Zeile {import_start + 1} ist leer."
        )
    if UNDERLINE_THEME_RE.fullmatch(title) or UNDERLINE_SUBTOPIC_RE.fullmatch(title):
        raise ParseError(
            f"Vor dem Import in Zeile {import_start + 1} steht nur eine "
            "Überschriften-Unterstreichung, aber kein Aufgabentitel."
        )

    history = ""
    if history_line is not None:
        history_match = HISTORY_RE.match(lines[history_line])
        if history_match:
            history = history_match.group("history").strip()

    return title_line, history_line, title, history


def parse_selection_file(path: Path) -> SelectionFile:
    """Liest und parst auswahl.typ vollständig."""
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ParseError(f"Datei nicht gefunden: {path}")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise ParseError(
            f"Datei ist nicht gültig UTF-8-kodiert: {exc}"
        ) from exc
    except OSError as exc:
        raise ParseError(f"Datei konnte nicht gelesen werden: {exc}") from exc

    newline = "\r\n" if "\r\n" in raw_text else "\n"
    ends_with_newline = raw_text.endswith(("\n", "\r"))
    lines = raw_text.splitlines()
    theme_at, subtopic_at = annotate_sections(lines)

    tasks: list[Task] = []
    seen_paths: dict[str, int] = {}

    index = 0
    while index < len(lines):
        match = IMPORT_RE.match(uncomment(lines[index]))
        if not match:
            index += 1
            continue

        import_start = index
        import_end = find_import_end(lines, import_start)
        import_path = match.group("path")

        if import_path in seen_paths:
            raise ParseError(
                f"Doppelter Importpfad {import_path!r} in Zeile "
                f"{seen_paths[import_path] + 1} und {import_start + 1}."
            )
        seen_paths[import_path] = import_start

        title_line, history_line, title, history = find_task_metadata(
            lines, import_start
        )
        active = not lines[import_start].lstrip().startswith("//")
        tasks.append(
            Task(
                task_id=import_path,
                title=title,
                path=import_path,
                theme=theme_at[title_line],
                subtopic=subtopic_at[title_line],
                active=active,
                history=history,
                title_line=title_line,
                history_line=history_line,
                import_start=import_start,
                import_end=import_end,
                import_lines=list(lines[import_start : import_end + 1]),
            )
        )

        index = import_end + 1

    if not tasks:
        raise ParseError(
            "In der Datei wurden keine Aufgabenblöcke gefunden. Erwartet wird "
            'ein Block mit #import "...": aufgabe, lösung.'
        )

    stat = path.stat()
    art = parse_header_value(lines, "art", "Prüfung")
    klasse = parse_header_value(lines, "klasse", "")
    datum = parse_header_value(lines, "datum", "")

    return SelectionFile(
        path=path,
        lines=lines,
        tasks=tasks,
        art=art,
        klasse=klasse,
        datum=datum,
        raw_text=raw_text,
        newline=newline,
        ends_with_newline=ends_with_newline,
        mtime_ns=stat.st_mtime_ns,
        size=stat.st_size,
    )


# ---------------------------------------------------------------------------
# Datum, Semester und Historie
# ---------------------------------------------------------------------------


def parse_exam_date(text: str) -> date:
    """Parst ein Datum im Format TT.MM.JJJJ (auch weitere gängige Formate)."""
    cleaned = text.strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f"Ungültiges Datum: {text!r}. Erwartet wird z. B. 30.10.2026."
    )


def semester_label(exam_date: date) -> str:
    """FS von ISO-KW 9 bis 28, sonst HS; Jahr zweistellig."""
    week = exam_date.isocalendar().week
    semester = "FS" if 9 <= week <= 28 else "HS"
    return f"{semester}{exam_date.year % 100:02d}"


def is_nachpruefung(art: str) -> bool:
    normalized = art.strip().casefold()
    return (
        normalized.startswith("nachprüfung")
        or normalized.startswith("nachpruefung")
        or normalized == "np"
    )


def clean_class_for_history(klasse: str) -> str:
    """Entfernt für die Historie die Klammer um das Schwerpunktfach."""
    cleaned = re.sub(r"\s*\(([^()]*)\)\s*", r" \1 ", klasse)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^NP\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def build_history_entry(art: str, klasse: str, exam_date: date) -> str:
    """Baut den Eintrag für die Zeile ``// Eingesetzt:``."""
    semester = semester_label(exam_date)
    if is_nachpruefung(art):
        return f"NP {clean_class_for_history(klasse)} ({semester})"
    return f"{klasse.strip()} ({semester})"


def normalize_text_field(value: str) -> str:
    """Vereinheitlicht Leerzeichen in einem einzeiligen Eingabefeld."""
    return re.sub(r"\s+", " ", value.strip())


def parse_semester_label(label: str) -> tuple[str, int] | None:
    """Liefert (Semester, Jahr) aus einem Label wie „HS26“ oder „FS23“."""
    label = label.strip()
    if len(label) >= 4 and label[:2] in ("FS", "HS") and label[2:].isdigit():
        return label[:2], int(label[2:])
    return None


def semester_rank(sem: str, year: int) -> int:
    """Chronologischer Rang: FS25 < HS25 < FS26 < HS26 < …"""
    return year * 2 + (0 if sem == "FS" else 1)


def compute_task_recency(history: str, current_semester_label: str) -> str:
    """
    Ermittelt, wie frisch eine Aufgabe zuletzt gestellt wurde.

    - „rot“: in diesem Semester bereits gestellt
    - „orange“: im letzten Semester gestellt
    - „gelb“: im vorletzten Semester gestellt
    - „grün“: sonst (auch ohne Historie)
    """
    if not history or not current_semester_label:
        return "green"

    pairs = [
        parse_semester_label(match[0] + match[1])
        for match in HISTORY_SEMESTER_RE.findall(history)
    ]
    pairs = [p for p in pairs if p is not None]
    if not pairs:
        return "green"

    current = parse_semester_label(current_semester_label)
    if current is None:
        return "green"

    best = max(pairs, key=lambda p: (p[1], p[0] == "HS"))
    if best == current:
        return "red"

    best_rank = semester_rank(best[0], best[1])
    current_rank = semester_rank(current[0], current[1])
    diff = current_rank - best_rank
    if diff == 1:
        return "orange"
    if diff == 2:
        return "yellow"
    return "green"


def validate_exam(art: str, klasse: str, datum: str) -> tuple[ExamInfo | None, list[str]]:
    """Validiert die drei Kopffelder und berechnet Semester/Historieneintrag."""
    art = normalize_text_field(art)
    klasse = normalize_text_field(klasse)
    datum = datum.strip()
    errors: list[str] = []

    if not art:
        errors.append("Prüfungsart fehlt.")
    if not klasse:
        errors.append("Klasse fehlt.")

    exam_date: date | None = None
    if not datum:
        errors.append("Prüfungsdatum fehlt.")
    else:
        try:
            exam_date = parse_exam_date(datum)
        except ValueError as exc:
            errors.append(str(exc))

    if exam_date is None:
        return None, errors

    if is_nachpruefung(art) and not clean_class_for_history(klasse):
        errors.append("Klasse enthält nach dem Entfernen der Klammern keinen Text.")

    if errors:
        return None, errors

    semester = semester_label(exam_date)
    history_entry = build_history_entry(art, klasse, exam_date)
    return (
        ExamInfo(
            art=art,
            klasse=klasse,
            datum=datum,
            exam_date=exam_date,
            semester=semester,
            history_entry=history_entry,
        ),
        [],
    )


def normalize_history_item(text: str) -> str:
    """Normalisiert einen Historieneintrag für den Duplikatvergleich."""
    text = text.casefold()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*\(\s*", "(", text)
    text = re.sub(r"\s*\)\s*", ")", text)
    return text.strip(" ,")


def append_history(line: str, entry: str) -> str:
    """Ergänzt einen Eintrag in einer ``// Eingesetzt:``-Zeile, ohne Duplikate."""
    match = HISTORY_RE.match(line)
    if not match:
        return line

    current = match.group("history").strip()
    items = [item.strip() for item in current.split(",") if item.strip()]
    entry_normalized = normalize_history_item(entry)
    if any(normalize_history_item(item) == entry_normalized for item in items):
        return line

    indent = line[: len(line) - len(line.lstrip())]
    if current:
        if not current.endswith(","):
            current += ","
        return f"{indent}// Eingesetzt: {current} {entry},"

    return f"{indent}// Eingesetzt: {entry},"


# ---------------------------------------------------------------------------
# Schreiben von auswahl.typ
# ---------------------------------------------------------------------------


def set_import_active(block: Sequence[str], active: bool) -> list[str]:
    """Kommentiert einen kompletten Importblock aus oder wieder ein."""
    if active:
        return [uncomment(line) for line in block]

    result: list[str] = []
    for line in block:
        if line.lstrip().startswith("//"):
            result.append(line)
        else:
            result.append("// " + line)
    return result


def set_header_value(lines: list[str], name: str, value: str) -> None:
    """Setzt ``#let name = "..."`` im Kopf; fügt die Zeile bei Bedarf ein."""
    escaped = typst_escape(value)
    active_re = re.compile(rf'^(\s*)#let\s+{re.escape(name)}\s*=\s*".*"\s*$')

    for index, line in enumerate(lines):
        if active_re.match(line):
            lines[index] = f'#let {name} = "{escaped}"'
            return

    commented_re = re.compile(
        rf'^\s*//\s*#let\s+{re.escape(name)}\s*=\s*".*"\s*$'
    )
    for index, line in enumerate(lines):
        if commented_re.match(line):
            lines.insert(index, f'#let {name} = "{escaped}"')
            return

    insert_at = 0
    for index, line in enumerate(lines):
        if re.match(r"^\s*#let\s+daten\s*=", line):
            insert_at = index
            break
    lines.insert(insert_at, f'#let {name} = "{escaped}"')


def render_selection_file(
    parsed: SelectionFile, info: ExamInfo, selected_ids: set[str]
) -> str:
    """Erzeugt den neuen Inhalt von auswahl.typ."""
    lines = list(parsed.lines)
    selected = set(selected_ids)

    # Von unten nach oben arbeiten, damit Einfügungen die noch nicht
    # bearbeiteten Indizes nicht verschieben.
    for task in sorted(parsed.tasks, key=lambda item: item.import_start, reverse=True):
        is_selected = task.task_id in selected

        block = lines[task.import_start : task.import_end + 1]
        new_block = set_import_active(block, is_selected)
        if new_block != block:
            lines[task.import_start : task.import_end + 1] = new_block

        if not is_selected:
            continue

        if task.history_line is not None:
            new_history = append_history(lines[task.history_line], info.history_entry)
            if new_history != lines[task.history_line]:
                lines[task.history_line] = new_history
        else:
            title_line = lines[task.title_line]
            indent = title_line[: len(title_line) - len(title_line.lstrip())]
            lines.insert(
                task.title_line + 1,
                f"{indent}// Eingesetzt: {info.history_entry},",
            )

    set_header_value(lines, "art", info.art)
    set_header_value(lines, "klasse", info.klasse)
    set_header_value(lines, "datum", info.datum)

    text = "\n".join(lines)
    if parsed.ends_with_newline:
        text += "\n"
    if parsed.newline != "\n":
        text = text.replace("\n", parsed.newline)
    return text


def check_file_signature(parsed: SelectionFile) -> None:
    """Verhindert, dass eine extern geänderte Datei überschrieben wird."""
    try:
        current_text = parsed.path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SaveError(f"Datei ist nicht mehr lesbar: {exc}") from exc

    if current_text != parsed.raw_text:
        raise SaveError(
            "Die Datei auswahl.typ wurde seit dem Einlesen extern geändert. "
            "Bitte zuerst 'Projekt neu einlesen' klicken."
        )


def save_selection(
    parsed: SelectionFile, info: ExamInfo, selected_ids: set[str]
) -> SaveResult:
    """Schreibt die Auswahl atomar zurück und verifiziert das Ergebnis."""
    selected = set(selected_ids)
    known = {task.task_id for task in parsed.tasks}
    unknown = selected - known
    if unknown:
        raise SaveError(
            "Unbekannte Aufgaben-ID(s): " + ", ".join(sorted(unknown))
        )
    if len(selected) > MAX_AUFGABEN:
        raise SaveError(
            f"Es sind {len(selected)} Aufgaben ausgewählt, erlaubt sind "
            f"höchstens {MAX_AUFGABEN}."
        )

    check_file_signature(parsed)
    new_text = render_selection_file(parsed, info, selected)

    if new_text == parsed.raw_text:
        return SaveResult(
            changed=False,
            path=parsed.path,
            backup_path=None,
            active_count=len(selected),
            parsed=parsed,
        )

    backup_path = parsed.path.with_name(parsed.path.name + BACKUP_SUFFIX)
    try:
        shutil.copy2(parsed.path, backup_path)
        # copy2 uebernimmt die mtime der Quelle; fuer die Anzeige soll das
        # Backup aber den Zeitpunkt der Sicherung tragen.
        os.utime(backup_path, None)
    except OSError as exc:
        raise SaveError(
            f"Backup {backup_path.name} konnte nicht erstellt werden: {exc}"
        ) from exc

    tmp_path = parsed.path.with_name(parsed.path.name + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="") as handle:
            handle.write(new_text)
            handle.flush()
            os.fsync(handle.fileno())

        shutil.copymode(parsed.path, tmp_path)
        os.replace(tmp_path, parsed.path)

        new_parsed = parse_selection_file(parsed.path)
        new_active = {task.task_id for task in new_parsed.tasks if task.active}
        if new_active != selected:
            raise SaveError(
                "Verifikation fehlgeschlagen: Die aktiven Aufgaben in der "
                "geschriebenen Datei stimmen nicht mit der Auswahl überein."
            )
        if (new_parsed.art, new_parsed.klasse, new_parsed.datum) != (
            info.art,
            info.klasse,
            info.datum,
        ):
            raise SaveError(
                "Verifikation fehlgeschlagen: Die Kopfdaten in der "
                "geschriebenen Datei stimmen nicht mit den Eingaben überein."
            )
    except Exception as exc:
        try:
            shutil.copy2(backup_path, parsed.path)
        except OSError as restore_exc:
            raise SaveError(
                f"Fehler beim Speichern ({exc}); außerdem konnte das Backup "
                f"nicht wiederhergestellt werden: {restore_exc}"
            ) from exc
        if isinstance(exc, SaveError):
            raise
        raise SaveError(f"Speichern fehlgeschlagen: {exc}") from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    return SaveResult(
        changed=True,
        path=parsed.path,
        backup_path=backup_path,
        active_count=len(selected),
        parsed=new_parsed,
    )


# ---------------------------------------------------------------------------
# Externe Befehle
# ---------------------------------------------------------------------------


def run_command(
    command: Sequence[str],
    cwd: Path,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Führt einen Befehl ohne Shell aus und fängt typische Fehler ab."""
    command_list = [str(part) for part in command]
    try:
        result = subprocess.run(
            command_list,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        raise CommandError(f"Befehl nicht gefunden: {command_list[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise CommandError(
            f"Timeout nach {timeout} s: {' '.join(command_list)}"
        ) from exc

    return CommandResult(
        command=command_list,
        returncode=result.returncode,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
    )


def compile_pdf(root: Path, typ_filename: str) -> PdfResult:
    """Kompiliert eine Typst-Datei in eine PDF und fängt Fehler ab."""
    label = "Prüfung" if typ_filename == PRUEFUNG_FILENAME else "Musterlösung"
    typ_path = root / typ_filename

    if not typ_path.is_file():
        return PdfResult(
            label=label,
            filename=typ_filename,
            pdf_path=None,
            stdout="",
            stderr="",
            error=f"Datei nicht gefunden: {typ_path}",
        )

    tinymist = shutil.which("tinymist")
    if not tinymist:
        return PdfResult(
            label=label,
            filename=typ_filename,
            pdf_path=None,
            stdout="",
            stderr="",
            error="tinymist wurde nicht im PATH gefunden.",
        )

    pdf_name = typ_path.with_suffix(".pdf").name
    target = root / pdf_name
    tmp_target: Path | None = None

    try:
        with tempfile.TemporaryDirectory(prefix="pruefung-pdf-") as tmp_dir:
            tmp_pdf = Path(tmp_dir) / pdf_name
            env = {**os.environ, "NO_COLOR": "1"}
            result = run_command(
                [
                    tinymist,
                    "compile",
                    "--pdf-standard",
                    "2.0",
                    "--no-pdf-tags",
                    "--root",
                    str(root),
                    str(typ_path),
                    str(tmp_pdf),
                ],
                cwd=root,
                timeout=180,
                env=env,
            )

            if result.returncode != 0:
                return PdfResult(
                    label=label,
                    filename=typ_filename,
                    pdf_path=None,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    error="tinymist compile ist fehlgeschlagen.",
                )
            if not tmp_pdf.is_file():
                return PdfResult(
                    label=label,
                    filename=typ_filename,
                    pdf_path=None,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    error="tinymist hat keine PDF-Datei erzeugt.",
                )

            data = tmp_pdf.read_bytes()
            tmp_target = target.with_name(target.name + ".tmp")
            with open(tmp_target, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_target, target)

            return PdfResult(
                label=label,
                filename=typ_filename,
                pdf_path=target,
                stdout=result.stdout,
                stderr=result.stderr,
            )
    except CommandError as exc:
        return PdfResult(
            label=label,
            filename=typ_filename,
            pdf_path=None,
            stdout="",
            stderr="",
            error=str(exc),
        )
    except OSError as exc:
        return PdfResult(
            label=label,
            filename=typ_filename,
            pdf_path=None,
            stdout="",
            stderr="",
            error=f"PDF konnte nicht geschrieben werden: {exc}",
        )
    finally:
        if tmp_target is not None:
            try:
                tmp_target.unlink(missing_ok=True)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Tinymist-Vorschau
# ---------------------------------------------------------------------------

_PREVIEW_PROC: subprocess.Popen[str] | None = None
_PREVIEW_LOG: Path | None = None


def stop_preview_process(process: subprocess.Popen[str] | None) -> None:
    """Beendet einen Tinymist-Prozess samt Prozessgruppe."""
    if process is None or process.poll() is not None:
        return

    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            process.terminate()
        except ProcessLookupError:
            pass

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                process.kill()
            except ProcessLookupError:
                pass


def cleanup_preview_at_exit() -> None:
    global _PREVIEW_PROC
    stop_preview_process(_PREVIEW_PROC)
    _PREVIEW_PROC = None


atexit.register(cleanup_preview_at_exit)


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def preview_http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=0.5) as response:
            return 200 <= response.status < 400
    except Exception:
        return False


def read_preview_log(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return strip_ansi(path.read_text(encoding="utf-8", errors="replace"))[-4000:]
    except OSError:
        return ""


def stop_preview() -> None:
    """Beendet die laufende Vorschau und räumt den Session-State auf."""
    global _PREVIEW_PROC
    process = st.session_state.pop("preview_proc", None)
    if process is None:
        process = _PREVIEW_PROC
    stop_preview_process(process)
    _PREVIEW_PROC = None
    st.session_state.pop("preview_url", None)
    st.session_state.pop("preview_filename", None)
    st.session_state.pop("preview_error", None)


def start_preview(root: Path, typ_filename: str) -> tuple[subprocess.Popen[str], str, Path]:
    """Startet ``tinymist preview`` und wartet, bis der Server erreichbar ist."""
    global _PREVIEW_PROC, _PREVIEW_LOG

    stop_preview()

    tinymist = shutil.which("tinymist")
    if not tinymist:
        raise PreviewError("tinymist wurde nicht im PATH gefunden.")

    if port_in_use(PREVIEW_HOST, PREVIEW_PORT):
        raise PreviewError(
            f"Port {PREVIEW_PORT} ist bereits belegt. Bitte einen alten "
            "Tinymist-Prozess beenden (z. B. pkill -f 'tinymist preview')."
        )

    log_path = Path(tempfile.gettempdir()) / (
        f"pruefung-tinymist-{os.getpid()}-{int(time.time())}.log"
    )

    try:
        log_handle = open(log_path, "w", encoding="utf-8")
    except OSError as exc:
        raise PreviewError(f"Logdatei konnte nicht erstellt werden: {exc}") from exc

    try:
        process = subprocess.Popen(
            [
                tinymist,
                "preview",
                str(root / typ_filename),
                "--no-open",
                "--root",
                str(root),
            ],
            cwd=str(root),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    except OSError as exc:
        raise PreviewError(f"tinymist konnte nicht gestartet werden: {exc}") from exc
    finally:
        log_handle.close()

    _PREVIEW_PROC = process
    _PREVIEW_LOG = log_path

    deadline = time.time() + 20
    while time.time() < deadline:
        if process.poll() is not None:
            output = read_preview_log(log_path)
            _PREVIEW_PROC = None
            raise PreviewError(
                f"tinymist wurde beendet (Exit-Code {process.returncode}).\n"
                f"{output}"
            )
        if preview_http_ok(PREVIEW_URL):
            return process, PREVIEW_URL, log_path
        time.sleep(0.25)

    stop_preview_process(process)
    _PREVIEW_PROC = None
    raise PreviewError(
        "Timeout: Die Tinymist-Vorschau war nach 20 Sekunden nicht erreichbar.\n"
        + read_preview_log(log_path)
    )


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------


def git_commit(root: Path, message: str, push: bool = False) -> GitResult:
    """Führt git add/commit (optional push) für auswahl.typ aus."""
    git = shutil.which("git")
    if not git:
        raise GitError("git wurde nicht im PATH gefunden.")

    check = run_command(
        [git, "rev-parse", "--is-inside-work-tree"], cwd=root, timeout=30
    )
    if check.returncode != 0:
        raise GitError(
            "Der Projektordner ist kein Git-Repository:\n"
            + strip_ansi(check.stderr).strip()
        )

    add = run_command([git, "add", "--", AUSWAHL_FILENAME], cwd=root, timeout=30)
    if add.returncode != 0:
        raise GitError(
            "git add ist fehlgeschlagen:\n" + strip_ansi(add.stderr).strip()
        )

    diff = run_command(
        [git, "diff", "--cached", "--quiet", "--", AUSWAHL_FILENAME],
        cwd=root,
        timeout=30,
    )
    if diff.returncode == 0:
        return GitResult(
            committed=False,
            commit_hash="",
            stdout=add.stdout,
            stderr=add.stderr,
        )
    if diff.returncode > 1:
        raise GitError(
            "git diff ist fehlgeschlagen:\n" + strip_ansi(diff.stderr).strip()
        )

    commit = run_command(
        [git, "commit", "-m", message, "--", AUSWAHL_FILENAME],
        cwd=root,
        timeout=60,
    )
    if commit.returncode != 0:
        raise GitError(
            "git commit ist fehlgeschlagen:\n" + strip_ansi(commit.stderr).strip()
        )

    hash_result = run_command(
        [git, "rev-parse", "--short", "HEAD"], cwd=root, timeout=30
    )
    commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else ""

    push_output = ""
    push_error = ""
    if push:
        push_result = run_command(
            [git, "push"], cwd=root, timeout=120, env=_git_network_env()
        )
        push_output = strip_ansi(push_result.stdout).strip()
        if push_result.returncode != 0:
            push_error = strip_ansi(push_result.stderr).strip()

    return GitResult(
        committed=True,
        commit_hash=commit_hash,
        stdout=commit.stdout,
        stderr=commit.stderr,
        push_output=push_output,
        push_error=push_error,
    )


def read_git_status(root: Path) -> dict[str, str] | None:
    """Liefert Branch, letzten Commit und Status von auswahl.typ."""
    git = shutil.which("git")
    if not git:
        return None

    try:
        check = run_command(
            [git, "rev-parse", "--is-inside-work-tree"], cwd=root, timeout=10
        )
        if check.returncode != 0:
            return None

        branch = run_command(
            [git, "branch", "--show-current"], cwd=root, timeout=10
        )
        log = run_command(
            [git, "log", "-1", "--format=%h %s"], cwd=root, timeout=10
        )
        status = run_command(
            [git, "status", "--short", "--", AUSWAHL_FILENAME], cwd=root, timeout=10
        )
    except (CommandError, OSError):
        return None

    return {
        "branch": branch.stdout.strip() if branch.returncode == 0 else "",
        "last_commit": log.stdout.strip() if log.returncode == 0 else "",
        "status": status.stdout.strip() if status.returncode == 0 else "",
    }


def _git_network_env() -> dict[str, str]:
    """Verhindert, dass Git bei fehlenden Credentials interaktiv blockiert."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    return env


def git_check_sync(root: Path) -> dict[str, str | int | bool] | None:
    """Prüft, ob der lokale Branch mit dem Remote synchron ist."""
    git = shutil.which("git")
    if not git:
        return None
    try:
        check = run_command(
            [git, "rev-parse", "--is-inside-work-tree"], cwd=root, timeout=10
        )
        if check.returncode != 0:
            return None
        remote_url = run_command(
            [git, "remote", "get-url", "origin"], cwd=root, timeout=10
        )
        remote_url_str = remote_url.stdout.strip() if remote_url.returncode == 0 else ""
        if not remote_url_str:
            return None

        branch_res = run_command(
            [git, "branch", "--show-current"], cwd=root, timeout=10
        )
        branch_name = branch_res.stdout.strip() if branch_res.returncode == 0 else ""

        file_status = run_command(
            [git, "status", "--porcelain", "--", AUSWAHL_FILENAME],
            cwd=root,
            timeout=10,
        )
        file_dirty = bool(file_status.stdout.strip())

        fetch_result = run_command(
            [git, "fetch", "--prune", "origin"],
            cwd=root,
            timeout=20,
            env=_git_network_env(),
        )

        ahead_n = 0
        behind_n = 0
        upstream_ok = False
        if branch_name:
            upstream = f"origin/{branch_name}"
            ahead_res = run_command(
                [git, "rev-list", "--count", f"{upstream}..HEAD"],
                cwd=root,
                timeout=10,
            )
            behind_res = run_command(
                [git, "rev-list", "--count", f"HEAD..{upstream}"],
                cwd=root,
                timeout=10,
            )
            upstream_ok = ahead_res.returncode == 0 and behind_res.returncode == 0
            if upstream_ok:
                ahead_n = int(ahead_res.stdout.strip() or 0)
                behind_n = int(behind_res.stdout.strip() or 0)
    except (CommandError, OSError, ValueError):
        return None

    return {
        "remote_url": remote_url_str,
        "branch": branch_name,
        "ahead": ahead_n,
        "behind": behind_n,
        "upstream_ok": upstream_ok,
        "file_dirty": file_dirty,
        "fetch_ok": fetch_result.returncode == 0,
        "fetch_stderr": (
            strip_ansi(fetch_result.stderr).strip()[:500]
            if fetch_result.returncode != 0
            else ""
        ),
    }


@st.cache_data(ttl=60, show_spinner="Git-Status wird mit origin abgeglichen …")
def cached_git_sync(root: str) -> dict[str, str | int | bool] | None:
    """Cached den Remote-Abgleich, damit nicht jeder Klick einen Fetch auslöst."""
    return git_check_sync(Path(root))


def git_pull_fast_forward(root: Path) -> dict[str, str | bool]:
    """Versucht einen Fast-Forward-Pull, nur wenn sicher."""
    git = shutil.which("git")
    if not git:
        return {"ok": False, "msg": "git nicht gefunden"}
    try:
        branch_res = run_command(
            [git, "branch", "--show-current"], cwd=root, timeout=10
        )
        branch_name = branch_res.stdout.strip() if branch_res.returncode == 0 else ""
        if not branch_name:
            return {"ok": False, "msg": "Kein lokaler Branch aktiv."}

        # Ungespeicherte Änderungen an auswahl.typ würden beim Pull verloren gehen.
        file_status = run_command(
            [git, "status", "--porcelain", "--", AUSWAHL_FILENAME],
            cwd=root,
            timeout=10,
        )
        if file_status.stdout.strip():
            return {
                "ok": False,
                "msg": (
                    "`auswahl.typ` hat lokale, nicht committete Änderungen. "
                    "Bitte zuerst speichern und committen oder die Änderungen "
                    "verwerfen; danach ist der Pull möglich."
                ),
            }

        upstream = f"origin/{branch_name}"
        ahead_res = run_command(
            [git, "rev-list", "--count", f"{upstream}..HEAD"],
            cwd=root,
            timeout=10,
        )
        behind_res = run_command(
            [git, "rev-list", "--count", f"HEAD..{upstream}"],
            cwd=root,
            timeout=10,
        )
        if ahead_res.returncode != 0 or behind_res.returncode != 0:
            return {
                "ok": False,
                "msg": f"Upstream `{upstream}` nicht gefunden. Bitte Remote-Branch prüfen.",
            }
        ahead_n = int(ahead_res.stdout.strip() or 0)
        behind_n = int(behind_res.stdout.strip() or 0)
        if ahead_n > 0:
            return {
                "ok": False,
                "msg": (
                    f"Lokale Commits vorhanden ({ahead_n} ahead) – "
                    "Pull nicht sicher. Bitte zuerst pushen oder manuell mergen."
                ),
            }
        if behind_n <= 0:
            return {"ok": False, "msg": "Nichts zu holen (kein Behind)."}

        # Fast-Forward ist nur möglich, wenn HEAD Vorfahre von origin/<branch> ist.
        ancestor = run_command(
            [git, "merge-base", "--is-ancestor", "HEAD", upstream],
            cwd=root,
            timeout=10,
        )
        if ancestor.returncode != 0:
            return {
                "ok": False,
                "msg": "Kein Fast-Forward möglich – die History ist divergiert.",
            }

        pull = run_command(
            [git, "pull", "--ff-only", "origin", branch_name],
            cwd=root,
            timeout=60,
            env=_git_network_env(),
        )
        if pull.returncode == 0:
            return {
                "ok": True,
                "msg": (
                    f"Pull erfolgreich (Fast-Forward, {behind_n} Commit(s)). "
                    f"{strip_ansi(pull.stdout).strip()[:200]}"
                ),
            }
        return {
            "ok": False,
            "msg": f"Pull fehlgeschlagen: {strip_ansi(pull.stderr).strip()[:300]}",
        }
    except (CommandError, OSError, ValueError) as exc:
        return {"ok": False, "msg": str(exc)}


# ---------------------------------------------------------------------------
# Streamlit-Hilfsfunktionen
# ---------------------------------------------------------------------------


def task_key(task_id: str) -> str:
    return f"task::{task_id}"


def selected_task_ids(parsed: SelectionFile) -> set[str]:
    return {
        task.task_id
        for task in parsed.tasks
        if bool(st.session_state.get(task_key(task.task_id), task.active))
    }


def active_task_ids(parsed: SelectionFile) -> set[str]:
    return {task.task_id for task in parsed.tasks if task.active}


def show_flash() -> None:
    flash = st.session_state.pop("flash", None)
    if not flash:
        return
    level, message = flash
    if level == "success":
        st.success(message)
    elif level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.info(message)


def streamlit_pdf_available() -> bool:
    """Prüft, ob die optionale streamlit-pdf-Komponente installiert ist."""
    try:
        import streamlit_pdf  # noqa: F401
    except ImportError:
        return False
    return True


def load_project(root_input: str) -> SelectionFile:
    """Lädt ein Projekt und setzt alle Session-State-Widgetwerte zurück."""
    if not root_input.strip():
        raise ParseError("Bitte einen Projektordner angeben.")

    root = Path(root_input).expanduser()
    if not root.is_absolute():
        root = root.resolve()
    if not root.is_dir():
        raise ParseError(f"Projektordner nicht gefunden: {root}")

    parsed = parse_selection_file(root / AUSWAHL_FILENAME)

    # Eine eventuell laufende Vorschau gehört zum alten Projekt.
    try:
        stop_preview()
    except Exception:
        pass

    for key in list(st.session_state.keys()):
        if key.startswith("task::"):
            del st.session_state[key]

    st.session_state.pop("task_filter", None)

    for task in parsed.tasks:
        st.session_state[task_key(task.task_id)] = task.active

    st.session_state["parsed"] = parsed
    st.session_state["loaded_root"] = str(root)
    st.session_state["header_art"] = parsed.art
    st.session_state["header_klasse"] = parsed.klasse
    st.session_state["header_datum"] = parsed.datum
    st.session_state["load_error"] = None
    st.session_state.pop("pdf_results", None)
    st.session_state.pop("git_result", None)
    st.session_state.pop("git_error", None)
    st.session_state.pop("preview_error", None)
    return parsed


def ensure_initial_load() -> None:
    if "parsed" in st.session_state:
        return
    if "root_input" not in st.session_state:
        st.session_state["root_input"] = str(DEFAULT_ROOT)
    try:
        load_project(st.session_state["root_input"])
    except Exception as exc:
        st.session_state["load_error"] = str(exc)


def render_sidebar() -> None:
    with st.sidebar.expander("Server beenden"):
        st.caption(
            "Beendet den Streamlit-Server. Der Tab kann danach geschlossen "
            "werden."
        )
        if st.button(
            "Server jetzt beenden",
            key="shutdown_server",
            width="stretch",
        ):
            st.session_state["shutdown_requested"] = True
            st.rerun()

    st.sidebar.divider()
    st.sidebar.header("Projekt")

    saved = load_saved_root()
    if saved is not None and "root_input" in st.session_state:
        current_val = st.session_state["root_input"].strip()
        if current_val == str(DEFAULT_ROOT) or current_val == "":
            st.session_state["root_input"] = saved

    st.sidebar.text_input(
        "Projektordner",
        key="root_input",
        help=(
            "Ordner mit auswahl.typ, pruefung.typ und loesungen.typ. "
            "Der Pfad darf ~ enthalten."
        ),
    )

    root_save_col, root_info_col = st.sidebar.columns([2, 3])
    with root_save_col:
        save_checked = st.checkbox(
            "Als Standard speichern",
            key=SAVE_ROOT_KEY,
            value=bool(saved) and (st.session_state.get("root_input", "").strip() == (saved or "")),
            help="Speichert den aktuellen Projektpfad als Standard (auch für .desktop / fish-Alias).",
        )
    with root_info_col:
        if saved:
            st.caption(f"Gespeichert: `{local_basename(saved)}`")
        else:
            st.caption("Kein Standardpfad gespeichert.")

    if save_checked:
        saved_path = st.session_state.get("root_input", "").strip()
        if saved_path and save_saved_root(saved_path):
            st.session_state["flash"] = ("success", f"Standardpfad gespeichert: `{local_basename(saved_path)}`")
        elif not saved_path:
            save_saved_root(None)
            st.session_state["flash"] = ("info", "Standardpfad gelöscht.")

    if st.sidebar.button("Projekt neu einlesen", type="primary"):
        try:
            load_project(st.session_state["root_input"])
            st.session_state["flash"] = (
                "success",
                f"Projekt neu eingelesen: {st.session_state['loaded_root']}",
            )
            st.rerun()
        except Exception as exc:
            st.session_state["load_error"] = str(exc)
    st.sidebar.caption(
        "Beim Neuladen werden ungespeicherte Änderungen verworfen."
    )

    if st.session_state.get("load_error"):
        st.sidebar.error(st.session_state["load_error"])

    parsed: SelectionFile | None = st.session_state.get("parsed")
    if parsed:
        st.sidebar.caption(f"Datei: `{parsed.path}`")
        active_count = sum(1 for task in parsed.tasks if task.active)
        st.sidebar.caption(
            f"{len(parsed.tasks)} Aufgaben · {active_count} in der Datei aktiv"
        )
        try:
            mtime = datetime.fromtimestamp(parsed.path.stat().st_mtime)
            st.sidebar.caption(f"Stand: {mtime:%d.%m.%Y %H:%M}")
        except OSError:
            st.sidebar.warning("Die Datei ist nicht mehr lesbar.")

        backup_path = parsed.path.with_name(parsed.path.name + BACKUP_SUFFIX)
        if backup_path.exists():
            try:
                backup_time = datetime.fromtimestamp(backup_path.stat().st_mtime)
                backup_label = f" (Stand {backup_time:%d.%m.%Y %H:%M})"
            except OSError:
                backup_label = ""
            st.sidebar.caption(
                f"Backup: `{backup_path.name}`{backup_label}"
            )

    st.sidebar.divider()
    st.sidebar.subheader("Werkzeuge")
    for tool in ("tinymist", "git"):
        path = shutil.which(tool)
        if path:
            st.sidebar.caption(f"✅ `{tool}`: {path}")
        else:
            st.sidebar.caption(f"❌ `{tool}` nicht gefunden")

    st.sidebar.caption(
        "Git-Status und Abgleich mit origin findest du im Bereich "
        "„Prüfungsdaten“."
    )


# ---------------------------------------------------------------------------
# Server beenden
# ---------------------------------------------------------------------------


def launcher_pid_file() -> Path:
    """Pfad zur PID-Datei, die der Startbefehl ``pruefung`` anlegt."""
    state_home = Path(
        os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")
    )
    state_dir = Path(
        os.environ.get("PRUEFUNG_STATE_DIR", state_home / "pruefung")
    )
    return state_dir / "streamlit.pid"


def _remove_launcher_pid_file() -> None:
    """Entfernt die PID-Datei, sofern sie zu diesem Serverprozess gehört."""
    pid_file = launcher_pid_file()
    try:
        if pid_file.read_text(encoding="utf-8").strip() == str(os.getpid()):
            pid_file.unlink()
    except OSError:
        pass


def _terminate_server() -> None:
    """Beendet den Streamlit-Prozess nach dem Abschiedshinweis."""
    _remove_launcher_pid_file()
    try:
        os.kill(os.getpid(), signal.SIGTERM)
    except OSError:
        os._exit(0)


def render_shutdown_screen() -> None:
    """Zeigt den Abschiedshinweis und beendet den Server kurz danach."""
    st.markdown(
        '<style>[data-testid="stAppDeployButton"] { display: none; }</style>',
        unsafe_allow_html=True,
    )
    if not st.session_state.get("shutdown_scheduled"):
        st.session_state["shutdown_scheduled"] = True
        timer = threading.Timer(3.0, _terminate_server)
        timer.daemon = True
        timer.start()

    st.markdown("## Server wird beendet")
    st.success(
        "Der Streamlit-Server wird in wenigen Sekunden beendet. Du kannst "
        "diesen Tab bzw. dieses Fenster danach schliessen."
    )
    st.caption(
        "Neu starten: `pruefung` im Terminal oder über die "
        "Desktop-Verknüpfung."
    )
    st.stop()


# ---------------------------------------------------------------------------
# UI-Bausteine
# ---------------------------------------------------------------------------

RECENCY_EMOJI = {
    "red": "🔴",
    "orange": "🟠",
    "yellow": "🟡",
    "green": "🟢",
}


def clear_selection(parsed: SelectionFile) -> None:
    """Button-Callback: setzt alle Aufgaben-Checkboxen vor dem Rerun zurück."""
    for task in parsed.tasks:
        st.session_state[task_key(task.task_id)] = False


def _section_changed() -> None:
    """Merkt sich, dass nach dem Bereichswechsel nach oben gescrollt werden soll."""
    st.session_state["scroll_to_top"] = True


def render_sticky_header(selected_count: int, dirty: bool) -> str:
    """Zeigt Auswahlzähler und Bereichsnavigation dauerhaft am oberen Rand."""
    st.markdown(STICKY_HEADER_CSS, unsafe_allow_html=True)

    if st.session_state.get("active_section") not in SECTIONS:
        st.session_state.pop("active_section", None)

    with st.container(key="sticky_header"):
        title_col, nav_col, count_col = st.columns(
            [2.4, 3.2, 1.3], vertical_alignment="center"
        )
        with title_col:
            marker = (
                ' <span title="Ungespeicherte Änderungen" '
                'style="color:#ed6c02">●</span>'
                if dirty
                else ""
            )
            st.markdown(
                f"#### {APP_ICON} {APP_TITLE}{marker}",
                unsafe_allow_html=True,
            )
        with nav_col:
            st.segmented_control(
                "Bereich",
                options=list(SECTIONS),
                default=SECTION_DATA,
                key="active_section",
                label_visibility="collapsed",
                on_change=_section_changed,
                width="stretch",
            )
        with count_col:
            text = f"{selected_count} / {MAX_AUFGABEN}"
            if selected_count > MAX_AUFGABEN:
                style = "background:#b3261e;color:#fff;border:1px solid #b3261e;"
            elif selected_count == MAX_AUFGABEN:
                style = "background:#1b5e20;color:#fff;border:1px solid #1b5e20;"
            elif selected_count == 0:
                style = (
                    "background:rgba(128,128,128,.12);color:inherit;"
                    "border:1px solid rgba(128,128,128,.45);"
                )
            else:
                style = (
                    "background:rgba(237,108,2,.15);color:#b45309;"
                    "border:1px solid #ed6c02;"
                )
            st.markdown(
                '<div style="'
                + style
                + "border-radius:999px;padding:.42rem .7rem;text-align:center;"
                "font-weight:650;white-space:nowrap;\">"
                + text
                + "</div>",
                unsafe_allow_html=True,
            )

    return st.session_state.get("active_section", SECTION_DATA)


def apply_section_visibility(section: str) -> None:
    """Blendet alle Bereiche ausser dem aktiven aus.

    Die Bereiche werden trotzdem vollständig gerendert, damit Streamlit die
    Widget-Zustände (Checkboxen, Textfelder) beim Bereichswechsel nicht
    verwirft.
    """
    css_class = SECTION_CLASS.get(section, SECTION_CLASS[SECTION_DATA])
    st.markdown(
        f"<style>.st-key-{css_class} {{ display: block; }}</style>",
        unsafe_allow_html=True,
    )


def run_javascript(script: str, *, key: str) -> None:
    """Führt JavaScript in einem unsichtbaren Same-Origin-iframe aus."""
    try:
        with st.container(key=key):
            st.iframe(f"<script>{script}</script>", height=1, tab_index=-1)
    except Exception:
        pass


def collapse_sidebar_on_start() -> None:
    """Klappt die Seitenleiste beim ersten Laden eines Tabs zu.

    ``initial_sidebar_state="collapsed"`` greift nicht, wenn der Browser
    bereits einen gespeicherten Zustand (localStorage) hat. Das Skript
    klickt daher einmal pro Sitzung den Collapse-Knopf; spätere Reruns
    lassen eine vom Benutzer geöffnete Seitenleiste unangetastet.
    """
    if st.session_state.get("sidebar_collapsed_on_start"):
        return
    st.session_state["sidebar_collapsed_on_start"] = True
    run_javascript(
        """
        (function () {
            const doc = window.parent.document;
            let tries = 0;
            const timer = setInterval(function () {
                const sidebar = doc.querySelector('[data-testid="stSidebar"]');
                const button =
                    doc.querySelector('button[aria-label="Collapse sidebar"]') ||
                    doc.querySelector(
                        '[data-testid="stSidebar"] [data-testid="stBaseButton-headerNoPadding"]'
                    );
                if (sidebar && button) {
                    clearInterval(timer);
                    if (sidebar.getBoundingClientRect().width > 0) {
                        button.click();
                    }
                } else if (++tries > 40) {
                    clearInterval(timer);
                }
            }, 50);
        })();
        """,
        key="sidebar_collapse_helper",
    )


def scroll_to_top_if_requested() -> None:
    """Scrollt nach einem Bereichswechsel nach oben."""
    if not st.session_state.pop("scroll_to_top", False):
        return
    run_javascript(
        """
        (function () {
            const doc = window.parent.document;
            const main = doc.querySelector('[data-testid="stMain"]');
            if (main) main.scrollTo({top: 0, behavior: 'instant'});
            window.parent.scrollTo({top: 0, behavior: 'instant'});
        })();
        """,
        key="scroll_top_helper",
    )


def _remote_short_name(sync_info: dict[str, str | int | bool]) -> str:
    remote = str(sync_info.get("remote_url", "")).rstrip("/")
    name = remote.split("/")[-1].split(":")[-1]
    return name.removesuffix(".git") or remote


def render_git_banner(
    parsed: SelectionFile,
    sync_info: dict[str, str | int | bool] | None,
    dirty: bool,
) -> None:
    """Zeigt den Remote-Status prominent oberhalb der Bereiche an."""
    pull_error = st.session_state.pop("git_pull_error", None)
    if pull_error:
        st.error(f"Pull fehlgeschlagen: {pull_error}")

    if sync_info is None:
        return

    fetch_ok = bool(sync_info.get("fetch_ok", False))
    branch = str(sync_info.get("branch", ""))
    ahead = int(sync_info.get("ahead", 0) or 0)
    behind = int(sync_info.get("behind", 0) or 0)
    upstream_ok = bool(sync_info.get("upstream_ok", False))
    file_dirty = bool(sync_info.get("file_dirty", False))

    if not fetch_ok:
        with st.container(border=True, key="git_fetch_banner"):
            text_col, button_col = st.columns(
                [5, 1.4], vertical_alignment="center"
            )
            with text_col:
                st.warning(
                    "Der Abgleich mit `origin` ist fehlgeschlagen. Der "
                    "angezeigte Git-Status ist möglicherweise veraltet."
                )
                detail = str(sync_info.get("fetch_stderr", "")).strip()
                if detail:
                    with st.expander("Details zum Fetch-Fehler"):
                        st.code(detail, language="text")
            with button_col:
                if st.button(
                    "Erneut prüfen",
                    key="retry_git_fetch",
                    width="stretch",
                ):
                    cached_git_sync.clear()
                    st.rerun()
        return

    if not upstream_ok:
        if branch:
            st.info(
                f"Für `{branch}` wurde kein Upstream `origin/{branch}` "
                "gefunden. Ein automatischer Abgleich ist nicht möglich."
            )
        return

    if behind <= 0:
        if ahead > 0:
            st.info(
                f"Lokale Commits sind noch nicht gepusht: {ahead} Commit(s) "
                f"vor `origin/{branch}`."
            )
        return

    diverged = ahead > 0
    pull_disabled = diverged or dirty or file_dirty

    with st.container(border=True, key="git_behind_banner"):
        text_col, button_col = st.columns([5, 1.4], vertical_alignment="center")
        with text_col:
            if diverged:
                st.error(
                    f"Lokaler Branch und `origin/{branch}` sind divergiert: "
                    f"{ahead} lokale und {behind} Remote-Commits. "
                    "Bitte manuell mergen."
                )
            else:
                st.warning(
                    f"Die lokale Kopie ist **{behind} Commit(s) hinter "
                    f"`origin/{branch}`**. Die lokale `auswahl.typ` ist "
                    "möglicherweise veraltet."
                )

            if dirty:
                st.caption(
                    "Es gibt ungespeicherte Änderungen in der App. Ein Pull "
                    "würde sie verwerfen; bitte zuerst speichern oder die "
                    "Seite neu laden."
                )
            elif file_dirty:
                st.caption(
                    "`auswahl.typ` hat lokale, nicht committete Änderungen. "
                    "Bitte zuerst committen; danach ist der Pull möglich."
                )
            elif not diverged:
                st.caption(
                    "Fast-Forward-Pull möglich. Dabei wird die lokale "
                    "`auswahl.typ` durch den Stand von origin ersetzt."
                )

        with button_col:
            if st.button(
                "Jetzt von GitHub holen",
                type="primary",
                key="pull_from_banner",
                disabled=pull_disabled,
                width="stretch",
            ):
                with st.spinner("Fast-Forward-Pull läuft …"):
                    result = git_pull_fast_forward(parsed.path.parent)
                cached_git_sync.clear()
                if result.get("ok"):
                    try:
                        load_project(str(parsed.path.parent))
                    except Exception as exc:
                        st.session_state["git_pull_error"] = (
                            "Pull war erfolgreich, aber die Datei konnte "
                            f"nicht neu geladen werden: {exc}"
                        )
                    else:
                        st.session_state["flash"] = (
                            "success",
                            str(result.get("msg", "Pull erfolgreich.")),
                        )
                        st.session_state["scroll_to_top"] = True
                else:
                    st.session_state["git_pull_error"] = str(
                        result.get("msg", "Pull fehlgeschlagen.")
                    )
                st.rerun()


def render_git_status_panel(
    parsed: SelectionFile,
    git_info: dict[str, str] | None,
    sync_info: dict[str, str | int | bool] | None,
) -> None:
    """Detaillierter Git-Status im Bereich Prüfungsdaten."""
    st.subheader("Git-Status")
    with st.container(border=True):
        st.caption(f"Datei: `{parsed.path}`")
        if git_info is None:
            st.info(
                "Kein Git-Repository oder Git nicht verfügbar. Die App "
                "funktioniert weiterhin; Commit und Remote-Abgleich entfallen."
            )
            return

        branch_col, commit_col, file_col = st.columns(3)
        with branch_col:
            st.markdown("**Branch**")
            st.code(git_info["branch"] or "—", language="text")
        with commit_col:
            st.markdown("**Letzter Commit**")
            st.code(git_info["last_commit"] or "—", language="text")
        with file_col:
            st.markdown("**auswahl.typ**")
            if git_info["status"]:
                st.warning("Lokal geändert")
            else:
                st.success("Unverändert")

        if git_info["status"]:
            st.code(git_info["status"], language="text")

        if sync_info is None:
            st.caption("Kein `origin`-Remote konfiguriert.")
        else:
            st.markdown(f"**Remote:** `{_remote_short_name(sync_info)}`")
            if not sync_info.get("fetch_ok", False):
                st.warning(
                    "Der letzte Fetch ist fehlgeschlagen. Der Status kann "
                    "veraltet sein."
                )
            elif not sync_info.get("upstream_ok", False):
                st.caption(
                    "Für den aktuellen Branch existiert kein Upstream "
                    "`origin/<branch>`."
                )
            else:
                ahead = int(sync_info.get("ahead", 0) or 0)
                behind = int(sync_info.get("behind", 0) or 0)
                if behind > 0 and ahead == 0:
                    st.warning(
                        f"{behind} Commit(s) hinter origin – siehe "
                        "Aktualisierungsbanner oben."
                    )
                elif ahead > 0 and behind == 0:
                    st.info(
                        f"{ahead} lokale Commit(s) sind noch nicht gepusht."
                    )
                elif ahead > 0 and behind > 0:
                    st.error(
                        f"Branch divergiert: {ahead} lokal, {behind} remote."
                    )
                else:
                    st.success("Synchron mit origin.")

        if st.button(
            "Git-Status aktualisieren",
            key="refresh_git_status",
            help="Führt erneut `git fetch --prune origin` aus.",
        ):
            cached_git_sync.clear()
            st.rerun()


def render_exam_data_section(
    parsed: SelectionFile,
    info: ExamInfo | None,
    errors: list[str],
    git_info: dict[str, str] | None,
    sync_info: dict[str, str | int | bool] | None,
) -> None:
    """Bereich 1: Prüfungsdaten und Git-Status."""
    st.subheader("Prüfungsdaten")
    with st.container(border=True):
        st.caption(
            "Diese Werte werden in den Kopf von `auswahl.typ` geschrieben."
        )
        col_art, col_klasse, col_datum = st.columns([1.2, 1, 1])
        with col_art:
            st.text_input(
                "Prüfungsart",
                key="header_art",
                placeholder="Prüfung / Nachprüfung",
            )
        with col_klasse:
            st.text_input("Klasse", key="header_klasse", placeholder="z. B. M5c")
        with col_datum:
            st.text_input(
                "Prüfungsdatum",
                key="header_datum",
                placeholder="TT.MM.JJJJ",
            )

        if errors:
            for error in errors:
                st.warning(error)
        elif info is not None:
            st.caption(
                f"Semester: **{info.semester}** · "
                f"Historieneintrag: `{info.history_entry}`"
            )
            if is_nachpruefung(info.art):
                st.caption(
                    "Nachprüfung: In der Historie wird der Eintrag mit „NP“ "
                    "gekennzeichnet; Klammern in der Klassenbezeichnung "
                    "entfallen."
                )

    render_git_status_panel(parsed, git_info, sync_info)


def ensure_header_keys(parsed: SelectionFile) -> None:
    if "header_art" not in st.session_state:
        st.session_state["header_art"] = parsed.art
    if "header_klasse" not in st.session_state:
        st.session_state["header_klasse"] = parsed.klasse
    if "header_datum" not in st.session_state:
        st.session_state["header_datum"] = parsed.datum


def ensure_saved_for_action(
    parsed: SelectionFile, info: ExamInfo, selected_ids: set[str]
) -> SelectionFile:
    """Speichert vor Vorschau/PDF/Git automatisch, falls nötig."""
    try:
        result = save_selection(parsed, info, selected_ids)
    except Exception as exc:
        st.session_state["flash"] = (
            "error",
            f"Speichern vor der Aktion fehlgeschlagen: {exc}",
        )
        st.rerun()
        return parsed

    if result.changed:
        st.session_state["parsed"] = result.parsed
        st.session_state["flash"] = (
            "info",
            "Die Auswahl wurde vor der Aktion automatisch gespeichert.",
        )
        cached_git_sync.clear()
    return result.parsed


def handle_save(parsed: SelectionFile, info: ExamInfo, selected_ids: set[str]) -> None:
    try:
        result = save_selection(parsed, info, selected_ids)
    except Exception as exc:
        st.session_state["flash"] = ("error", f"Speichern fehlgeschlagen: {exc}")
        st.rerun()
        return

    if result.changed:
        st.session_state["parsed"] = result.parsed
        backup_name = result.backup_path.name if result.backup_path else "–"
        st.session_state["flash"] = (
            "success",
            f"Auswahl gespeichert. Backup: `{backup_name}`.",
        )
        cached_git_sync.clear()
    else:
        st.session_state["flash"] = (
            "info",
            "Keine Änderungen – die Datei ist bereits aktuell.",
        )
    st.rerun()


def handle_preview(
    parsed: SelectionFile, info: ExamInfo, selected_ids: set[str], target: str
) -> None:
    new_parsed = ensure_saved_for_action(parsed, info, selected_ids)
    typ_filename = (
        PRUEFUNG_FILENAME if target == "Prüfung" else LOESUNGEN_FILENAME
    )

    try:
        process, url, _log_path = start_preview(new_parsed.path.parent, typ_filename)
    except Exception as exc:
        st.session_state["preview_error"] = str(exc)
        st.session_state.pop("preview_url", None)
        st.session_state.pop("preview_proc", None)
        st.rerun()
        return

    st.session_state["preview_proc"] = process
    st.session_state["preview_url"] = url
    st.session_state["preview_filename"] = typ_filename
    st.session_state["preview_error"] = None
    st.rerun()


def handle_pdf(parsed: SelectionFile, info: ExamInfo, selected_ids: set[str]) -> None:
    new_parsed = ensure_saved_for_action(parsed, info, selected_ids)
    with st.spinner("Prüfung und Musterlösung werden als PDF erzeugt …"):
        results = [
            compile_pdf(new_parsed.path.parent, PRUEFUNG_FILENAME),
            compile_pdf(new_parsed.path.parent, LOESUNGEN_FILENAME),
        ]
    st.session_state["pdf_results"] = results
    st.rerun()


def handle_git(
    parsed: SelectionFile, info: ExamInfo, selected_ids: set[str], push: bool
) -> None:
    new_parsed = ensure_saved_for_action(parsed, info, selected_ids)
    message = f"{info.art} {info.klasse} {info.datum}"

    try:
        result = git_commit(new_parsed.path.parent, message, push=push)
    except Exception as exc:
        st.session_state["git_error"] = str(exc)
        st.session_state["git_result"] = None
        st.rerun()
        return

    st.session_state["git_result"] = result
    st.session_state["git_error"] = None
    cached_git_sync.clear()
    st.rerun()


def render_action_results() -> None:
    # Kleiner Abstand, damit Ergebnisfelder nicht direkt an den Buttons kleben.
    st.space("small")

    preview_error = st.session_state.get("preview_error")
    if preview_error:
        with st.expander("Fehler der Tinymist-Vorschau", expanded=True):
            st.error(preview_error)

    preview_url = st.session_state.get("preview_url")
    preview_process = st.session_state.get("preview_proc")
    if preview_url:
        if preview_process is not None and preview_process.poll() is not None:
            st.warning("Die Tinymist-Vorschau wurde beendet.")
            st.session_state.pop("preview_url", None)
            st.session_state.pop("preview_proc", None)
        else:
            filename = st.session_state.get("preview_filename", "")
            with st.expander(f"Tinymist-Vorschau: {filename}", expanded=True):
                left, right = st.columns([3, 1])
                with left:
                    st.link_button(
                        "Vorschau im neuen Tab öffnen",
                        preview_url,
                        type="primary",
                    )
                with right:
                    if st.button("Vorschau stoppen", key="stop_preview_button"):
                        stop_preview()
                        st.rerun()

                if hasattr(st, "iframe"):
                    st.iframe(preview_url, height=900)
                else:
                    from streamlit.components.v1 import iframe

                    iframe(preview_url, height=900, scrolling=True)
                st.caption(
                    "Falls die eingebettete Vorschau nicht lädt, den Link "
                    "oben verwenden."
                )

    pdf_results: list[PdfResult] | None = st.session_state.get("pdf_results")
    if pdf_results:
        with st.expander("PDF-Ergebnisse", expanded=True):
            for result in pdf_results:
                if result.error:
                    st.error(f"{result.label}: {result.error}")
                    output = "\n".join(
                        part
                        for part in (result.stdout, result.stderr)
                        if part.strip()
                    )
                    if output.strip():
                        st.code(strip_ansi(output), language="text")
                    continue

                if result.pdf_path is None:
                    st.error(f"{result.label}: Kein PDF-Pfad vorhanden.")
                    continue

                st.success(f"{result.label}: `{result.pdf_path}`")
                if result.stderr.strip():
                    st.caption(
                        "Tinymist-Hinweise: " + strip_ansi(result.stderr).strip()
                    )
                try:
                    data = result.pdf_path.read_bytes()
                except OSError as exc:
                    st.error(f"{result.label}: PDF nicht lesbar: {exc}")
                    continue

                st.download_button(
                    f"{result.label} als PDF herunterladen",
                    data=data,
                    file_name=result.pdf_path.name,
                    mime="application/pdf",
                    key=f"download_pdf_{result.filename}",
                )

                if streamlit_pdf_available():
                    try:
                        with st.expander(f"{result.label} anzeigen"):
                            st.pdf(data, height=800)
                    except Exception as exc:
                        st.warning(
                            f"Die eingebettete PDF-Anzeige ist nicht verfügbar: "
                            f"{exc}. Bitte den Download-Button verwenden."
                        )

    git_error = st.session_state.get("git_error")
    if git_error:
        with st.expander("Git-Fehler", expanded=True):
            st.error(git_error)

    git_result: GitResult | None = st.session_state.get("git_result")
    if git_result:
        with st.expander("Git-Ergebnis", expanded=True):
            if git_result.committed:
                st.success(f"Commit `{git_result.commit_hash}` erstellt.")
            else:
                st.info(
                    "Keine Änderungen an `auswahl.typ` – es wurde kein Commit "
                    "erstellt."
                )
            if git_result.stdout.strip():
                st.code(strip_ansi(git_result.stdout), language="text")
            if git_result.stderr.strip():
                st.code(strip_ansi(git_result.stderr), language="text")
            if git_result.push_output:
                st.success("Push erfolgreich.")
                st.code(git_result.push_output, language="text")
            if git_result.push_error:
                st.error("Der Commit war erfolgreich, aber der Push ist fehlgeschlagen.")
                st.code(git_result.push_error, language="text")


def render_tasks(parsed: SelectionFile, semester_for_colors: str) -> None:
    """Bereich 2: Aufgaben filtern, abwählen und auswählen."""
    st.subheader("Aufgaben")
    selected_count = len(selected_task_ids(parsed))

    filter_col, clear_col = st.columns([4, 1.2], vertical_alignment="bottom")
    with filter_col:
        filter_text = st.text_input(
            "Aufgaben filtern",
            key="task_filter",
            placeholder="Titel, Thema, Pfad oder Historie …",
        ).strip().casefold()
    with clear_col:
        st.button(
            "Alle abwählen",
            key="btn_clear_selection",
            on_click=clear_selection,
            args=(parsed,),
            disabled=selected_count == 0,
            width="stretch",
            help="Setzt alle Aufgaben-Checkboxen zurück.",
        )

    terms = filter_text.split()

    legend = (
        "🔴 = in diesem Semester gestellt  |  🟠 = letztes Semester  |  "
        "🟡 = vorletztes Semester  |  🟢 = sonst"
    )
    st.caption(legend)
    if semester_for_colors:
        st.caption(
            f"Die Ampel bezieht sich auf das eingegebene Prüfungsdatum "
            f"(Semester **{semester_for_colors}**)."
        )
    else:
        st.caption(
            "Die Ampel bezieht sich auf das Prüfungsdatum. Bitte ein gültiges "
            "Datum eingeben, damit die Semesterzuordnung stimmt."
        )

    if selected_count > MAX_AUFGABEN:
        st.error(
            f"Es sind {selected_count} Aufgaben ausgewählt. Erlaubt sind "
            f"höchstens {MAX_AUFGABEN}. Bitte Aufgaben abwählen."
        )

    def matches(task: Task) -> bool:
        if not terms:
            return True
        haystack = " ".join(
            [
                task.title,
                task.theme,
                task.subtopic,
                task.path,
                task.history,
            ]
        ).casefold()
        return all(term in haystack for term in terms)

    groups: OrderedDict[str, OrderedDict[str, list[Task]]] = OrderedDict()
    for task in parsed.tasks:
        groups.setdefault(task.theme, OrderedDict()).setdefault(
            task.subtopic, []
        ).append(task)

    shown = 0

    for theme, subtopics in groups.items():
        theme_tasks = [task for tasks in subtopics.values() for task in tasks]
        if not any(matches(task) for task in theme_tasks):
            continue

        selected_in_theme = sum(
            1
            for task in theme_tasks
            if bool(st.session_state.get(task_key(task.task_id), task.active))
        )
        # Beim Start ist alles zugeklappt. Nur Themen mit ausgewählten
        # Aufgaben (oder aktiver Suche) werden automatisch geöffnet.
        expanded = bool(terms) or selected_in_theme > 0

        with st.expander(
            f"{theme} · {selected_in_theme}/{len(theme_tasks)} ausgewählt",
            expanded=expanded,
        ):
            for subtopic, tasks in subtopics.items():
                filtered_tasks = [task for task in tasks if matches(task)]
                if not filtered_tasks:
                    continue
                if subtopic:
                    st.markdown(f"**{subtopic}**")

                for task in filtered_tasks:
                    key = task_key(task.task_id)
                    if key not in st.session_state:
                        st.session_state[key] = task.active

                    recency = compute_task_recency(
                        task.history, semester_for_colors
                    )
                    emoji = RECENCY_EMOJI.get(recency, "🟢")
                    label = f"{emoji} {task.title}"
                    if task.active:
                        label += "  ·  in Datei aktiv"

                    help_text = (
                        f"Pfad: `{task.path}`\n\n"
                        f"Historie: {task.history or '—'}\n\n"
                        f"Status in der Datei: "
                        f"{'aktiv' if task.active else 'inaktiv'}"
                    )
                    st.checkbox(label, key=key, help=help_text)
                    shown += 1

    if shown == 0:
        st.warning("Keine Aufgaben passen zum Filter.")


def render_actions_section(
    parsed: SelectionFile,
    info: ExamInfo | None,
    errors: list[str],
    selected_ids: set[str],
    selected_count: int,
    dirty: bool,
    semester_for_colors: str,
) -> None:
    """Bereich 3: Speichern, Vorschau, PDF und Git."""
    st.subheader("Aktionen")

    if errors:
        st.error("Bitte zuerst die Prüfungsdaten korrigieren.")
        if st.button("Zu den Prüfungsdaten", key="goto_data"):
            st.session_state["active_section"] = SECTION_DATA
            st.session_state["scroll_to_top"] = True
            st.rerun()

    selected_tasks = [
        task for task in parsed.tasks if task.task_id in selected_ids
    ]

    with st.container(border=True):
        st.markdown(
            f"**{selected_count} von {MAX_AUFGABEN} Aufgaben ausgewählt**"
        )
        if selected_count == 0:
            st.info(
                "Noch keine Aufgaben ausgewählt. Im Bereich „Aufgaben“ die "
                "gewünschten Aufgaben ankreuzen."
            )
            if st.button("Aufgaben auswählen", key="goto_tasks"):
                st.session_state["active_section"] = SECTION_TASKS
                st.session_state["scroll_to_top"] = True
                st.rerun()
        elif selected_count > MAX_AUFGABEN:
            st.error(
                f"{selected_count} Aufgaben sind zu viele. Bitte auf "
                f"höchstens {MAX_AUFGABEN} reduzieren."
            )
        else:
            for index, task in enumerate(selected_tasks, 1):
                recency = compute_task_recency(
                    task.history, semester_for_colors
                )
                emoji = RECENCY_EMOJI.get(recency, "🟢")
                st.write(f"{index}. {emoji} {task.title} — `{task.path}`")

    if dirty:
        st.caption(
            "Beim Start einer Aktion wird die aktuelle Auswahl automatisch "
            "gespeichert."
        )

    can_save = info is not None and selected_count <= MAX_AUFGABEN
    can_generate = can_save and selected_count > 0

    save_col, git_col = st.columns(2)
    with save_col:
        st.markdown("**Speichern**")
        st.caption(
            "Schreibt die Auswahl in `auswahl.typ`; vorher wird "
            "`auswahl.typ.bak` angelegt."
        )
        save_clicked = st.button(
            "Auswahl speichern",
            type="primary",
            key="action_save",
            disabled=not can_save,
            width="stretch",
        )
    with git_col:
        st.markdown("**Git**")
        st.caption(
            "Committet nur `auswahl.typ` mit der Prüfungsbezeichnung als "
            "Commit-Nachricht."
        )
        push_after = st.checkbox(
            "Nach dem Commit pushen",
            value=False,
            key="push_after_commit",
            help="Führt nach erfolgreichem Commit zusätzlich `git push` aus.",
        )
        git_clicked = st.button(
            "In Git committen",
            key="action_git",
            disabled=not can_save,
            width="stretch",
        )

    preview_col, pdf_col = st.columns(2)
    with preview_col:
        st.markdown("**Vorschau**")
        st.caption(
            "Startet tinymist für Prüfung oder Musterlösung. Die Vorschau "
            "kann im neuen Tab geöffnet werden."
        )
        preview_target = st.radio(
            "Vorschau für",
            ["Prüfung", "Musterlösung"],
            horizontal=True,
            key="preview_target",
        )
        preview_clicked = st.button(
            "Vorschau starten",
            key="action_preview",
            disabled=not can_generate,
            width="stretch",
        )
    with pdf_col:
        st.markdown("**PDF**")
        st.caption(
            "Erzeugt `pruefung.pdf` und `loesungen.pdf` mit Tinymist. "
            "Fehlermeldungen werden in der App angezeigt."
        )
        pdf_clicked = st.button(
            "PDFs erzeugen",
            key="action_pdf",
            disabled=not can_generate,
            width="stretch",
        )

    if save_clicked:
        assert info is not None
        handle_save(parsed, info, selected_ids)
    if preview_clicked:
        assert info is not None
        handle_preview(parsed, info, selected_ids, preview_target)
    if pdf_clicked:
        assert info is not None
        handle_pdf(parsed, info, selected_ids)
    if git_clicked:
        assert info is not None
        handle_git(parsed, info, selected_ids, push_after)

    if st.session_state.get("active_section") == SECTION_ACTIONS:
        render_action_results()


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    if st.session_state.get("shutdown_requested"):
        render_shutdown_screen()

    ensure_initial_load()
    render_sidebar()

    parsed: SelectionFile | None = st.session_state.get("parsed")
    if parsed is None:
        st.title(APP_TITLE)
        st.error(
            "Es konnte kein Projekt geladen werden. Bitte in der Seitenleiste "
            "einen gültigen Projektordner mit `auswahl.typ` angeben und auf "
            "„Projekt neu einlesen“ klicken."
        )
        st.stop()

    ensure_header_keys(parsed)
    collapse_sidebar_on_start()

    art = st.session_state.get("header_art", "")
    klasse = st.session_state.get("header_klasse", "")
    datum = st.session_state.get("header_datum", "")
    info, errors = validate_exam(art, klasse, datum)

    selected_ids = selected_task_ids(parsed)
    active_ids = active_task_ids(parsed)
    selected_count = len(selected_ids)

    dirty = (
        normalize_text_field(art) != parsed.art
        or normalize_text_field(klasse) != parsed.klasse
        or datum.strip() != parsed.datum
        or selected_ids != active_ids
    )

    # Die Ampel soll sich am aktuell eingegebenen Prüfungsdatum orientieren.
    semester_for_colors = info.semester if info else ""
    if not semester_for_colors and parsed.datum:
        try:
            semester_for_colors = semester_label(parse_exam_date(parsed.datum))
        except ValueError:
            semester_for_colors = ""

    active_section = render_sticky_header(selected_count, dirty)
    apply_section_visibility(active_section)
    show_flash()

    sync_info = cached_git_sync(str(parsed.path.parent))
    git_info = read_git_status(parsed.path.parent)
    render_git_banner(parsed, sync_info, dirty)

    with st.container(key=SECTION_CLASS[SECTION_DATA]):
        render_exam_data_section(parsed, info, errors, git_info, sync_info)

    with st.container(key=SECTION_CLASS[SECTION_TASKS]):
        render_tasks(parsed, semester_for_colors)

    with st.container(key=SECTION_CLASS[SECTION_ACTIONS]):
        render_actions_section(
            parsed,
            info,
            errors,
            selected_ids,
            selected_count,
            dirty,
            semester_for_colors,
        )

    scroll_to_top_if_requested()

    st.divider()
    st.caption(
        "Beim Speichern wird zuerst eine Sicherung als `auswahl.typ.bak` "
        "angelegt. Nicht ausgewählte Aufgaben werden auskommentiert; die "
        "Historie bereits aktiver, aber abgewählter Aufgaben bleibt erhalten."
    )


if __name__ == "__main__":
    main()
