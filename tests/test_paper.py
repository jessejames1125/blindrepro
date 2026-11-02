import gzip
import io
import tarfile

from blindrepro.paper import (
    REMOVED,
    leak_check,
    load_paper,
    numbers_in,
    redact,
    text_from_arxiv_source,
)


def tar_of(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as package:
        for name, body in files.items():
            data = body.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            package.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def test_redact_removes_strings_and_reports_misses():
    text, report = redact("value is 4.2 here", ["value is 4.2", "not in the text"])
    assert text == f"{REMOVED} here"
    assert report["strings_removed"] == 1
    assert report["strings_not_found"] == ["not in the text"]


def test_redact_handles_overlapping_strings_longest_first():
    text, _ = redact("the result 4.2 keV", ["4.2", "the result 4.2 keV"])
    assert text == REMOVED


def test_redact_removes_links_to_code_even_with_no_strings():
    text, report = redact("See https://github.com/a/b and \\url{https://zenodo.org/record/1}.", [])
    assert "github" not in text
    assert "zenodo" not in text
    assert report["code_links_removed"] == 2


def test_redact_leaves_ordinary_links_alone():
    text, report = redact("See https://example.org/doc", [])
    assert "example.org" in text
    assert report["code_links_removed"] == 0


def test_numbers_are_read_in_paper_formats():
    values = [n[0] for n in numbers_in(r"a 2.95e21 b 2.95 \times 10^{21} c 2.95×10^21 d 1.5")]
    assert values.count(2.95e21) == 3
    assert 1.5 in values


def test_leak_check_finds_a_value_left_in_the_text():
    hits = leak_check(r"minimum of 2.95 \times 10^{21} keV", {"tp": 2.9450e21})
    assert hits and hits[0]["key"] == "tp"


def test_leak_check_is_clean_when_the_value_is_gone():
    assert leak_check(f"minimum of {REMOVED} keV", {"tp": 2.945e21}) == []


def test_leak_check_finds_thousands_separators_and_negative_values():
    assert leak_check("a total of 12,345.6 events", {"n": 12345.6})[0]["printed"] == "12,345.6"
    assert leak_check("the energy is −0.7639 per spin", {"e": -0.7639})[0]["key"] == "e"


def test_leak_check_ignores_a_nearby_number_the_target_does_not_round_to():
    # Optimal angles printed next to the targets in a QAOA paper sat within 0.5% of them.
    assert leak_check("angles 0.3028 and 0.5710", {"nu": 0.30327, "nu6": 0.57214}) == []


def test_leak_check_finds_the_target_rounded_to_fewer_digits():
    assert leak_check("about 0.303 at depth one", {"nu": 0.30327})[0]["printed"] == "0.303"


def test_leak_check_ignores_low_precision_coincidences():
    assert leak_check("Section 3 and figure 12", {"count": 12.0}) == []


def test_arxiv_source_is_flattened_without_comments_or_disk_writes(tmp_path):
    blob = tar_of(
        {
            "main.tex": "\\documentclass{article}\n\\input{sec}\n% private note 9.99\nbody\n",
            "sec.tex": "section text\n",
            "old.tex": "unused draft\n",
        }
    )
    text = text_from_arxiv_source(blob)
    assert "section text" in text
    assert "body" in text
    assert "private note" not in text
    assert "unused draft" not in text


def test_arxiv_source_ignores_path_tricks_in_the_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    blob = tar_of({"../../evil.tex": "\\documentclass{a} x", "main.tex": "\\documentclass{article} y"})
    text_from_arxiv_source(blob)
    assert not (tmp_path.parent.parent / "evil.tex").exists()


def test_single_gzip_source_is_read():
    assert text_from_arxiv_source(gzip.compress(b"\\documentclass{a} z")).endswith("z")


def test_local_text_paper_is_loaded_and_hashed(tmp_path):
    source = tmp_path / "p.tex"
    source.write_text("hello", encoding="utf-8")
    paper, text = load_paper(str(source), tmp_path / "private")
    assert text == "hello"
    assert len(paper.sha256) == 64
    assert (tmp_path / "private" / "paper_full.txt").exists()
