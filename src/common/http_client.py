"""HTTP client tunggal untuk seluruh proyek.

Menyediakan retry otomatis, timeout, dan user-agent yang konsisten.
Semua pengambilan HTTP (feed RSS maupun resolusi redirect) lewat sini.
"""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HttpClient:
    def __init__(
        self,
        user_agent: str,
        timeout_seconds: int = 20,
        max_retries: int = 3,
    ) -> None:
        self.timeout = timeout_seconds
        retry = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session = requests.Session()
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({"User-Agent": user_agent})

    def get(self, url: str) -> requests.Response:
        """GET dengan retry + raise untuk status error."""
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp

    def resolve_final_url(self, url: str) -> str:
        """Ikuti redirect sampai dapat URL artikel asli.

        Dipakai untuk link Google News RSS yang mengarah ke news.google.com.
        Hanya header yang diunduh (stream), isi halaman tidak diambil.
        Gagal resolve -> kembalikan URL apa adanya, bukan error.
        """
        try:
            resp = self.session.get(
                url, timeout=self.timeout, stream=True, allow_redirects=True
            )
            final = resp.url
            resp.close()
            return final or url
        except requests.RequestException:
            return url
