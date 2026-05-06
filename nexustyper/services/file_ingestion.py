"""nexustyper.services.file_ingestion — pure file I/O helpers.

Public API
----------
load_text_from_path(path)      Read a file and return its plain-text content.
save_text_to_path(text, path)  Write UTF-8 plain text atomically.
supported_open_filter()        Qt-style filter string for QFileDialog.getOpenFileName.
supported_save_filter()        Qt-style filter string for QFileDialog.getSaveFileName.
FileIngestionError             Raised when a file cannot be read.

No Qt imports.  Format-specific third-party dependencies are imported lazily
inside each reader so missing libraries produce a clear FileIngestionError
rather than an ImportError at module load time.
"""

from __future__ import annotations

import os
import platform
import subprocess
import tempfile
from html.parser import HTMLParser
from typing import Optional


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class FileIngestionError(Exception):
    """Raised when a file cannot be opened or decoded into plain text."""


# ---------------------------------------------------------------------------
# Filter strings (single source of truth)
# ---------------------------------------------------------------------------

_OPEN_FILTER = (
    "All Supported (*.txt *.md *.markdown *.html *.htm *.rtf"
    " *.py *.js *.ts *.java *.c *.cpp *.h *.hpp *.cs *.go *.rs *.swift *.kt"
    " *.json *.yaml *.yml);;"
    "Text/Markdown/HTML/RTF (*.txt *.md *.markdown *.html *.htm *.rtf);;"
    "Code Files (*.py *.js *.ts *.java *.c *.cpp *.h *.hpp *.cs *.go *.rs *.swift *.kt);;"
    "All Files (*)"
)

_SAVE_FILTER = (
    "Text Files (*.txt);;"
    "Code Files (*.py *.js *.ts *.java *.c *.cpp *.h *.hpp *.cs *.go *.rs *.swift *.kt);;"
    "All Files (*)"
)


def supported_open_filter() -> str:
    """Return the Qt-style file-filter string for an open-file dialog."""
    return _OPEN_FILTER


def supported_save_filter() -> str:
    """Return the Qt-style file-filter string for a save-file dialog."""
    return _SAVE_FILTER


# ---------------------------------------------------------------------------
# Format readers (private)
# ---------------------------------------------------------------------------

class _HTMLStripper(HTMLParser):
    """Minimal stdlib HTML-to-plaintext converter."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._in_style = False
        self._in_script = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "style":
            self._in_style = True
        elif tag == "script":
            self._in_script = True
        elif tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "style":
            self._in_style = False
        elif tag == "script":
            self._in_script = False

    def handle_data(self, data: str) -> None:
        if not self._in_style and not self._in_script:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _read_html(path: str) -> str:
    """Read an HTML file and return stripped plain text using stdlib."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            raw = fh.read()
    except OSError as exc:
        raise FileIngestionError(f"Cannot open HTML file: {exc}") from exc

    # Prefer beautifulsoup4 when available for better accuracy.
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(raw, "html.parser")
        # Remove script/style elements
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n")
    except ImportError:
        pass

    # Fallback: stdlib HTMLParser
    stripper = _HTMLStripper()
    try:
        stripper.feed(raw)
    except Exception:
        pass
    return stripper.get_text()


def _read_rtf(path: str) -> Optional[str]:
    """Read an RTF file, returning plain text or None on failure.

    On macOS, delegates to the built-in *textutil* command.
    On other platforms, attempts the *striprtf* third-party library.
    Returns None if neither strategy is available (caller falls back to raw read).
    """
    if platform.system() == "Darwin":
        try:
            out = subprocess.check_output(
                ["textutil", "-convert", "txt", "-stdout", path],
                stderr=subprocess.DEVNULL,
            )
            return out.decode("utf-8", errors="ignore")
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None

    # Non-macOS: try striprtf
    try:
        from striprtf.striprtf import rtf_to_text  # type: ignore
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            rtf_src = fh.read()
        return rtf_to_text(rtf_src)
    except ImportError:
        # No striprtf — caller will read the file as raw text (best-effort)
        return None
    except Exception as exc:
        raise FileIngestionError(f"Cannot parse RTF file: {exc}") from exc


def _read_pdf(path: str) -> str:
    """Extract plain text from a PDF file.

    Tries *pdfplumber* first (better for tabular/complex PDFs), then falls
    back to *pypdf*.  Raises FileIngestionError if neither is installed or
    extraction fails.
    """
    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(path) as pdf:
            parts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    parts.append(page_text)
        return "\n".join(parts)
    except ImportError:
        pass  # try next option

    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(path)
        parts = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(parts)
    except ImportError:
        pass

    raise FileIngestionError(
        "Cannot read PDF: install 'pdfplumber' or 'pypdf' (pip install pdfplumber)."
    )


def _read_docx(path: str) -> str:
    """Extract plain text from a Word .docx file using *python-docx*.

    Raises FileIngestionError if the library is not installed.
    """
    try:
        import docx  # type: ignore
    except ImportError:
        raise FileIngestionError(
            "Cannot read .docx: install 'python-docx' (pip install python-docx)."
        )
    try:
        doc = docx.Document(path)
        return "\n".join(para.text for para in doc.paragraphs)
    except Exception as exc:
        raise FileIngestionError(f"Cannot parse .docx file: {exc}") from exc


def _read_csv(path: str) -> str:
    """Read a CSV file and return tab-aligned plain text."""
    import csv
    try:
        with open(path, newline="", encoding="utf-8", errors="ignore") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
        return "\n".join("\t".join(row) for row in rows)
    except Exception as exc:
        raise FileIngestionError(f"Cannot parse CSV file: {exc}") from exc


# ---------------------------------------------------------------------------
# Extension dispatcher
# ---------------------------------------------------------------------------

def load_text_from_path(path: str) -> str:
    """Open *path* and return its content as a plain-text string.

    Dispatches to the appropriate format reader based on file extension.
    Falls back to a UTF-8 text read for unknown extensions.

    Raises
    ------
    FileIngestionError
        When the file cannot be opened, decoded, or parsed.
    """
    if not os.path.exists(path):
        raise FileIngestionError(f"File not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    text: Optional[str] = None

    try:
        if ext in (".html", ".htm"):
            text = _read_html(path)

        elif ext == ".rtf":
            text = _read_rtf(path)
            # _read_rtf returns None when no RTF-capable tool is available;
            # fall through to the plain-text read below.

        elif ext == ".pdf":
            text = _read_pdf(path)

        elif ext == ".docx":
            text = _read_docx(path)

        elif ext == ".csv":
            text = _read_csv(path)

        # Plain-text fallback (also handles .txt, .md, all code extensions, etc.)
        if text is None:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            except OSError as exc:
                raise FileIngestionError(f"Cannot read file: {exc}") from exc

    except FileIngestionError:
        raise
    except Exception as exc:
        raise FileIngestionError(f"Unexpected error reading {path!r}: {exc}") from exc

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def save_text_to_path(text: str, path: str) -> None:
    """Write *text* as UTF-8 to *path*.

    Uses an atomic write (temp-file + rename on the same filesystem) so a
    crash mid-write does not leave the destination file truncated.

    Raises
    ------
    FileIngestionError
        When the file cannot be written.
    """
    dest_dir = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dest_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp_path, path)
        except Exception:
            # Clean up the temp file if rename failed
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except FileIngestionError:
        raise
    except OSError as exc:
        raise FileIngestionError(f"Cannot save file: {exc}") from exc
    except Exception as exc:
        raise FileIngestionError(f"Unexpected error saving {path!r}: {exc}") from exc
