# -*- coding: utf-8 -*-
"""Tai lieu tram van hanh (core/tag_docs/*.json) phai NOI DUNG voi than lenh DEF goc.

Moi y quan trong co kich ban mo phong kem checks: sua than lenh, sua bo mo phong hay sua
tai lieu ma lech nhau la bao do o day. Can thu muc DEF cua hang; khong co thi bo qua.
"""
import copy
import re

import pytest

from core import macro_def as MD
from core import tag_docs as TD
from core.block_params import param_meta

EXPECTED = ("820C", "820D", "820E", "820F", "8211")
_PREFIX = ("in:", "out:", "prm:", "ops:", "st:")


def _co_def():
    return bool(MD.body_of(MD.symbol_of("820E")))


needs_def = pytest.mark.skipif(not _co_def(), reason="vendor DEF files not found")


def _cac_kich_ban():
    return [(code, sc) for code in TD.codes() for sc in (TD.doc_for(code) or {}).get("scenarios", [])]


def _cac_cap(node, path="doc"):
    """Moi cap {"en", "vi"} trong tai lieu, kem duong dan de bao loi cho ro."""
    if isinstance(node, dict):
        if "en" in node:
            yield path, node
        for k, v in node.items():
            yield from _cac_cap(v, "%s.%s" % (path, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _cac_cap(v, "%s[%d]" % (path, i))


def test_expected_stations_have_docs():
    assert set(EXPECTED) <= set(TD.codes())
    for code in EXPECTED:
        assert TD.doc_for(code) is not None, code


@pytest.mark.parametrize("code", EXPECTED)
def test_every_text_is_bilingual(code):
    d = TD.doc_for(code)
    pairs = list(_cac_cap(d))
    assert pairs
    for path, p in pairs:
        assert isinstance(p.get("en"), str) and p["en"].strip(), path + " en"
        assert isinstance(p.get("vi"), str) and p["vi"].strip(), path + " vi"


@needs_def
@pytest.mark.parametrize("code,sc", _cac_kich_ban(), ids=lambda x: x if isinstance(x, str) else x.get("id"))
def test_scenario_checks_pass(code, sc):
    assert sc.get("checks"), "scenario %s has no checks" % sc.get("id")
    assert TD.check_scenario(code, sc) == []


@needs_def
@pytest.mark.parametrize("code", EXPECTED)
def test_doc_covers_every_pin_param_and_hmi_signal(code):
    assert TD.coverage(code) == []


@needs_def
@pytest.mark.parametrize("code", EXPECTED)
def test_doc_mentions_nothing_that_is_not_there(code):
    """Khong duoc ke chan / tham so / tin hieu HMI ma than lenh va bang cua hang khong co."""
    d = TD.doc_for(code)
    pins = MD.pins_of(code)
    so_chan = {str(n) for side in pins.values() for n in side}
    assert set(d["pins"]) <= so_chan
    assert set(d["params"]) <= {str(n) for n in param_meta().get(code, {})}
    assert {h["tok"] for h in d["hmi"]} <= set(TD.hmi_tokens(code))


@needs_def
@pytest.mark.parametrize("code", EXPECTED)
def test_section_line_refs_are_inside_the_body(code):
    n = len(MD.body_of(MD.symbol_of(code)))
    for s in TD.doc_for(code)["sections"]:
        so = [int(x) for x in re.findall(r"\d+", s["def"])]
        assert so and all(1 <= x <= n for x in so), (s["def"], n)


@pytest.mark.parametrize("code,sc", _cac_kich_ban(), ids=lambda x: x if isinstance(x, str) else x.get("id"))
def test_scenario_shape(code, sc):
    assert float(sc["until"]) > 0 and float(sc.get("dt", 0.5)) > 0
    sigs = [c["sig"] for c in sc.get("checks", [])] + [r["sig"] for r in sc.get("show", [])]
    assert all(s.startswith(_PREFIX) for s in sigs), sigs
    for c in sc.get("checks", []):
        assert {"eq", "ge", "le"} & set(c), c
        assert set(c) <= {"t", "sig", "eq", "ge", "le"}, c
    if sc.get("chart"):
        assert sc.get("show") and sc.get("note") and sc.get("title")
        assert all(r.get("kind") in ("bit", "num") and r.get("label") for r in sc["show"])


@needs_def
def test_a_wrong_statement_is_caught():
    """Doi 1 gia tri mong doi -> checker phai bao loi, khong duoc im lang cho qua."""
    sc = copy.deepcopy(next(s for s in TD.doc_for("8211")["scenarios"] if s["id"] == "rate_and_hl"))
    for c in sc["checks"]:
        if c["sig"] == "out:SV" and c["t"] == [4, 9.5]:
            c["eq"] = 40
    loi = TD.check_scenario("8211", sc)
    assert len(loi) == 1 and "expected {'eq': 40}" in loi[0]


def test_unknown_signal_kind_is_rejected():
    sc = {"until": 0.5, "set": {"bad:X": 1}}
    with pytest.raises(ValueError):
        TD.run_scenario("8211", sc)


def test_pick_falls_back_to_english():
    assert TD.pick({"en": "A", "vi": ""}, "vi") == "A"
    assert TD.pick({"en": "A", "vi": "B"}, "vi") == "B"
    assert TD.pick(None) == ""


def test_missing_code_has_no_doc():
    assert TD.doc_for("ZZZZ") is None
