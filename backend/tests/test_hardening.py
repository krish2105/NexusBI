"""Production-hardening tests: DSN encryption, SSRF guard, read-only verification,
rate limiting, and tenant isolation."""
from app.config import settings
from app.core.connguard import (check_connection, check_host,
                               classify_probe_error, verify_read_only)
from app.core.crypto import decrypt, encrypt
from app.core.ratelimit import RateLimiter


# --- DSN encryption at rest ---
def test_dsn_encryption_roundtrip():
    dsn = "postgresql://user:s3cret@db.example.com:5432/warehouse"
    enc = encrypt(dsn)
    assert enc != dsn
    assert "s3cret" not in enc          # secret not visible in ciphertext
    assert enc.startswith("enc:v1:")
    assert decrypt(enc) == dsn


def test_decrypt_tolerates_plaintext_demo_path():
    # the bundled sqlite demo path is stored as-is (no credentials)
    assert decrypt("sqlite:///x.db") == "sqlite:///x.db"


# --- read-only verification (side-effect-free probe) ---
def test_demo_connection_verified_readonly():
    check = check_connection(settings.demo_target_url)
    assert check.ok and check.is_readonly


def test_pg_role_classifier_accepts_readonly_error():
    # A read-only Postgres role refuses the write with a read-only/permission error.
    for msg in ["cannot execute INSERT in a read-only transaction",
                "permission denied for table _nexus_wcheck_zzz"]:
        c = classify_probe_error(msg)
        assert c.ok and c.is_readonly


def test_pg_role_classifier_rejects_writable_role():
    # A writable role fails only because the probe table is absent -> rejected.
    c = classify_probe_error('relation "_nexus_wcheck_zzz" does not exist')
    assert not c.ok and not c.is_readonly


# --- SSRF / private-host guard ---
def test_ssrf_blocks_localhost_postgres():
    check = check_host("postgresql://u:p@127.0.0.1:5432/db")
    assert not check.ok


def test_ssrf_blocks_cloud_metadata():
    check = check_host("postgresql://u:p@169.254.169.254:5432/db")
    assert not check.ok


def test_sqlite_demo_host_allowed():
    assert check_host("sqlite:///demo.db").ok


# --- rate limiter ---
def test_rate_limiter_blocks_after_limit():
    rl = RateLimiter(limit=3, window_s=60)
    t = 1000.0
    assert all(rl.allow("ip", now=t + i * 0.1)[0] for i in range(3))
    ok, retry = rl.allow("ip", now=t + 0.4)
    assert not ok and retry > 0


def test_rate_limiter_window_resets():
    rl = RateLimiter(limit=1, window_s=10)
    assert rl.allow("ip", now=0.0)[0]
    assert not rl.allow("ip", now=1.0)[0]
    assert rl.allow("ip", now=11.0)[0]   # window elapsed


# --- auth enforcement + tenant isolation (demo stays open) ---
def test_auth_required_for_custom_connection(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(settings, "require_auth", True)
    with TestClient(app) as c:
        # creating a connection now requires auth
        assert c.post("/connections", json={"name": "x"}).status_code == 401
        # but the bundled demo query stays open to the public
        r = c.post("/query/run", json={"question": "Total merchandise revenue"})
        assert r.status_code == 200 and not r.json()["blocked"]
