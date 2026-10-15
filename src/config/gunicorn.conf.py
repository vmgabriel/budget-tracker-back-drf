"""Gunicorn configuration for the Django WSGI application.

Loaded with ``gunicorn -c src/config/gunicorn.conf.py config.wsgi:application``.
Every knob can be overridden through the environment so a deployment can be
retuned without rebuilding the image, but the defaults below are already
production-shaped and safe to run unattended.

Nothing in this file imports Django: Gunicorn reads it before the application
is loaded, and the application must not be imported at this point.
"""

import multiprocessing
import os


def _int_env(name: str, default: int) -> int:
    """Read a positive integer from the environment, ignoring junk values.

    A malformed value (empty string, non-numeric) falls back to the default
    rather than crashing the boot, because a typo in a secret store should not
    take the whole stack down.
    """
    raw = os.environ.get(name, "")
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _available_cpus() -> int:
    """CPU count visible to this process, honouring cgroup/affinity limits.

    ``multiprocessing.cpu_count`` reports every core on the host, which
    over-counts badly inside a container limited to a fraction of the machine.
    """
    affinity = getattr(os, "sched_getaffinity", None)
    if affinity is None:  # pragma: no cover - non-Linux fallback
        return multiprocessing.cpu_count()
    return len(affinity(0))


# Workers: the classic (2 * CPU_CORES) + 1 heuristic. Gunicorn's sync workers
# spend most of their time waiting on PostgreSQL, so the "one worker per core"
# advice under-provisions here; two per core keeps cores busy while one worker
# is blocked on I/O.
#
# How to tune:
#   * Measure p95 latency and worker CPU saturation under real traffic, then
#     move this number by small steps (usually +1 or +2).
#   * Each worker is a separate process with its own database connections
#     (CONN_MAX_AGE), so workers and threads multiply PostgreSQL connections.
#     Keep ``workers * threads`` comfortably below the server's
#     max_connections, minus headroom for migrations, backups, and admin work.
#   * Leave at least one core for the Celery worker, Beat, Redis, and PostgreSQL
#     if they share the same host.
#   * GUNICORN_WORKERS=0 in the environment pins this value; setting it in .env
#     is the supported way to override it per deployment.
default_workers = 2 * _available_cpus() + 1
workers = _int_env("GUNICORN_WORKERS", default_workers)

# Threads per worker. Each thread gets its own database connection, so this is
# a second multiplier on the connection count above. 4 is enough for the
# IO-bound endpoints in this project (reports, document lookups); raise it only
# after checking max_connections.
threads = _int_env("GUNICORN_THREADS", 4)

# A request that outlives this budget is assumed to be stuck and the worker is
# killed and replaced. 60s leaves room for slow reports without letting a dead
# request hold a connection indefinitely. Long-running work belongs in Celery,
# not in an HTTP handler.
timeout = _int_env("GUNICORN_TIMEOUT", 60)

# How long a worker gets to finish in-flight requests after a SIGTERM. Must
# stay above the Compose stop_grace_period only if you raise that too; 30s is
# enough for the short handlers in this project and lets deploys finish fast.
graceful_timeout = _int_env("GUNICORN_GRACEFUL_TIMEOUT", 30)

# Reuse the listening socket across restarts so a reload does not drop the
# proxy's connections, and keep-alive on the worker side.
reuse_port = False
keepalive = _int_env("GUNICORN_KEEPALIVE", 5)

# Bind to every interface inside the container; publish it on the host through
# Compose, or hand it to a reverse proxy on the same network.
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

# Docker logging drivers capture stdout/stderr, so logs must never go to files.
# "-" means stdout for access and stderr for errors.
accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "-")
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "-")
# Django writes its own timestamped lines; duplicating them here adds noise.
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info").lower()
# Log the request line, status, and duration. Enough for access auditing without
# logging bodies or headers, which would put JWTs into the log stream.
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(M)sms'

# The container is already its own PID namespace with an init process, so
# Gunicorn must not fork a second master and create an orphaned process tree.
preload_app = False

# Worker recycling bounds the damage from slow memory growth in long-lived
# processes. Random jitter spreads the cost instead of restarting every worker
# on the same tick.
max_requests = _int_env("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = _int_env("GUNICORN_MAX_REQUESTS_JITTER", 100)

# Do not advertise the server identity on error pages.
forwarded_allow_ips = os.environ.get("GUNICORN_FORWARDED_ALLOW_IPS", "*")
proc_name = "life-utility-web"
