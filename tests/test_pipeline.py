import json

import pytest
from conftest import GOOD_ADAPTER, GOOD_DERIVE, SPEC, make_authors_repo, write_recording

from blindrepro.judges import RecordedJudge, Session
from blindrepro.paper import Paper
from blindrepro.pipeline import RunStopped, cutoff_statement, run_case, show
from blindrepro.verify import verify


def run(tmp_path, case_for, derive=GOOD_DERIVE, adapter=GOOD_ADAPTER, area="3.14159265", spec=None, **options):
    repo = make_authors_repo(tmp_path / "authors_repo", area)
    recording = write_recording(tmp_path / "recording", derive, adapter, spec)
    return run_case(case_for(repo, **options), RecordedJudge(recording))


def test_good_run_reproduces_and_writes_the_note(tmp_path, case_for):
    verdict = run(tmp_path, case_for)
    assert verdict["comparison"]["status"] == "REPRODUCED"
    assert verdict["comparison"]["max_error"] < 1e-6
    note = (tmp_path / "run" / "verdict.md").read_text(encoding="utf-8")
    assert "REPRODUCED" in note
    assert "What was blinded" in note
    assert "What was not blinded" in note
    assert verdict["blinding"]["freeze_hash"] in note


def test_terminal_output_starts_with_the_table(tmp_path, case_for, capsys):
    verdict = run(tmp_path, case_for)
    capsys.readouterr()
    show(verdict)
    first = capsys.readouterr().out.splitlines()[0]
    assert first.startswith("quantity")
    assert "error" in first


def test_wrong_authors_value_diverges_with_the_real_error(tmp_path, case_for):
    verdict = run(tmp_path, case_for, area="2.0")
    assert verdict["comparison"]["status"] == "DIVERGED"
    assert abs(verdict["comparison"]["max_error"] - (3.14159265358979 - 2) / 2) < 1e-9


def test_authors_code_that_does_not_run_is_reported_as_a_finding(tmp_path, case_for):
    verdict = run(tmp_path, case_for, adapter=None)
    assert verdict["comparison"]["status"] == "NOT COMPARED"
    note = (tmp_path / "run" / "verdict.md").read_text(encoding="utf-8")
    assert "needs a compiler" in note


def test_adapter_that_crashes_is_reported_with_its_error(tmp_path, case_for):
    verdict = run(tmp_path, case_for, adapter="raise ValueError('their code broke')\n")
    assert verdict["comparison"]["status"] == "NOT COMPARED"
    assert "their code broke" in verdict["code"]["could_not_run"]


def test_code_that_cannot_be_fetched_is_not_compared(tmp_path, case_for):
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER)
    verdict = run_case(case_for(tmp_path / "no_such_repo"), RecordedJudge(recording))
    assert verdict["comparison"]["status"] == "NOT COMPARED"
    assert "could not be fetched" in verdict["comparison"]["reason"]


def test_derivation_that_crashes_is_not_compared(tmp_path, case_for):
    verdict = run(tmp_path, case_for, derive="raise RuntimeError('stuck')\n")
    assert verdict["comparison"]["status"] == "NOT COMPARED"
    record = json.loads((tmp_path / "run" / "frozen" / "freeze.json").read_text(encoding="utf-8"))
    assert record["derivation_ran"] is False
    assert "stuck" in record["script_error"]


def test_derivation_reaching_for_the_network_is_counted(tmp_path, case_for):
    derive = (
        "import json, math, socket\n"
        "try:\n    socket.getaddrinfo('github.com', 443)\nexcept PermissionError:\n    pass\n"
        'print(json.dumps({"area": math.pi, "half": math.pi / 2}))\n'
    )
    verdict = run(tmp_path, case_for, derive=derive)
    assert verdict["blinding"]["guard_blocked"] == 1


def test_typed_in_answer_is_flagged(tmp_path, case_for):
    derive = 'import json\nprint(json.dumps({"area": 3.14159265, "half": 1.5707963}))\n'
    verdict = run(tmp_path, case_for, derive=derive)
    assert verdict["comparison"]["status"] == "REPRODUCED"
    assert len(verdict["blinding"]["literals"]) == 2
    note = (tmp_path / "run" / "verdict.md").read_text(encoding="utf-8")
    assert "match a target value" in note


def test_answers_and_links_are_gone_from_what_the_agent_reads(tmp_path, case_for):
    run(tmp_path, case_for)
    shown = (tmp_path / "run" / "private" / "paper_shown.txt").read_text(encoding="utf-8")
    assert "3.14159" not in shown
    assert "github" not in shown
    assert "pi r^2" in shown


def test_leak_check_reports_a_value_the_redaction_missed(tmp_path, case_for):
    spec = {**SPEC, "redact": []}
    verdict = run(tmp_path, case_for, spec=spec)
    assert verdict["blinding"]["leaks"][0]["key"] == "area"


def test_values_stay_visible_only_when_asked(tmp_path, case_for):
    verdict = run(tmp_path, case_for, show_values=True)
    assert verdict["blinding"]["values_shown"] is True
    assert "3.14159" in (tmp_path / "run" / "private" / "paper_shown.txt").read_text(encoding="utf-8")


class SpyJudge(RecordedJudge):
    def __init__(self, folder):
        super().__init__(folder)
        self.seen = {}
        self.order = []

    def session(self, prompt, workspace, tools, run_config=None, minutes=30, stage=""):
        self.seen[stage] = {
            "files": sorted(p.relative_to(workspace).as_posix() for p in workspace.rglob("*") if p.is_file()),
            "text": {p.name: p.read_text(encoding="utf-8", errors="replace") for p in workspace.glob("*.*") if p.is_file()},
            "tools": list(tools),
            "prompt": prompt,
            "run_config": run_config,
        }
        self.order.append(stage)
        return super().session(prompt, workspace, tools, run_config, minutes, stage)


@pytest.fixture
def spy_run(tmp_path, case_for):
    repo = make_authors_repo(tmp_path / "authors_repo")
    judge = SpyJudge(write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER))
    verdict = run_case(case_for(repo), judge)
    return judge, verdict


def test_blind_agent_never_has_the_authors_code(spy_run):
    judge, _ = spy_run
    blind = judge.seen["derive"]
    assert blind["files"] == ["paper.txt", "spec.json"]
    assert "AREA =" not in " ".join(blind["text"].values())


def test_blind_agent_never_sees_paper_values_or_the_redaction_list(spy_run):
    judge, _ = spy_run
    shown = json.loads(judge.seen["derive"]["text"]["spec.json"])
    assert sorted(shown) == ["claim", "quantities"]
    assert "3.14159" not in judge.seen["derive"]["text"]["paper.txt"]


def test_blind_agent_has_no_shell_or_web(spy_run):
    judge, _ = spy_run
    assert not {"Bash", "PowerShell", "WebFetch", "WebSearch", "Agent"} & set(judge.seen["derive"]["tools"])


def test_blind_prompt_never_names_the_code_location(spy_run, tmp_path):
    judge, _ = spy_run
    assert str(tmp_path / "authors_repo") not in judge.seen["derive"]["prompt"]
    assert "authors_repo" not in json.dumps(judge.seen["derive"]["run_config"])


def test_memory_check_has_no_tools_and_no_paper(spy_run):
    judge, _ = spy_run
    assert judge.seen["recall"]["tools"] == []
    assert judge.seen["recall"]["files"] == []


def test_order_is_derive_then_recall_then_adapter(spy_run):
    judge, verdict = spy_run
    assert judge.order == ["scope", "derive", "recall", "adapter"]
    assert verdict["blinding"]["code_fetched_at"] >= verdict["blinding"]["frozen_at"]


def test_adapter_agent_cannot_see_the_derivation_or_its_values(spy_run):
    judge, _ = spy_run
    adapter = judge.seen["adapter"]
    assert "code/circle.py" in adapter["files"]
    assert not [f for f in adapter["files"] if "derive" in f or "results" in f]
    assert sorted(json.loads(adapter["text"]["spec.json"])) == ["claim", "quantities"]


def test_stop_after_freeze_then_finish_keeps_the_same_hash(tmp_path, case_for):
    repo = make_authors_repo(tmp_path / "authors_repo")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER)
    case = case_for(repo, stop_after_freeze=True)
    with pytest.raises(RunStopped) as stopped:
        run_case(case, RecordedJudge(recording))
    first = json.loads((case.out / "frozen" / "freeze.json").read_text(encoding="utf-8"))["freeze_hash"]
    assert first in str(stopped.value)
    assert not (case.out / "authors").exists()
    case.stop_after_freeze = False
    verdict = run_case(case, RecordedJudge(recording))
    assert verdict["blinding"]["freeze_hash"] == first


def test_changing_the_frozen_files_stops_the_comparison(tmp_path, case_for):
    repo = make_authors_repo(tmp_path / "authors_repo")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER)
    case = case_for(repo, stop_after_freeze=True)
    with pytest.raises(RunStopped):
        run_case(case, RecordedJudge(recording))
    (case.out / "frozen" / "blind" / "derive.py").write_text("print(1)\n", encoding="utf-8")
    case.stop_after_freeze = False
    with pytest.raises(RunStopped, match="changed"):
        run_case(case, RecordedJudge(recording))


def test_not_computable_stops_before_any_derivation(tmp_path, case_for):
    repo = make_authors_repo(tmp_path / "authors_repo")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER, {"not_computable": "needs a telescope"})
    with pytest.raises(RunStopped, match="telescope"):
        run_case(case_for(repo), RecordedJudge(recording))


def test_bad_spec_is_refused(tmp_path, case_for):
    repo = make_authors_repo(tmp_path / "authors_repo")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER, {"claim": "x", "quantities": [{"key": "not a key"}]})
    with pytest.raises(RunStopped, match="bad key"):
        run_case(case_for(repo), RecordedJudge(recording))


def test_memory_check_counts_stated_and_matching_values(tmp_path, case_for):
    repo = make_authors_repo(tmp_path / "authors_repo")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER)
    (recording / "probe").mkdir()
    (recording / "probe" / "recall.json").write_text(json.dumps({"stated": {"area": 3.14, "half": None}}), encoding="utf-8")
    verdict = run_case(case_for(repo), RecordedJudge(recording))
    assert verdict["blinding"]["recall"]["stated"] == 1
    assert verdict["blinding"]["recall"]["matched"] == 1


def test_authors_edit_is_flagged(tmp_path, case_for):
    adapter = (
        'import json, sys\nsys.path.insert(0, "code")\nimport circle\n'
        'print(json.dumps({"area": circle.AREA, "half": circle.AREA / 2}))\n'
    )

    class EditingJudge(RecordedJudge):
        def session(self, prompt, workspace, tools, run_config=None, minutes=30, stage=""):
            done = super().session(prompt, workspace, tools, run_config, minutes, stage)
            if stage == "adapter":
                path = workspace / "code" / "circle.py"
                path.write_text(path.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
            return done

    repo = make_authors_repo(tmp_path / "authors_repo")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, adapter)
    verdict = run_case(case_for(repo), EditingJudge(recording))
    assert verdict["code"]["modified"] is True
    assert "needed an edit" in (tmp_path / "run" / "verdict.md").read_text(encoding="utf-8")
    assert "# edited" in (tmp_path / "run" / "authors" / "patch.diff").read_text(encoding="utf-8")


def test_divergence_asks_for_an_explanation_with_both_sides(tmp_path, case_for):
    class ExplainingJudge(RecordedJudge):
        skip_explain = False
        seen = None

        def session(self, prompt, workspace, tools, run_config=None, minutes=30, stage=""):
            if stage == "explain":
                ExplainingJudge.seen = (sorted(p.name for p in workspace.iterdir()), list(tools))
                return Session("They use a different radius.", "m", "v", 1.0, [], [])
            return super().session(prompt, workspace, tools, run_config, minutes, stage)

    repo = make_authors_repo(tmp_path / "authors_repo", "2.0")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER)
    verdict = run_case(case_for(repo), ExplainingJudge(recording))
    assert verdict["explanation"] == "They use a different radius."
    names, tools = ExplainingJudge.seen
    assert {"derivation", "authors", "comparison.json"} <= set(names)
    assert "Write" not in tools
    assert "a model's reading" in (tmp_path / "run" / "verdict.md").read_text(encoding="utf-8")


def test_verify_passes_a_clean_record(tmp_path, case_for):
    run(tmp_path, case_for)
    lines = []
    assert verify(tmp_path / "run", say=lines.append) == 0
    assert any("Hashes match" in line for line in lines)
    assert any("REPRODUCED" in line for line in lines)


def test_verify_refuses_a_changed_record(tmp_path, case_for):
    run(tmp_path, case_for)
    (tmp_path / "run" / "frozen" / "blind" / "derive.py").write_text("print(1)\n", encoding="utf-8")
    lines = []
    assert verify(tmp_path / "run", say=lines.append) == 2
    assert lines[0].startswith("Note: verify runs the scripts")
    assert lines[1].startswith("REFUSED")


def test_verify_refuses_edited_authors_values(tmp_path, case_for):
    run(tmp_path, case_for, area="2.0")
    record_path = tmp_path / "run" / "authors" / "code_record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["values"]["area"] = 3.14159265
    record_path.write_text(json.dumps(record), encoding="utf-8")
    lines = []
    assert verify(tmp_path / "run", say=lines.append, skip_authors=True) == 2
    assert "authors/code_record.json changed after the seal" in "\n".join(lines)


def test_verify_refuses_an_unexpected_freeze_hash(tmp_path, case_for):
    verdict = run(tmp_path, case_for)
    lines = []
    assert verify(tmp_path / "run", say=lines.append, expect="0" * 64) == 2
    assert verify(tmp_path / "run", say=lines.append, expect=verdict["blinding"]["freeze_hash"]) == 0


def test_verify_is_incomplete_when_the_derivation_does_not_rerun(tmp_path, case_for, monkeypatch):
    run(tmp_path, case_for)
    from blindrepro import verify as verify_module

    monkeypatch.setattr(verify_module, "rerun_derivation", lambda bundle, record: (None, 0.0))
    lines = []
    assert verify(tmp_path / "run", say=lines.append) == 1
    assert any("this check is incomplete" in line for line in lines)


def test_verify_refuses_a_package_line_that_is_not_a_name(tmp_path, case_for):
    from blindrepro.record import canonical, seal, sha256_bytes

    run(tmp_path, case_for)
    freeze_path = tmp_path / "run" / "frozen" / "freeze.json"
    record = json.loads(freeze_path.read_text(encoding="utf-8"))
    record.pop("freeze_hash")
    record["packages"] = ["--index-url=https://example.com/simple", "numpy"]
    record["freeze_hash"] = sha256_bytes(canonical(record))
    freeze_path.write_text(json.dumps(record), encoding="utf-8")
    seal(tmp_path / "run", record["freeze_hash"])
    lines = []
    assert verify(tmp_path / "run", say=lines.append) == 2
    assert any("not a plain package name" in line for line in lines)


def test_finishing_with_another_tolerance_is_refused(tmp_path, case_for):
    repo = make_authors_repo(tmp_path / "authors_repo", "3.14159265")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER, None)
    with pytest.raises(RunStopped):
        run_case(case_for(repo, stop_after_freeze=True), RecordedJudge(recording))
    with pytest.raises(RunStopped, match="same settings"):
        run_case(case_for(repo, tolerance=0.5), RecordedJudge(recording))


def test_new_files_in_the_authors_code_count_as_an_edit(tmp_path, case_for):
    adapter = (
        "import json, pathlib, sys\n"
        "pathlib.Path('code/extra.py').write_text('AREA = 3.14159265' + chr(10))\n"
        "sys.path.insert(0, 'code')\n"
        "import extra\n"
        'print(json.dumps({"area": extra.AREA, "half": extra.AREA / 2}))\n'
    )
    verdict = run(tmp_path, case_for, adapter=adapter)
    assert verdict["code"]["modified"] is True
    patch = (tmp_path / "run" / "authors" / "patch.diff").read_text(encoding="utf-8")
    assert "+++ b/extra.py" in patch


def test_verdict_records_the_seal(tmp_path, case_for):
    verdict = run(tmp_path, case_for)
    seal_record = json.loads((tmp_path / "run" / "seal.json").read_text(encoding="utf-8"))
    assert seal_record["seal_hash"] == verdict["seal_hash"]
    assert "verdict.json" in seal_record["files"]
    assert not any(name.startswith("private/") for name in seal_record["files"])


def paper_dated(date):
    return Paper("arXiv:1", "", "", date, "", "x", "")


def test_cutoff_statement_for_a_paper_after_the_cutoff():
    result = cutoff_statement(paper_dated("2026-09-30"), "claude-opus-5-5", "")
    assert result["after_cutoff"] is True
    assert "should not be in training data" in result["statement"]


def test_cutoff_statement_for_a_paper_before_the_cutoff():
    result = cutoff_statement(paper_dated("2021-05-24"), "claude-opus-5-5", "")
    assert result["after_cutoff"] is False
    assert "may be in training data" in result["statement"]


def test_cutoff_statement_for_an_unknown_model_says_so():
    assert "not known" in cutoff_statement(paper_dated("2021-05-24"), "other-model", "")["statement"]


def test_cutoff_override_is_used():
    assert cutoff_statement(paper_dated("2021-05-24"), "other-model", "2020-01")["after_cutoff"] is True
