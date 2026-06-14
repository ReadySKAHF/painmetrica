import multiprocessing
import os

# ─── Bind ────────────────────────────────────────────────────────────────────
# Unix socket для production (Linux), TCP для Windows dev
if os.name == 'nt':
    bind = '127.0.0.1:8000'
    worker_class = 'gthread'
    threads = 4
else:
    bind = 'unix:/run/painmetrica/gunicorn.sock'
    worker_class = 'sync'
    threads = 1

# ─── Workers ─────────────────────────────────────────────────────────────────
workers = min(multiprocessing.cpu_count() * 2 + 1, 9)

# ─── Timeouts ────────────────────────────────────────────────────────────────
timeout = 30
graceful_timeout = 30
keepalive = 5

# ─── Логи ────────────────────────────────────────────────────────────────────
accesslog = 'logs/gunicorn_access.log'
errorlog = 'logs/gunicorn_error.log'
loglevel = 'warning'

# ─── Безопасность ────────────────────────────────────────────────────────────
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
