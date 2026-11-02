import json

from blindrepro.record import check_freeze, check_seal, freeze, seal, shareable_transcript, tool_calls


def frozen(tmp_path):
    folder = tmp_path / "frozen"
    (folder / "blind").mkdir(parents=True)
    (folder / "blind" / "derive.py").write_text("print(1)\n", encoding="utf-8")
    (folder / "results.json").write_text("{}", encoding="utf-8")
    return folder, freeze(folder, {"frozen_at": "2026-11-02T00:00:00Z", "tolerance": 0.05})


def test_clean_record_passes(tmp_path):
    folder, record = frozen(tmp_path)
    assert check_freeze(folder) == []
    assert len(record["freeze_hash"]) == 64


def test_changing_one_byte_is_caught(tmp_path):
    folder, _ = frozen(tmp_path)
    (folder / "blind" / "derive.py").write_text("print(2)\n", encoding="utf-8")
    assert check_freeze(folder) == ["blind/derive.py changed after the freeze"]


def test_deleting_a_file_is_caught(tmp_path):
    folder, _ = frozen(tmp_path)
    (folder / "results.json").unlink()
    assert check_freeze(folder) == ["results.json is missing"]


def test_adding_a_file_is_caught(tmp_path):
    folder, _ = frozen(tmp_path)
    (folder / "blind" / "extra.py").write_text("x", encoding="utf-8")
    assert check_freeze(folder) == ["blind/extra.py was added after the freeze"]


def test_editing_the_stated_facts_is_caught(tmp_path):
    folder, _ = frozen(tmp_path)
    path = folder / "freeze.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["tolerance"] = 0.5
    path.write_text(json.dumps(data), encoding="utf-8")
    assert "freeze.json was edited" in check_freeze(folder)[0]


def test_missing_freeze_is_caught(tmp_path):
    assert check_freeze(tmp_path) == ["freeze.json is missing"]


EVENTS = [
    {"type": "system", "subtype": "init", "cwd": "C:\\tmp\\w", "session_id": "s", "plugins": ["x"]},
    {"type": "rate_limit_event"},
    {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "id": "1", "name": "Read", "input": {"file_path": "C:\\tmp\\w\\paper.txt"}}]},
    },
    {
        "type": "user",
        "tool_use_result": {"file": {"content": "FULL PAPER TEXT"}},
        "message": {"content": [{"type": "tool_result", "tool_use_id": "1", "content": "FULL PAPER TEXT"}]},
    },
    {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "id": "2", "name": "Write", "input": {"file_path": "C:\\tmp\\w\\derive.py", "content": "x=1"}}]},
    },
    {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "2", "content": "written to C:\\tmp\\w\\derive.py"}]}},
]


def test_shareable_transcript_withholds_what_was_read_and_keeps_a_hash():
    out = json.dumps(shareable_transcript(json.loads(json.dumps(EVENTS)), [("C:\\tmp\\w", "<work>")]))
    assert "FULL PAPER TEXT" not in out
    assert "withheld, 15 characters, sha256" in out


def test_shareable_transcript_swaps_local_paths_and_drops_noise():
    out = shareable_transcript(json.loads(json.dumps(EVENTS)), [("C:\\tmp\\w", "<work>")])
    text = json.dumps(out)
    assert "tmp" not in text
    assert "rate_limit_event" not in text
    assert "session_id" not in text
    assert out[0]["cwd"] == "<work>"


def test_shareable_transcript_keeps_what_the_agent_wrote():
    text = json.dumps(shareable_transcript(json.loads(json.dumps(EVENTS)), []))
    assert "x=1" in text


def test_tool_calls_lists_every_call():
    assert [c["tool"] for c in tool_calls(EVENTS)] == ["Read", "Write"]


def test_paths_are_swapped_in_every_spelling():
    swaps = [("C:\\Users\\someone", "<home>"), ("Users\\someone", "<home>")]
    events = [{"type": "assistant", "message": {"content": "C:\\Users\\someone\\a C:/Users/someone/b C:\\\\Users\\\\someone\\\\c /c/Users/someone/d"}}]
    text = shareable_transcript(events, swaps)[0]["message"]["content"]
    assert "someone" not in text


def test_a_record_file_added_in_a_subfolder_is_caught(tmp_path):
    folder, _ = frozen(tmp_path)
    (folder / "blind" / "freeze.json").write_text("{}", encoding="utf-8")
    assert check_freeze(folder) == ["blind/freeze.json was added after the freeze"]


def test_seal_covers_the_whole_run_except_private(tmp_path):
    run = tmp_path / "run"
    (run / "authors").mkdir(parents=True)
    (run / "private").mkdir()
    (run / "authors" / "code_record.json").write_text('{"values": {"a": 1}}', encoding="utf-8")
    seal(run, "f" * 64)
    (run / "private" / "paper_full.txt").write_text("text", encoding="utf-8")
    assert check_seal(run) == []
    (run / "authors" / "code_record.json").write_text('{"values": {"a": 2}}', encoding="utf-8")
    assert check_seal(run) == ["authors/code_record.json changed after the seal"]
