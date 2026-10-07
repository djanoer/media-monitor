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
