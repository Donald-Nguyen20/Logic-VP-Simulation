# -*- coding: utf-8 -*-
"""Do song chet model NVIDIA: cai gi la CHET, cai gi phai giu lai.

Bo sai o day ton kem theo ca hai chieu: bo nham mot model dang chay thi nguoi dung
mat cho chon, con giu lai mot model da khai tu thi ho chon vao roi lai bao loi."""
import pytest

from core import llm_nvidia as NV


class _Tra(object):
    """Cau tra loi HTTP gia - chi can dung hai thu ma do_mot nhin toi."""

    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


@pytest.fixture
def gia(monkeypatch):
    """Thay cho lan goi mang that bang mot ma loi dat san."""
    def dat(status_code, text=""):
        monkeypatch.setattr(NV.requests, "post",
                            lambda *a, **k: _Tra(status_code, text))
    return dat


# NVIDIA bao model het vong doi bang 410 kem han ngay thang:
#   {"status":410,"title":"Gone","detail":"The model '...' has reached its end of
#    life on 2026-09-14T08:00:00Z and is no longer available."}
_HET_DOI = ('{"type":"about:blank","title":"Gone","status":410,"detail":"The model '
            "'deepseek-ai/deepseek-v4-pro-0813' has reached its end of life on "
            '2026-09-14T08:00:00Z and is no longer available."}')


def test_410_la_chet(gia):
    gia(410, _HET_DOI)
    assert NV.do_mot("nvapi-x", "deepseek-ai/deepseek-v4-pro-0813") == NV.CHET


def test_404_van_la_chet(gia):
    gia(404, "Function 'abc' Not found for account 'xyz'")
    assert NV.do_mot("nvapi-x", "01-ai/yi-large") == NV.CHET


def test_model_chet_bi_bo_khoi_danh_sach():
    """CHET thi bien han khoi o chon; CHUA_RO thi con, nhung xep sau."""
    ra = NV._xep({"a/song": NV.SONG, "b/het-doi": NV.CHET, "c/chua-ro": NV.CHUA_RO})
    assert ra == ["a/song", "c/chua-ro"]


@pytest.mark.parametrize("ma", [429, 500, 502, 503])
def test_loi_tam_thoi_khong_duoc_coi_la_chet(gia, ma):
    """May chu ban hay bi chan la chuyen nhat thoi - bo model that la mat oan."""
    gia(ma, "server busy")
    assert NV.do_mot("nvapi-x", "moonshotai/kimi-k2") == NV.CHUA_RO


def test_tu_choi_cong_cu_van_la_con_song(gia):
    gia(400, "this model does not support tools")
    assert NV.do_mot("nvapi-x", "x/y") == NV.SONG_KHONG_CONG_CU
