"""Test helper format tampilan (app/format.py): murni, tanpa streamlit."""

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import format as fmt


def test_bersihkan_html_buang_tag_img():
    mentah = (
        '<img src="https://akcdn.detik.net.id/visual/2024/11/26/x.jpeg?w=360&amp;q=90" />'
        " WNA Malaysia meminta agar tidak ada kriminalisasi."
    )
    bersih = fmt.bersihkan_html(mentah)
    assert "<img" not in bersih and "&amp;" not in bersih
    assert bersih == "WNA Malaysia meminta agar tidak ada kriminalisasi."


def test_bersihkan_html_kosong():
    assert fmt.bersihkan_html(None) == ""
    assert fmt.bersihkan_html("") == ""


def test_format_wita():
    # 04:10 UTC -> 12:10 WITA
    assert fmt.format_wita("2026-09-25T04:10:00+00:00") == "25 Sep 2026, 12:10 WITA"
    assert fmt.format_wita("2026-09-25T04:10:00Z") == "25 Sep 2026, 12:10 WITA"
    assert fmt.format_wita(None) == "-"
    assert fmt.format_wita("bukan-tanggal") == "-"


def test_waktu_relatif():
    now = datetime.datetime(2026, 9, 25, 4, 0, tzinfo=datetime.timezone.utc)
    assert fmt.waktu_relatif("2026-09-25T03:59:30+00:00", now) == "baru saja"
    assert fmt.waktu_relatif("2026-09-25T03:55:00+00:00", now) == "5 menit lalu"
    assert fmt.waktu_relatif("2026-09-25T02:00:00+00:00", now) == "2 jam lalu"
    assert fmt.waktu_relatif("2026-09-23T04:00:00+00:00", now) == "2 hari lalu"
    assert fmt.waktu_relatif(None, now) == "-"
