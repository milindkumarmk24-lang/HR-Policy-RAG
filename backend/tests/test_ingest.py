from app.ingest import categorise, chunk_body, chunk_pdf, clean_text, detect_headings, strip_running_lines

from tests.conftest import SAMPLE


def test_sample_handbook_chunks_have_pages_and_sections():
    chunks, pages = chunk_pdf(SAMPLE, "doc1", SAMPLE.name)
    assert pages == 17
    assert 40 <= len(chunks) <= 120
    sick = [c for c in chunks if c.metadata["section"] == "3.4 Sick Leave"]
    assert sick, "section-aware chunking should produce a Sick Leave chunk"
    assert sick[0].metadata["page"] == 4
    assert sick[0].metadata["category"] == "Leave"
    assert "medical certificate" in chunk_body(sick[0])
    # every chunk carries a 1-based page and a unique id
    ids = {c.metadata["chunk_id"] for c in chunks}
    assert len(ids) == len(chunks)
    assert all(1 <= c.metadata["page"] <= c.metadata["page_end"] <= pages for c in chunks)


def test_running_header_and_footer_removed():
    chunks, _ = chunk_pdf(SAMPLE, "doc1", SAMPLE.name)
    text = "\n".join(c.page_content for c in chunks)
    assert "Employee Handbook 2026\n" not in text
    assert "Page 7" not in text


def test_chunks_do_not_straddle_sections():
    chunks, _ = chunk_pdf(SAMPLE, "doc1", SAMPLE.name)
    for c in chunks:
        body = chunk_body(c)
        # a chunk may start with its own heading but never contains the next section's heading
        assert "3.5 Public Holidays" not in body or c.metadata["section"] == "3.5 Public Holidays"


def test_heading_detection_rejects_sentences():
    text = "3.4 Sick Leave\nYou receive 10 working days.\n30 days of unused earned leave carry forward to the\n" \
           "2. Apply on PeopleDesk at least 7 days in advance\nLEAVE POLICY\n"
    titles = [h.title for h in detect_headings(text)]
    assert titles == ["3.4 Sick Leave", "Leave Policy"]


def test_strip_running_lines_and_clean():
    pages = [f"ACME Handbook\nPolicy about topic {chr(65 + i)}\nPage {i}" for i in range(1, 6)]
    out = strip_running_lines(pages)
    assert out[0].strip() == "Policy about topic B"
    raw = "\x7f Bullet one\n\x7f Bullet two is wrap-\nped here\nA medical\ncertificate is needed.\n3.5 Public Holidays"
    assert clean_text(raw) == "- Bullet one\n- Bullet two is wrapped here\nA medical certificate is needed.\n" \
                              "3.5 Public Holidays"


def test_categorise():
    assert categorise("3. Leave Policy > 3.7 Maternity Leave") == "Leave"
    assert categorise("7.2 Hotel Limits and Per Diem") == "Travel & expenses"
    assert categorise("Something", "nothing relevant here") == "General"


def test_roman_and_lettered_headings():
    text = ("I. Introduction\nSome text here.\nII. Pregnancy and Childbirth\nA. Sick Leave\nbody\n"
            "H. Telework\nbody\nI. Part-Time Work\nbody\nIII. Adoption and Foster Care\nA. Sick Leave\nbody")
    titles = [h.title for h in detect_headings(text)]
    assert titles == ["I. Introduction", "II. Pregnancy and Childbirth", "II.A Sick Leave", "II.H Telework",
                      "II.I Part-Time Work", "III. Adoption and Foster Care", "III.A Sick Leave"]


def test_table_of_contents_lines_dropped():
    raw = "Contents\nA. Sick Leave .................... 12\nB. Annual Leave . . . . . . . . 14\nReal text."
    assert clean_text(raw) == "Contents\nReal text."
