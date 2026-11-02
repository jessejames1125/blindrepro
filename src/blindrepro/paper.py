"""Turn a paper reference into text the agent can read, with the answers taken out."""

from __future__ import annotations

import gzip
import hashlib
import html
import io
import json
import re
import subprocess
import tarfile
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .envs import ensure_env

ARXIV_ID = re.compile(r"(?:arxiv[:/]|arxiv\.org/(?:abs|pdf|e-print)/)?(\d{4}\.\d{4,5}(?:v\d+)?)(?:\.pdf)?$", re.I)
CODE_LINK = re.compile(
    r"(?:https?://|www\.)?(?:github\.com|gitlab\.[a-z.]+|bitbucket\.org|zenodo\.org|codeocean\.com"
    r"|huggingface\.co|osf\.io|figshare\.com)[^\s}\])>\"']*",
    re.I,
)
REMOVED = "[value removed]"
LINK_REMOVED = "[code link removed]"
USER_AGENT = "blindrepro (paper reproduction tool)"


@dataclass
class Paper:
    ref: str
    url: str
    title: str
    first_public: str
    license: str
    source_kind: str
    sha256: str

    def to_dict(self) -> dict:
        return asdict(self)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as reply:
        return reply.read()


def _strip_comments(tex: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", tex)


def _flatten(sources: dict[str, str]) -> str:
    """Inline \\input and \\include starting from the file with \\documentclass."""
    mains = [name for name, body in sources.items() if "\\documentclass" in _strip_comments(body)]
    if not mains:
        return "\n\n".join(_strip_comments(body) for body in sources.values())
    main = max(mains, key=lambda name: len(sources[name]))

    def expand(name: str, depth: int) -> str:
        body = _strip_comments(sources[name])
        if depth > 8:
            return body

        def replace(match: re.Match) -> str:
            target = match.group(1).strip()
            for candidate in (target, target + ".tex"):
                if candidate in sources:
                    return expand(candidate, depth + 1)
            return ""

        return re.sub(r"\\(?:input|include)\{([^}]+)\}", replace, body)

    return expand(main, 0)


def text_from_arxiv_source(blob: bytes) -> str:
    """Read LaTeX out of an arXiv source package in memory. Nothing is unpacked to disk."""
    sources: dict[str, str] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as package:
            for member in package.getmembers():
                if member.isfile() and member.name.endswith((".tex", ".bbl")):
                    extracted = package.extractfile(member)
                    if extracted:
                        name = member.name.removeprefix("./")
                        sources[name] = extracted.read().decode("utf-8", "replace")
    except tarfile.ReadError:
        try:
            return gzip.decompress(blob).decode("utf-8", "replace")
        except OSError:
            return ""
    bibliographies = {k: v for k, v in sources.items() if k.endswith(".bbl")}
    text = _flatten({k: v for k, v in sources.items() if k.endswith(".tex")})
    if bibliographies:
        text += "\n\n" + "\n".join(bibliographies.values())
    return text


def text_from_pdf(pdf: Path) -> str:
    """PDF text through pypdf in its own environment, so the core stays dependency free."""
    python = ensure_env(["pypdf"])
    code = (
        "import sys, json, pypdf\n"
        "r = pypdf.PdfReader(sys.argv[1])\n"
        "sys.stdout.buffer.write('\\n\\n'.join(p.extract_text() or '' for p in r.pages).encode('utf-8'))\n"
    )
    done = subprocess.run([str(python), "-I", "-c", code, str(pdf)], capture_output=True, check=True)
    return done.stdout.decode("utf-8", "replace")


def arxiv_metadata(identifier: str) -> dict:
    """Title, first posting date and license, read from the abstract page."""
    bare = re.sub(r"v\d+$", "", identifier)
    try:
        page = _fetch(f"https://arxiv.org/abs/{bare}").decode("utf-8", "replace")
    except OSError:
        return {}
    title = re.search(r'<meta name="citation_title" content="([^"]*)"', page)
    posted = re.search(r"Submitted on (\d{1,2} \w{3} \d{4})", page)
    license_link = re.search(r'href="(https?://(?:arxiv\.org/licenses|creativecommons\.org)[^"]+)"', page)
    first_public = ""
    if posted:
        first_public = datetime.strptime(posted.group(1), "%d %b %Y").date().isoformat()
    return {
        "title": html.unescape(title.group(1)) if title else "",
        "first_public": first_public,
        "license": license_link.group(1) if license_link else "",
    }


def load_paper(ref: str, private_dir: Path) -> tuple[Paper, str]:
    """Return the record and the full text. The text stays in the private folder."""
    private_dir.mkdir(parents=True, exist_ok=True)
    match = ARXIV_ID.search(ref.strip())
    local = Path(ref)
    if local.exists():
        suffix = local.suffix.lower()
        text = text_from_pdf(local) if suffix == ".pdf" else local.read_text(encoding="utf-8", errors="replace")
        paper = Paper(ref=local.name, url="", title=local.stem, first_public="", license="", source_kind=suffix.lstrip(".") or "text", sha256="")
    elif match:
        identifier = match.group(1)
        meta = arxiv_metadata(identifier)
        text = text_from_arxiv_source(_fetch(f"https://arxiv.org/e-print/{identifier}"))
        kind = "arxiv-latex"
        if not text.strip():
            pdf_path = private_dir / "paper.pdf"
            pdf_path.write_bytes(_fetch(f"https://arxiv.org/pdf/{identifier}"))
            text = text_from_pdf(pdf_path)
            kind = "arxiv-pdf-text"
        paper = Paper(
            ref=f"arXiv:{identifier}",
            url=f"https://arxiv.org/abs/{identifier}",
            title=meta.get("title", ""),
            first_public=meta.get("first_public", ""),
            license=meta.get("license", ""),
            source_kind=kind,
            sha256="",
        )
    elif ref.startswith(("http://", "https://")):
        pdf_path = private_dir / "paper.pdf"
        pdf_path.write_bytes(_fetch(ref))
        text = text_from_pdf(pdf_path)
        paper = Paper(ref=ref, url=ref, title="", first_public="", license="", source_kind="pdf-text", sha256="")
    else:
        raise FileNotFoundError(f"Cannot read paper {ref!r}. Give a file, a URL, or arxiv:ID.")
    paper.sha256 = sha256_text(text)
    (private_dir / "paper_full.txt").write_text(text, encoding="utf-8")
    (private_dir / "paper.json").write_text(json.dumps(paper.to_dict(), indent=2), encoding="utf-8")
    return paper, text


def redact(text: str, strings: list[str]) -> tuple[str, dict]:
    """Blank the given strings and all links to code. Report anything that did not match."""
    missed = []
    applied = 0
    for item in sorted({s for s in strings if s.strip()}, key=len, reverse=True):
        count = text.count(item)
        if count:
            text = text.replace(item, REMOVED)
            applied += count
        else:
            missed.append(item)
    text, links = CODE_LINK.subn(LINK_REMOVED, text)
    return text, {"strings_removed": applied, "strings_not_found": missed, "code_links_removed": links}


NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s*(?:\\times|\\cdot|×|x)\s*10\s*\^?\s*\{?\s*([+-−]?\d+)\s*\}?|[eE]([+-]?\d+))?"
)


def numbers_in(text: str) -> list[tuple[float, str, int]]:
    """Every number in the text as (value, printed form, offset)."""
    found = []
    for match in NUMBER.finditer(text):
        exponent = match.group(2) or match.group(3) or "0"
        try:
            value = float(match.group(1).replace(",", "")) * 10 ** int(exponent.replace("−", "-"))
        except (ValueError, OverflowError):
            continue
        found.append((value, match.group(0), match.start()))
    return found


def significant_digits(printed: str) -> int:
    mantissa = re.match(r"[\d,]+(?:\.\d+)?", printed).group(0)
    return len(mantissa.replace(",", "").replace(".", "").lstrip("0"))


def leak_check(text: str, values: dict[str, float], rel: float = 0.005) -> list[dict]:
    """Which target values still appear in what the agent could read, to three or more digits.

    Signs are ignored, because a minus sign in text takes many forms.
    """
    hits = []
    numbers = [n for n in numbers_in(text) if significant_digits(n[1]) >= 3]
    for key, value in values.items():
        if not isinstance(value, (int, float)) or value == 0:
            continue
        for number, printed, offset in numbers:
            if abs(number - abs(value)) <= rel * abs(value):
                start = max(0, offset - 50)
                hits.append({"key": key, "value": value, "printed": printed, "context": " ".join(text[start:offset + 40].split())})
                break
    return hits
