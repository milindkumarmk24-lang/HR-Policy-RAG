"""PDF ingestion: load pages, strip running headers/footers, detect section
headings, and split into section-aware chunks that remember their page numbers.

Why section-aware? HR handbooks are organised into short numbered sections
("3.4 Sick Leave", "3.5 Public Holidays"). A plain fixed-size splitter happily
glues the end of one policy to the start of the next, and the retriever then
returns a chunk that is half about the wrong leave type. Splitting inside
section boundaries keeps each chunk about one policy, and the section title
doubles as a human-readable citation.
"""
from __future__ import annotations

import bisect
import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --------------------------------------------------------------------------- #
# Categories used to tag chunks (shown in citations and used by the router).
# Matched against the chapter + section title first, then the chunk body.
# --------------------------------------------------------------------------- #
CATEGORIES: dict[str, tuple[str, ...]] = {
    "Leave": ("leave", "holiday", "vacation", "time off", "absence", "maternity", "paternity",
              "sabbatical", "bereavement", "comp-off", "compensatory"),
    "Benefits": ("benefit", "insurance", "medical", "health", "provident", "gratuity", "wellness",
                 "allowance", "referral", "learning", "pension"),
    "Compensation": ("salary", "payroll", "pay ", "compensation", "bonus", "increment", "payslip",
                     "performance review", "appraisal", "advance"),
    "Conduct": ("conduct", "ethic", "harassment", "posh", "disciplin", "grievance", "whistle",
                "gift", "conflict of interest", "dress", "misconduct", "social media", "alcohol"),
    "Work arrangements": ("remote", "hybrid", "work from home", "working hours", "attendance",
                          "overtime", "shift", "flexible"),
    "Travel & expenses": ("travel", "expense", "per diem", "hotel", "reimburse", "conveyance"),
    "Separation": ("resign", "notice period", "separation", "exit", "termination", "full and final",
                   "relieving"),
    "IT & security": ("information security", "security", "password", "device", "acceptable use",
                      "laptop", "data protection"),
    "Employment": ("probation", "onboarding", "confirmation", "employment categor", "joining", "intern"),
}
CATEGORY_NAMES = list(CATEGORIES) + ["General"]

NUMBERED_HEADING = re.compile(
    r"^(?:(?i:chapter|section|part)\s+)?(?P<num>\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+(?P<title>[A-Z][^\n]{2,90})$"
)
# "II. Pregnancy and Childbirth" / "A. Sick Leave" (Roman-numeral chapters, lettered sections)
ROMAN_LETTER_HEADING = re.compile(r"^(?P<num>[IVX]{1,4}|[A-Z])[.)]\s+(?P<title>[A-Z][^\n]{2,90})$")
SMALL_WORDS = {"a", "an", "and", "the", "of", "for", "to", "in", "on", "or", "with", "at", "by", "from", "&"}


@dataclass
class Heading:
    pos: int          # character offset in the full document text
    level: int        # 1 = chapter, 2 = section, ...
    number: str | None
    title: str        # full heading text, e.g. "3.4 Sick Leave"


def file_sha(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def load_pages(path: Path) -> list[str]:
    """One string per PDF page, via LangChain's PyPDFLoader (pypdf under the hood)."""
    docs = PyPDFLoader(str(path), mode="page").load()
    return [d.page_content or "" for d in docs]


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #
def _norm_line(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def strip_running_lines(pages: list[str]) -> list[str]:
    """Remove headers/footers that repeat on most pages ("Company Handbook | Page 7").

    A line is "running" if, after replacing digits with '#', it appears in the
    first or last three lines of at least half of the pages (and at least 3).
    """
    if len(pages) < 3:
        return pages
    counts: Counter[str] = Counter()
    for page in pages:
        lines = [ln for ln in page.splitlines() if ln.strip()]
        edge = {_norm_line(ln) for ln in lines[:3] + lines[-3:]}
        counts.update(edge)
    threshold = max(3, len(pages) // 2)
    running = {ln for ln, c in counts.items() if c >= threshold and len(ln) < 120}
    cleaned = []
    for page in pages:
        lines = page.splitlines()
        cleaned.append("\n".join(ln for ln in lines if _norm_line(ln) not in running))
    return cleaned


def clean_text(text: str) -> str:
    text = text.replace(" ", " ").replace("’", "'").replace("‘", "'")
    # Bullets come out of many PDFs as '•', '' or a DEL control character.
    text = re.sub(r"^[ \t]*[\x7f•●▪‣]+[ \t]*", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"^.*(?:\.\s?){4,}\s*[\divxlc]+\s*$\n?", "", text, flags=re.MULTILINE | re.IGNORECASE)  # TOC dot leaders
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)         # re-join hyphenated line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return reflow(text.strip())


def _is_heading_line(line: str) -> bool:
    stripped = line.strip()
    m = NUMBERED_HEADING.match(stripped) or ROMAN_LETTER_HEADING.match(stripped)
    return bool(m and _looks_like_title(m.group("title")))


def reflow(text: str) -> str:
    """Join lines that a PDF wrapped mid-sentence ("A medical\\ncertificate").

    A line is joined to the next only when it ends without terminal punctuation
    and the next line starts in lower case (or with a number that isn't a
    heading). Headings, bullets and table cells, which start with a capital,
    a dash or a section number, keep their own lines.
    """
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        if out and out[-1] and line:
            prev = out[-1]
            joinable_end = re.search(r"[a-z0-9,;:(/&-]$", prev) is not None
            joinable_start = (re.match(r"[a-z(]", line) is not None
                              or (re.match(r"\d", line) is not None and not _is_heading_line(line)))
            if joinable_end and joinable_start and not _is_heading_line(prev):
                out[-1] = f"{prev} {line}"
                continue
        out.append(line)
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Heading detection
# --------------------------------------------------------------------------- #
def _looks_like_title(title: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'()\-/&]*", title)
    if not words or len(words) > 12 or title.rstrip().endswith((".", ",", ";", ":")):
        return False
    content = [w for w in words if w.lower() not in SMALL_WORDS]
    if not content:
        return False
    capitalised = sum(1 for w in content if w[0].isupper())
    return capitalised / len(content) >= 0.6


def detect_headings(text: str) -> list[Heading]:
    """Numbered ("3.4 Sick Leave"), Roman/lettered ("II. Pregnancy", "A. Sick
    Leave") and ALL-CAPS headings. Lettered sections under a Roman chapter are
    labelled "II.A Sick Leave" so they stay unique across chapters."""
    headings: list[Heading] = []
    pos = 0
    roman: str | None = None        # current Roman chapter number
    last_letter: str | None = None  # last lettered section seen in this chapter
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            m = NUMBERED_HEADING.match(stripped)
            r = None if m else ROMAN_LETTER_HEADING.match(stripped)
            if m and _looks_like_title(m.group("title")):
                num = m.group("num")
                headings.append(Heading(pos, num.count(".") + 1, num, stripped))
            elif r and _looks_like_title(r.group("title")):
                tok, title = r.group("num"), r.group("title").strip()
                # "I" after "H" (or "V" after "U") is a letter, not a numeral.
                follows_letter = len(tok) == 1 and last_letter is not None and ord(tok) == ord(last_letter) + 1
                if set(tok) <= set("IVX") and not follows_letter:
                    roman, last_letter = tok, None
                    headings.append(Heading(pos, 1, tok, f"{tok}. {title}"))
                else:
                    last_letter = tok
                    label = f"{roman}.{tok}" if roman else tok
                    headings.append(Heading(pos, 2, label, f"{label} {title}"))
            elif (stripped.isupper() and 4 <= len(stripped) <= 60 and len(re.findall(r"[A-Z]", stripped)) >= 4
                  and not re.search(r"\d{3,}", stripped)):
                headings.append(Heading(pos, 1, None, stripped.title()))
        pos += len(line) + 1
    return headings


def categorise(title: str, body: str = "") -> str:
    hay = f" {title.lower()} "
    for cat, words in CATEGORIES.items():
        if any(w in hay for w in words):
            return cat
    body_l = body.lower()
    scores = {cat: sum(body_l.count(w) for w in words) for cat, words in CATEGORIES.items()}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, score), (_, runner_up) = ranked[0], ranked[1]
    return best if score >= 3 and score >= 1.5 * runner_up else "General"


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #
def chunk_pdf(path: Path, doc_id: str, filename: str, chunk_size: int = 1000,
              chunk_overlap: int = 150) -> tuple[list[Document], int]:
    """Return (chunks, page_count). Each chunk's metadata carries page numbers
    (1-based, as printed by a PDF viewer), section, chapter and category."""
    raw_pages = load_pages(path)
    pages = [clean_text(p) for p in strip_running_lines(raw_pages)]

    # Concatenate pages, remembering where each one starts.
    offsets: list[int] = []
    parts: list[str] = []
    cursor = 0
    for p in pages:
        offsets.append(cursor)
        parts.append(p)
        cursor += len(p) + 2
    full = "\n\n".join(parts)

    def page_at(pos: int) -> int:
        return bisect.bisect_right(offsets, pos)  # 1-based page number

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
        add_start_index=True,
    )

    headings = detect_headings(full)
    spans: list[tuple[int, int, str | None, str | None]] = []  # (start, end, chapter, section)
    if len(headings) >= 3:
        if headings[0].pos > 0:
            spans.append((0, headings[0].pos, None, None))
        chapter: str | None = None
        for i, h in enumerate(headings):
            end = headings[i + 1].pos if i + 1 < len(headings) else len(full)
            if h.level == 1:
                chapter = h.title
                section = h.title
            else:
                section = h.title
            spans.append((h.pos, end, chapter, section))
    else:
        # No usable headings: fall back to page-by-page recursive splitting.
        for i, p in enumerate(pages):
            spans.append((offsets[i], offsets[i] + len(p), None, None))

    chunks: list[Document] = []
    for start, end, chapter, section in spans:
        body = full[start:end].strip()
        if not body or (section is not None and len(body) <= len(section) + 5):
            # A bare chapter title directly followed by its first section: skip,
            # the section chunks already carry the chapter name.
            continue
        lead = len(full[start:end]) - len(full[start:end].lstrip())
        for piece in splitter.create_documents([body]):
            text = piece.page_content.strip()
            if len(text) < 20:
                continue
            abs_start = start + lead + piece.metadata.get("start_index", 0)
            abs_end = abs_start + len(text)
            header_bits = [b for b in (chapter, section) if b]
            if len(header_bits) == 2 and header_bits[0] == header_bits[1]:
                header_bits = header_bits[:1]
            header = " > ".join(header_bits)
            idx = len(chunks)
            meta = {
                "chunk_id": f"{doc_id}:{idx:04d}",
                "doc_id": doc_id,
                "source": filename,
                "page": page_at(abs_start),
                "page_end": page_at(max(abs_start, abs_end - 1)),
                "chapter": chapter,
                "section": section,
                "category": categorise(" ".join(header_bits), text),
                "header": header,
                "chunk_index": idx,
            }
            # Contextual chunk header: the embedding sees which section a chunk
            # belongs to, even for the second or third chunk of a long section.
            content = f"[{header}]\n{text}" if header else text
            chunks.append(Document(page_content=content, metadata=meta))
    return chunks, len(pages)


def chunk_body(doc: Document) -> str:
    """The chunk text without its contextual header line (for display)."""
    header = doc.metadata.get("header")
    if header and doc.page_content.startswith(f"[{header}]\n"):
        return doc.page_content[len(header) + 3:]
    return doc.page_content
