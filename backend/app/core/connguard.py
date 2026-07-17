"""Connection-time defenses for the target database.

Two checks run before any user-supplied connection is accepted:

1. SSRF / private-host guard — a connection string is an SSRF vector. We block
   DSNs whose host resolves to loopback, private, link-local, or cloud-metadata
   ranges unless ``ALLOW_LOCAL_TARGETS`` is set (dev). The bundled SQLite demo
   has no network host and is always allowed.

2. Read-only verification — we don't take the caller's word that a DB is
   read-only. We probe with a side-effect-free write attempt against a
   non-existent table: a read-only role fails with a *read-only / permission*
   error, while a writable role fails with a *relation-does-not-exist* error.
   We accept the connection only when the former is observed.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import settings
from app.db.target_pool import ReadOnlyExecutionError, TargetPool

# NB: the probe table name must NOT contain the substring "readonly", or a
# "relation ... does not exist" error would falsely match the read-only regex.
_PROBE = "INSERT INTO _nexus_wcheck_zzz (x) VALUES (1)"
_READONLY_SIGNS = re.compile(
    r"read[- ]?only|permission denied|not allowed|cannot execute .* in a read-only",
    re.I)
_MISSING_SIGNS = re.compile(
    r"no such table|does not exist|relation .* does not exist|unknown", re.I)


@dataclass
class ConnCheck:
    ok: bool
    reason: str
    is_readonly: bool = False


def _host_is_private(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True  # unresolvable -> treat as unsafe
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast
                or str(ip) == "169.254.169.254"):  # cloud metadata
            return True
    return False


def check_host(url: str) -> ConnCheck:
    if url.startswith("sqlite"):
        return ConnCheck(True, "sqlite (no network host)")
    host = urlparse(url).hostname or ""
    if not host:
        return ConnCheck(False, "no host in connection string")
    if getattr(settings, "allow_local_targets", False):
        return ConnCheck(True, "local targets allowed (dev)")
    if _host_is_private(host):
        return ConnCheck(False, f"host '{host}' resolves to a private/loopback/"
                                "metadata address and is blocked (SSRF defense)")
    return ConnCheck(True, f"host '{host}' ok")


def classify_probe_error(msg: str) -> ConnCheck:
    """Interpret the error from a write probe run on the caller's *raw* role.

    A read-only role fails with a read-only/permission error; a writable role
    fails only because the probe table is absent. We fail closed on anything
    ambiguous."""
    if _READONLY_SIGNS.search(msg):
        return ConnCheck(True, "verified read-only role (write refused)",
                         is_readonly=True)
    if _MISSING_SIGNS.search(msg):
        return ConnCheck(False, "role is writable (probe failed only because the "
                                "table is absent) — rejected; grant a read-only role")
    return ConnCheck(False, f"could not confirm read-only role: {msg[:120]}")


def verify_read_only(url: str) -> ConnCheck:
    # Must be usable at all (through our normal, read-only-enforcing pool).
    pool = TargetPool(url=url)
    try:
        pool.execute("SELECT 1 AS ok LIMIT 1")
    except Exception as e:  # noqa: BLE001
        return ConnCheck(False, f"could not query target: {str(e)[:120]}")

    if pool.dialect == "sqlite":
        # SQLite read-only is enforced by the pool itself (mode=ro + query_only);
        # our access cannot write regardless of file permissions (Layer 1).
        return ConnCheck(True, "read-only enforced by pool (sqlite mode=ro)",
                         is_readonly=True)

    # Postgres: probe the caller's ROLE directly (raw connection, no forced
    # read-only transaction) so a writable role is detected and rejected.
    return _verify_pg_role(url)


def _verify_pg_role(url: str) -> ConnCheck:  # pragma: no cover - needs live Postgres
    try:
        import psycopg2

        con = psycopg2.connect(url)
        con.autocommit = True
        try:
            con.cursor().execute(_PROBE)
            return ConnCheck(False, "role accepted a write — NOT read-only, rejected")
        except Exception as e:  # noqa: BLE001
            return classify_probe_error(str(e))
        finally:
            con.close()
    except Exception as e:  # noqa: BLE001
        return ConnCheck(False, f"could not connect to verify role: {str(e)[:120]}")


def check_connection(url: str) -> ConnCheck:
    host = check_host(url)
    if not host.ok:
        return host
    return verify_read_only(url)
