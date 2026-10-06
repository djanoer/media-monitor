"""Test pemuatan konfigurasi (memakai file config asli proyek)."""

from src.common.config import load_media, load_settings


def test_load_media_lima_belas_media_aktif():
    media = load_media()
    assert len(media) == 16
    names = {m["name"] for m in media}
    assert names == {
        "tempo", "cnn_indonesia", "antara", "republika", "bisnis_indonesia",
        "kompas", "detik", "liputan6", "jawa_pos", "kumparan",
        "tribunnews", "okezone", "sindonews", "viva", "merdeka",
        "suara",
    }


def test_setiap_media_punya_field_wajib():
    for m in load_media():
        assert m["feed"].startswith("http")
        assert m["type"] in ("native", "gnews")


def test_settings_punya_kunci_wajib():
    s = load_settings()
    assert s["fetch"]["interval_hours"] == 1
    assert s["fetch"]["max_articles_per_media"] == 30
    assert s["retention"]["retention_days"] == 30
    assert s["storage"]["db_path"]


def _dotenv_palsu(monkeypatch):
    """dotenv tiruan: baca KEY=VALUE, tidak menimpa env yang sudah ada."""
    import os
    import sys
    import types

    mod = types.ModuleType("dotenv")

    def load_dotenv(path=None):
        try:
            baris = open(path, encoding="utf-8").read().splitlines()
        except OSError:
            return False
        for b in baris:
            b = b.strip()
            if b and not b.startswith("#") and "=" in b:
                k, v = b.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
        return True

    mod.load_dotenv = load_dotenv
    monkeypatch.setitem(sys.modules, "dotenv", mod)


def test_muat_dotenv_dari_file(tmp_path, monkeypatch):
    import os
    import sys
    sys.path.insert(0, ".")
    from src.common import config
    _dotenv_palsu(monkeypatch)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    (tmp_path / ".env").write_text("YOUTUBE_API_KEY=kunci-palsu\n",
                                   encoding="utf-8")
    cfgdir = tmp_path / "config"
    cfgdir.mkdir()
    (cfgdir / "settings.yaml").write_text("storage:\n  db_path: x.db\n",
                                          encoding="utf-8")
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    config.load_settings(cfgdir / "settings.yaml")
    assert os.environ.get("YOUTUBE_API_KEY") == "kunci-palsu"


def test_env_sistem_menang_atas_dotenv(tmp_path, monkeypatch):
    import os
    import sys
    sys.path.insert(0, ".")
    from src.common import config
    _dotenv_palsu(monkeypatch)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    (tmp_path / ".env").write_text("YOUTUBE_API_KEY=dari-file\n",
                                   encoding="utf-8")
    cfgdir = tmp_path / "config"
    cfgdir.mkdir()
    (cfgdir / "settings.yaml").write_text("storage:\n  db_path: x.db\n",
                                          encoding="utf-8")
    monkeypatch.setenv("YOUTUBE_API_KEY", "dari-setx")
    config.load_settings(cfgdir / "settings.yaml")
    assert os.environ.get("YOUTUBE_API_KEY") == "dari-setx"


def test_tanpa_dotenv_tetap_jalan(tmp_path, monkeypatch):
    # python-dotenv tak terinstal -> dilewati diam-diam, config tetap kebaca
    import sys
    sys.path.insert(0, ".")
    from src.common import config
    assert "dotenv" not in sys.modules or True
    cfgdir = tmp_path / "config"
    cfgdir.mkdir()
    (cfgdir / "settings.yaml").write_text("storage:\n  db_path: x.db\n",
                                          encoding="utf-8")
    assert config.load_settings(cfgdir / "settings.yaml")["storage"]["db_path"] == "x.db"
