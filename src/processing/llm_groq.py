"""Ringkasan AI via API OpenAI-compatible (Groq / Top Tools AI).

Sengaja hanya pakai stdlib (urllib) agar jalan tanpa dependensi tambahan.
Provider dipilih via env:
  TOPTOOLS_API_KEY (+ opsional TOPTOOLS_API_URL, TOPTOOLS_MODEL)
  GROQ_API_KEY (+ opsional GROQ_MODEL) — fallback / kompatibilitas laptop.

Best-effort: semua kegagalan (tanpa key, timeout, 429/kuota, respons aneh)
mengembalikan None — pemanggil WAJIB fallback ke ringkasan ekstraktif,
bukan retry berulang.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request

log = logging.getLogger("media_monitor")


class RateLimitError(Exception):
    """API mengembalikan HTTP 429 (rate limit). Layak dicoba lagi
    setelah menunggu — berbeda dengan gagal lain (401/timeout) yang
    langsung mengembalikan None."""

API_URL_GROQ = "https://api.groq.com/openai/v1/chat/completions"
API_URL_TOPTOOLS = "https://top-tools-ai.com/v1/chat/completions"
MODEL_DEFAULT = "qwen/qwen3.8-27b"
MODEL_DEFAULT_TOPTOOLS = "top-tools-ai"  # model gratis 10M token/hari
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

PROMPT_TEMPLATE = (
    "Ringkas berita Indonesia berikut dalam 3-4 kalimat Bahasa Indonesia "
    "yang padat dan informatif. Hanya tulis ringkasannya, tanpa pembuka.\n\n"
    "Judul: {judul}\n\nIsi:\n{isi}"
)

AI_ROUTE = "/home/hatch/workspace/scripts/ai_route.py"
GATEWAY_KEY_FILE = "/home/hatch/.9router/.gateway-key"


def _ringkasan_valid(teks):
    if teks is None or teks.strip() == "":
        return None

    low = teks.lower()
    bocor_patterns = [
        "thinking process", "analyze the request", "the user wants",
        "summarize the provided", "write only the", "constraint:",
        "here's a summary of", "here is a summary of", "i need to summarize",
        "let me summarize"
    ]

    if any(pattern in low for pattern in bocor_patterns):
        return None

    if re.match(r'^\s*1\.\s+\*\*', teks):
        return None

    teks = re.sub(r'(?i)^ringkasan\s*:\s*', '', teks).strip()

    if len(teks) < 40:
        return None

    return teks.strip()


def ringkas_via_9router(
    judul: str,
    isi: str,
    max_tokens: int = 300,
    timeout: int = 600,
) -> tuple[str | None, str | None]:
    """Ringkasan via 9Router (ai_route.py) — rantai fallback penuh model gratis.

    Kembalikan (teks_ringkasan, nama_model) atau (None, None) bila semua gagal.
    0-token Ruby: hanya subprocess ke script lokal + HTTP ke gateway lokal.
    """
    import os
    import subprocess
    import sys
    import tempfile

    if not (isi or "").strip():
        return None, None
    if not os.path.exists(GATEWAY_KEY_FILE):
        log.warning("ringkas_via_9router: gateway key tidak ada, skip")
        return None, None
    prompt = PROMPT_TEMPLATE.format(
        judul=(judul or "").strip()[:300],
        isi=isi.strip()[:6000],
    )
    prompt_path = out_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         dir="/tmp") as pf:
            pf.write(prompt)
            prompt_path = pf.name
        out_path = prompt_path + ".out"
        r = subprocess.run(
            [sys.executable, AI_ROUTE, "--prompt-file", prompt_path,
             "--tier", "ringan", "--max-tokens", str(max_tokens),
             "--out", out_path],
            capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            log.warning("ringkas_via_9router: ai_route gagal: %s",
                        (r.stderr or "")[-200:])
            return None, None
        with open(out_path, encoding="utf-8") as f:
            teks = f.read().strip()
        model = None
        for line in (r.stderr or "").splitlines():
            if "OK via" in line:
                model = line.split("OK via")[-1].strip()
        return _ringkasan_valid(teks), model
    except Exception as exc:
        log.warning("ringkas_via_9router gagal: %s", exc)
        return None, None
    finally:
        import os as _os
        for p in (prompt_path, out_path):
            if p:
                try:
                    _os.unlink(p)
                except OSError:
                    pass


def ringkas_artikel(
    judul: str,
    isi: str,
    api_key: str,
    model: str = MODEL_DEFAULT,
    max_tokens: int = 300,
    timeout: int = 60,
    api_url: str = API_URL_GROQ,
) -> str | None:
    """Minta ringkasan ke API OpenAI-compatible. Kembalikan teks atau None."""
    if not api_key or not (isi or "").strip():
        return None
    prompt = PROMPT_TEMPLATE.format(
        judul=(judul or "").strip()[:300],
        isi=isi.strip()[:6000],
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")
    req = urllib.request.Request(
        api_url, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}",
                 "User-Agent": UA},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        teks = (data["choices"][0]["message"]["content"] or "").strip()
        return teks or None
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimitError(f"HTTP 429: {e.reason}")
        log.warning("ringkas_artikel gagal: HTTP %s", e.code)
        return None
    except Exception as exc:  # timeout, JSON rusak, ...
        log.warning("ringkas_artikel gagal: %s", exc)
        return None
