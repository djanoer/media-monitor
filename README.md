# Media Monitor

Dashboard Streamlit untuk memantau isu-isu yang ramai diberitakan 10 media nasional Indonesia.

Lihat `ROADMAP.md` untuk rencana fase kerja, keputusan desain, dan hasil riset feed RSS.

## Menjalankan scheduler (Fase 1)

Dari root proyek dengan venv aktif:

```bash
# satu siklus fetch lalu keluar (untuk testing / cron)
.venv/bin/python run_scheduler.py --once

# jalan terus, fetch tiap 1 jam (APScheduler in-process)
.venv/bin/python run_scheduler.py
```

Log: `logs/fetch.log`. Database: `data/media_monitor.db`.
Menjalankan test: `.venv/bin/python -m pytest tests/ -q`
