import pytest

from app.llm.parsing import extract_json


def test_extract_json_pure_object() -> None:
    assert extract_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_extract_json_with_code_fence() -> None:
    text = '```json\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_extract_json_with_bare_code_fence() -> None:
    text = '```\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_extract_json_with_surrounding_prose() -> None:
    text = '물론이죠! 아래는 추천입니다:\n{"a": 1}\n이상입니다.'
    assert extract_json(text) == {"a": 1}


def test_extract_json_with_nested_objects() -> None:
    text = '설명: {"a": {"min": "5:00", "max": "5:30"}, "b": [1, 2, 3]} 끝.'
    assert extract_json(text) == {"a": {"min": "5:00", "max": "5:30"}, "b": [1, 2, 3]}


def test_extract_json_unparseable_raises() -> None:
    with pytest.raises(ValueError):
        extract_json("이건 그냥 텍스트입니다, JSON이 아니에요.")


def test_extract_json_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        extract_json("")
