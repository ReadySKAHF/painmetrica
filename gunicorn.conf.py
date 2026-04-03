import multiprocessing

# ─── Bind ───────────────────────────────────────────────────────────────────
# Windows не поддерживает unix sockets — используем TCP
bind = '127.0.0.1:8000'

# ─── Workers ────────────────────────────────────────────────────────────────
# На Windows используем gthread (fork недоступен)
worker_class = 'gthread'
workers = 2
threads = 4

# ─── Timeouts ───────────────────────────────────────────────────────────────
timeout = 30
graceful_timeout = 30
keepalive = 5

# ─── Логи ───────────────────────────────────────────────────────────────────
accesslog = 'logs/gunicorn_access.log'
errorlog = 'logs/gunicorn_error.log'
loglevel = 'warning'

# ─── Безопасность ───────────────────────────────────────────────────────────
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
