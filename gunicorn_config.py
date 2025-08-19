# gunicorn_config.py
import os
import multiprocessing

# Server socket - เปลี่ยนเป็น Unix socket
bind = "unix:/tmp/aicamera.sock"  # เปลี่ยนจาก "0.0.0.0:8080"
backlog = 2048

# Worker processes - Thread workers for camera access
workers = 1  # Single process with multiple threads
worker_class = "gthread"  # Use thread workers instead of process workers
threads = 4  # Number of threads per worker
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "/workspace/logs/gunicorn_access.log"
errorlog = "/workspace/logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "aicamera_v1.3"

# Timeout settings - Increased for camera operations
timeout = 60  # Increased from 30 for camera operations
keepalive = 2

# The app path - using wsgi.py for better WSGI compatibility
# REMOVED: app = "v1_3.src.wsgi:app"  # This conflicts with command line

# Preload app for better performance (DISABLED for camera safety)
preload_app = False

# Single worker mode - master process handles requests directly
# This prevents multiple processes from accessing camera hardware
daemon = False

# User and group (will be set by systemd)
# user = "camuser"
# group = "camuser"

# Environment variables
raw_env = [
    "FLASK_ENV=production",
    "FLASK_APP=v1_3.src.wsgi:app"
]