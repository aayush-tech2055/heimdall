"""The Pydantic Flag and the TypeScript Flag must stay identical (CLAUDE.md, flag contract)."""

import re
import typing
from pathlib import Path

import pytest

from app.models.flag import CATEGORIES, LAYERS, SEVERITIES, SOURCE_TYPES, Flag

TS_PATH = Path(__file__).resolve().parents[3] / "frontend" / "src" / "types" / "flag.ts"
pytestmark = pytest.mark.skipif(not TS_PATH.exists(), reason="frontend not checked out")


def _ts() -> str:
    return TS_PATH.read_text(encoding="utf-8")


def _ts_const(name: str) -> tuple[str, ...]:
    match = re.search(rf"export const {name} = \[(.*?)\] as const;", _ts(), re.S)
    assert match, f"{name} not found in flag.ts"
    return tuple(re.findall(r'"([^"]+)"', match.group(1)))


def _ts_fields(interface: str) -> set[str]:
    match = re.search(rf"export interface {interface} \{{(.*?)\n\}}", _ts(), re.S)
    assert match, f"{interface} not found in flag.ts"
    return set(re.findall(r"^\s*(\w+)\??:", match.group(1), re.M))


def test_enums_match():
    assert _ts_const("SOURCE_TYPES") == SOURCE_TYPES
    assert _ts_const("CATEGORIES") == CATEGORIES
    assert _ts_const("SEVERITIES") == SEVERITIES
    assert _ts_const("LAYERS") == LAYERS


def test_flag_fields_match():
    assert _ts_fields("Flag") == set(Flag.model_fields)


def test_location_fields_match():
    for model in typing.get_args(Flag.model_fields["location"].annotation):
        assert _ts_fields(model.__name__) == set(model.model_fields), model.__name__
