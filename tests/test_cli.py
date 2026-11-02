import json
import shutil

import pytest
from conftest import GOOD_ADAPTER, GOOD_DERIVE, PAPER, make_authors_repo, write_recording

from blindrepro import cli, doctor
from blindrepro.pipeline import Case, run_case
from blindrepro.judges import RecordedJudge
from blindrepro.record import check_freeze, check_seal


def test_version(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert "blindrepro" in capsys.readouterr().out


def test_run_with_a_recorded_judge_prints_the_table_and_writes_a_note(tmp_path, capsys):
    repo = make_authors_repo(tmp_path / "repo")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER)
    paper = tmp_path / "paper.txt"
    paper.write_text(PAPER, encoding="utf-8")
    out = tmp_path / "run"
    code = cli.main(
        ["run", str(paper), "--target", "the area", "--code", str(repo), "--out", str(out), "--judge", f"recorded:{recording}", "--model-cutoff", "2026-06"]
    )
    printed = capsys.readouterr().out
    assert code == 0
    assert "REPRODUCED" in printed
    assert (out / "verdict.md").exists()


def test_run_with_an_unknown_judge_is_a_clear_error(tmp_path, capsys):
    code = cli.main(["run", "x", "--target", "y", "--code", "z", "--judge", "nope", "--out", str(tmp_path / "r")])
    assert code == 3
    assert "Unknown judge" in capsys.readouterr().out


def test_run_exits_nonzero_when_it_diverges(tmp_path, capsys):
    repo = make_authors_repo(tmp_path / "repo", "2.0")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER)
    paper = tmp_path / "paper.txt"
    paper.write_text(PAPER, encoding="utf-8")
    code = cli.main(["run", str(paper), "--target", "a", "--code", str(repo), "--out", str(tmp_path / "r"), "--judge", f"recorded:{recording}"])
    assert code == 1
    assert "DIVERGED" in capsys.readouterr().out


def test_a_stopped_run_says_why_in_its_folder(tmp_path, capsys):
    repo = make_authors_repo(tmp_path / "repo")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER, {"not_computable": "needs a dataset"})
    paper = tmp_path / "paper.txt"
    paper.write_text(PAPER, encoding="utf-8")
    out = tmp_path / "r"
    code = cli.main(["run", str(paper), "--target", "a", "--code", str(repo), "--out", str(out), "--judge", f"recorded:{recording}"])
    assert code == 3
    assert "needs a dataset" in (out / "stopped.txt").read_text(encoding="utf-8")


def test_a_failed_install_stops_the_run_with_its_reason(tmp_path, capsys, monkeypatch):
    from blindrepro import envs, pipeline

    def fail(case, judge):
        raise envs.InstallFailed("Installing the packages took more than 15 minutes, so it was stopped.")

    monkeypatch.setattr(pipeline, "run_case", fail)
    out = tmp_path / "r"
    code = cli.main(["run", "x", "--target", "y", "--code", "z", "--out", str(out), "--judge", f"recorded:{tmp_path}"])
    assert code == 3
    assert "15 minutes" in (out / "stopped.txt").read_text(encoding="utf-8")


def bundled_case(tmp_path):
    repo = make_authors_repo(tmp_path / "repo")
    recording = write_recording(tmp_path / "recording", GOOD_DERIVE, GOOD_ADAPTER)
    paper = tmp_path / "paper.txt"
    paper.write_text(PAPER, encoding="utf-8")
    bundle = tmp_path / "bundle"
    run_case(Case(str(paper), "the area", str(repo), bundle), RecordedJudge(recording))
    shutil.rmtree(bundle / "private")
    return bundle


def use_demo(monkeypatch, bundle):
    monkeypatch.setattr(cli, "_bundled", lambda name: bundle)
    frozen = json.loads((bundle / "frozen" / "freeze.json").read_text(encoding="utf-8"))
    monkeypatch.setitem(cli.DEMO_HASHES, "lawson", frozen["freeze_hash"])


def test_the_shipped_demo_matches_its_published_hash_and_seal():
    bundle = cli._bundled("lawson")
    assert bundle is not None
    frozen = json.loads((bundle / "frozen" / "freeze.json").read_text(encoding="utf-8"))
    assert frozen["freeze_hash"] == cli.DEMO_HASHES["lawson"]
    assert check_freeze(bundle / "frozen") == []
    assert check_seal(bundle) == []
    assert (bundle / "authors" / "vendor" / "LICENSE").exists()


def test_a_demo_whose_hash_differs_from_the_published_one_is_refused(tmp_path, capsys, monkeypatch):
    bundle = bundled_case(tmp_path)
    monkeypatch.setattr(cli, "_bundled", lambda name: bundle)
    monkeypatch.setitem(cli.DEMO_HASHES, "lawson", "0" * 64)
    assert cli.main(["demo", "lawson"]) == 2


def test_demo_replays_and_compares_for_real(tmp_path, capsys, monkeypatch):
    bundle = bundled_case(tmp_path)
    use_demo(monkeypatch, bundle)
    assert cli.main(["demo", "lawson"]) == 0
    printed = capsys.readouterr().out
    assert "Hashes match" in printed
    assert "REPRODUCED" in printed
    assert "Derivation rerun" in printed
    assert "sealed record" in printed
    assert "--full" in printed


def test_demo_full_reruns_the_authors_code(tmp_path, capsys, monkeypatch):
    bundle = bundled_case(tmp_path)
    use_demo(monkeypatch, bundle)
    assert cli.main(["demo", "lawson", "--full"]) == 0
    printed = capsys.readouterr().out
    assert "Authors' code rerun" in printed
    assert "REPRODUCED" in printed


def test_demo_tamper_shows_the_refusal(tmp_path, capsys, monkeypatch):
    bundle = bundled_case(tmp_path)
    monkeypatch.setattr(cli, "_bundled", lambda name: bundle)
    assert cli.main(["demo", "lawson", "--tamper"]) == 0
    printed = capsys.readouterr().out
    assert "REFUSED" in printed
    assert "blind/derive.py changed after the freeze" in printed


def test_demo_with_an_unknown_name_is_a_clear_error(capsys, monkeypatch):
    monkeypatch.setattr(cli, "_bundled", lambda name: None)
    assert cli.main(["demo", "nope"]) == 2
    assert "No demo named" in capsys.readouterr().out


def test_verify_command_returns_the_check_status(tmp_path, capsys):
    bundle = bundled_case(tmp_path)
    assert cli.main(["verify", str(bundle)]) == 0
    assert cli.main(["verify", str(bundle), "--skip-authors"]) == 0
    assert "not rerun" in capsys.readouterr().out


def test_doctor_runs_and_reports_the_guard(capsys):
    assert doctor.run() in (0, 1)
    printed = capsys.readouterr().out
    assert "guard" in printed
    assert "ok  guard" in printed


def test_doctor_never_prints_account_details(capsys, monkeypatch):
    class Done:
        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(command, **options):
        if "--version" in command:
            return Done("1.0 (Claude Code)")
        return Done(json.dumps({"loggedIn": True, "email": "someone@example.com"}))

    monkeypatch.setattr(doctor.shutil, "which", lambda name: "claude")
    monkeypatch.setattr(doctor.subprocess, "run", fake_run)
    ok, note = doctor.check_claude()
    assert ok
    assert "someone" not in note


def test_doctor_says_when_claude_is_not_signed_in(monkeypatch):
    class Done:
        stdout = json.dumps({"loggedIn": False})

    monkeypatch.setattr(doctor.shutil, "which", lambda name: "claude")
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **k: Done())
    ok, note = doctor.check_claude()
    assert not ok
    assert "claude auth login" in note
