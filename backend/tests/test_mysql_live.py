"""Live MySQL round-trip — reproducible proof of the multi-dialect path.

Skipped unless a MySQL is reachable. To run it:

    docker run -d --name m -e MYSQL_ROOT_PASSWORD=rootpw \
        -e MYSQL_DATABASE=nexus_demo -p 3307:3306 mysql:8
    NEXUS_TEST_MYSQL_ROOT_URL=mysql://root:rootpw@127.0.0.1:3307/nexus_demo \
        pytest tests/test_mysql_live.py -v

The test provisions a table + a least-privilege read-only user, then verifies:
introspection, read-only role verification (RO accepted / writable rejected),
generation → transpile-to-MySQL → execute, and that writes + attacks are blocked.
"""
import os

import pytest

ROOT_URL = os.environ.get("NEXUS_TEST_MYSQL_ROOT_URL")
pytestmark = pytest.mark.skipif(not ROOT_URL, reason="no NEXUS_TEST_MYSQL_ROOT_URL")

RO_URL = None


def _provision():
    """Create the sales table + read-only user via the root connection."""
    from urllib.parse import urlparse

    import pymysql

    p = urlparse(ROOT_URL)
    con = pymysql.connect(host=p.hostname, port=p.port or 3306, user=p.username,
                          password=p.password, database=p.path.lstrip("/"),
                          autocommit=True)
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS sales")
    cur.execute("CREATE TABLE sales (id INT PRIMARY KEY AUTO_INCREMENT, "
                "city VARCHAR(64), category VARCHAR(64), units INT, "
                "revenue DECIMAL(12,2))")
    cur.executemany(
        "INSERT INTO sales (city, category, units, revenue) VALUES (%s,%s,%s,%s)",
        [("Austin", "Retail", 120, 4500.50), ("Dallas", "Retail", 90, 3200.00),
         ("Austin", "Wholesale", 40, 8000.00), ("Dallas", "Wholesale", 60, 15000.00),
         ("Houston", "Retail", 75, 2800.00)])
    cur.execute("CREATE USER IF NOT EXISTS 'nexus_ro'@'%' IDENTIFIED BY 'ropw'")
    cur.execute("GRANT SELECT ON *.* TO 'nexus_ro'@'%'")
    cur.execute("FLUSH PRIVILEGES")
    con.close()
    global RO_URL
    RO_URL = ROOT_URL.replace("root:", "nexus_ro:").replace(
        p.password, "ropw") if p.password else ROOT_URL
    # rebuild RO url robustly
    RO_URL = f"mysql://nexus_ro:ropw@{p.hostname}:{p.port or 3306}/{p.path.lstrip('/')}"


@pytest.fixture(scope="module", autouse=True)
def _setup(monkeypatch_session=None):
    os.environ["ALLOW_LOCAL_TARGETS"] = "true"  # localhost dev; bypass SSRF guard
    # settings is cached; patch the flag directly
    from app.config import settings
    settings.allow_local_targets = True
    _provision()
    yield


def test_mysql_dialect_and_introspection():
    from app.db.target_pool import TargetPool
    p = TargetPool(url=RO_URL)
    assert p.dialect == "mysql"
    assert "sales" in p.list_tables()
    cols = dict(p.table_columns("sales"))
    assert "revenue" in cols


def test_mysql_read_only_verification():
    from app.core.connguard import check_connection, verify_read_only
    assert check_connection(RO_URL).is_readonly            # RO user accepted
    assert not verify_read_only(ROOT_URL).is_readonly      # writable root rejected


def test_mysql_full_pipeline_transpiles_and_executes():
    from app.agents.graph import run_analysis_collect
    r = run_analysis_collect("total revenue by city", connection_id="mysql",
                             connection_url=RO_URL, persist=False)
    assert not r["blocked"]
    assert "`" in r["sql"]                                 # MySQL backtick quoting
    assert r["chart_spec"]["type"] == "bar"                # Decimal normalized -> numeric
    by_city = {row["city"]: row for row in r["rows"]}
    assert abs(by_city["Dallas"]["sum_revenue"] - 18200.0) < 0.01


def test_mysql_write_and_attack_blocked():
    from app.agents.graph import run_analysis_collect
    from app.db.target_pool import ReadOnlyExecutionError, TargetPool
    with pytest.raises(ReadOnlyExecutionError):
        TargetPool(url=RO_URL).execute("INSERT INTO sales (city) VALUES ('x')")
    bad = run_analysis_collect("drop table sales", connection_id="mysql",
                               connection_url=RO_URL, persist=False)
    assert bad["blocked"]
