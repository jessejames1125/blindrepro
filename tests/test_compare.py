import math

from blindrepro.compare import compare, flatten, import_check, literal_check, parse_result_line


def test_reproduced_when_all_values_are_within_the_limit():
    result = compare({"a": 1.01, "b": 2.0}, {"a": 1.0, "b": 2.0}, tolerance=0.05)
    assert result.status == "REPRODUCED"
    assert abs(result.max_error - 0.01) < 1e-9


def test_one_miss_is_diverged_with_the_true_max_error():
    result = compare({"a": 1.0, "b": 3.0}, {"a": 1.0, "b": 2.0}, tolerance=0.05)
    assert result.status == "DIVERGED"
    assert abs(result.max_error - 0.5) < 1e-9
    assert [r.within for r in result.rows] == [True, False]


def test_error_is_measured_against_the_authors_value():
    result = compare({"a": 2.0}, {"a": 1.0}, tolerance=2.0)
    assert result.max_error == 1.0


def test_zero_on_the_authors_side_uses_plain_difference():
    result = compare({"a": 0.01}, {"a": 0.0}, tolerance=0.05)
    assert result.status == "REPRODUCED"
    assert result.max_error == 0.01


def test_blind_side_missing_a_value_is_a_miss_not_a_pass():
    result = compare({"a": None, "b": 1.0}, {"a": 1.0, "b": 1.0})
    assert result.status == "DIVERGED"
    assert result.rows[0].note == "blind side gave no value"


def test_expected_key_nobody_gave_is_a_miss():
    result = compare({"a": 1.0}, {"a": 1.0}, expected_keys=["a", "z"])
    assert result.status == "DIVERGED"
    assert any(r.key == "z" for r in result.rows)


def test_no_authors_values_is_not_compared_and_keeps_the_blind_values():
    result = compare({"a": 1.0}, None)
    assert result.status == "NOT COMPARED"
    assert result.rows[0].derived == 1.0
    assert result.max_error is None


def test_no_derivation_is_not_compared():
    assert compare(None, {"a": 1.0}).status == "NOT COMPARED"


def test_lists_compare_element_by_element():
    result = compare({"a": [1.0, 2.0]}, {"a": [1.0, 4.0]}, tolerance=0.05)
    assert [r.key for r in result.rows] == ["a[0]", "a[1]"]
    assert result.status == "DIVERGED"


def test_nan_and_infinity_are_treated_as_no_value():
    assert flatten({"a": math.nan, "b": math.inf, "c": 1}) == {"a": None, "b": None, "c": 1.0}
    assert compare({"a": math.nan}, {"a": 1.0}).status == "NOT COMPARED"


def test_paper_value_is_shown_but_never_changes_the_status():
    result = compare({"a": 1.0}, {"a": 1.0}, {"a": 99.0})
    assert result.status == "REPRODUCED"
    assert result.rows[0].paper == 99.0


def test_result_line_takes_the_last_json_object():
    assert parse_result_line('noise\n{"a": 1}\nmore\n{"a": 2}\n') == {"a": 2}


def test_result_line_accepts_multiline_json_alone():
    assert parse_result_line('{\n"a": 1\n}\n') == {"a": 1}


def test_result_line_rejects_text():
    assert parse_result_line("no json here") is None


def test_literal_check_flags_a_typed_in_answer():
    source = "x = 2.9450e21\ny = 3\n"
    hits = literal_check(source, {"target": 2.9450416e21})
    assert hits == [{"key": "target", "literal": 2.945e21, "line": 1}]


def test_literal_check_ignores_small_integers_and_computed_values():
    source = "import math\nx = 3\ny = math.pi * 2\n"
    assert literal_check(source, {"three": 3.0, "tau": 6.283185}) == []


def test_literal_check_survives_a_syntax_error():
    assert literal_check("def (", {"a": 1.0}) == []


def test_import_check_finds_low_level_modules():
    source = "import numpy\nimport ctypes\nfrom urllib.request import urlopen\nx = __import__('socket')\n"
    assert import_check(source) == ["ctypes", "socket", "urllib"]


def test_import_check_is_quiet_for_numeric_code():
    assert import_check("import numpy as np\nfrom scipy import linalg\nimport json, math\n") == []
