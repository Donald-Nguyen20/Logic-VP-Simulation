# -*- coding: utf-8 -*-
"""Model VUA SUY NGHI VUA TRA LOI: phan suy nghi khong duoc thanh cau tra loi.

Nemotron-3, deepseek-r1, o-series nhap nhap truoc khi viet. Khi het cho giua chung,
may chu do luon phan nhap nhap do sang o 'content'. Neu app cu the ma hien thi thi
nguoi dung doc duoc dan bai tieng Anh cua model - dung cai loi da gap that."""
import pytest

from core import llm_client as LC


def _luot(content="", reasoning="", tool_calls=None, finish="stop"):
    """Mot cau tra loi JSON cua may chu, rut gon con dung phan app doc toi."""
    msg = {"role": "assistant", "content": content}
    if reasoning:
        msg["reasoning_content"] = reasoning
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg, "finish_reason": finish}]}


_GOI = [{"id": "c1", "function": {"name": "get_source",
                                  "arguments": '{"name": "GEN FREQ QB"}'}}]

# Nguyen van doan da gap: content dai y het reasoning, deu 626 ky tu.
_NHAP = "We need to parse the context. We need to list every line ending in '...'."


def test_suy_nghi_do_sang_content_thi_bo():
    assert LC._chu_that({"content": _NHAP, "reasoning_content": _NHAP}) == ""


def test_suy_nghi_bi_cat_ngan_hon_cung_bo():
    """Co luc content la phan suy nghi da bi cat bot - van la suy nghi."""
    assert LC._chu_that({"content": _NHAP[:40], "reasoning_content": _NHAP}) == ""


def test_cau_tra_loi_that_van_giu_du_co_suy_nghi():
    m = {"content": "GEN I/S bao may phat da hoa luoi.", "reasoning_content": _NHAP}
    assert LC._chu_that(m) == "GEN I/S bao may phat da hoa luoi."


def test_model_khong_suy_nghi_khong_bi_dung_toi():
    """Groq/gpt-oss khong co truong reasoning_content - duong cu phai nguyen ven."""
    assert LC._chu_that({"content": _NHAP}) == _NHAP


@pytest.fixture
def khach(monkeypatch):
    """Client that, nhung moi lan goi may chu deu lay tu danh sach dat san."""
    def lam(cac_luot):
        c = LC.OpenAICompatibleClient("k", "http://x", "m")
        nhat_ky = []

        def gia(messages, tools, on_event=None, max_tokens=0):
            nhat_ky.append({"co_cong_cu": bool(tools), "cho": max_tokens})
            return cac_luot[len(nhat_ky) - 1]

        monkeypatch.setattr(c, "_post", gia)
        monkeypatch.setattr(c, "_run_tools",
                            lambda calls, ev: [(i, n, "ket qua tra cuu") for i, n, _ in calls])
        return c, nhat_ky
    return lam


def test_het_cho_khi_dang_nghi_thi_hoi_lai_MA_VAN_GIU_CONG_CU(khach):
    """Loi that: het cho luc dang nghi -> app hoi lai nhung bo cong cu -> model khong
    tra cuu duoc nua nen ngoi ke lai cac buoc dinh lam. Phai giu cong cu."""
    c, nk = khach([
        _luot(content=_NHAP, reasoning=_NHAP, finish="length"),   # het cho giua chung
        _luot(tool_calls=_GOI),                                   # hoi lai: goi cong cu
        _luot(content="GEN I/S len khi may phat da hoa luoi.", reasoning="nghi tiep"),
    ])
    assert c.ask("sys", "hoi") == "GEN I/S len khi may phat da hoa luoi."
    assert nk[1]["co_cong_cu"] is True, "lan hoi lai phai con cong cu"
    assert nk[1]["cho"] == 0, "lan hoi lai phai duoc cho rong (0 = mac dinh 4000)"


def test_model_thuong_bi_cat_thi_van_hoi_lai_khong_cong_cu(khach):
    """Duong cu cho model khong suy nghi: cat giua chung la vi cau tra loi dai."""
    c, nk = khach([
        _luot(content="dang viet do dang", finish="length"),
        _luot(content="cau tra loi day du"),
    ])
    assert c.ask("sys", "hoi") == "cau tra loi day du"
    assert nk[1]["co_cong_cu"] is False


def test_biet_model_suy_nghi_thi_luot_sau_noi_cho_ra(khach):
    """Hoc mot lan: cac luot tra cuu sau do khong duoc bop con 1200 token nua."""
    c, nk = khach([
        _luot(reasoning="nghi", tool_calls=_GOI),
        _luot(content="xong"),
    ])
    assert c.ask("sys", "hoi") == "xong"
    assert nk[0]["cho"] == LC._MAX_TOKENS_TRACUU
    assert nk[1]["cho"] == LC._MAX_TOKENS_SUY_NGHI


def test_luot_tra_cuu_cua_model_thuong_van_bop_nho(khach):
    c, nk = khach([_luot(tool_calls=_GOI), _luot(content="xong")])
    assert c.ask("sys", "hoi") == "xong"
    assert [x["cho"] for x in nk] == [LC._MAX_TOKENS_TRACUU, LC._MAX_TOKENS_TRACUU]
