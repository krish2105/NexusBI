"""Bring-your-own-CSV: upload -> instant warehouse -> grounded zero-key query."""
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app

CSV = (
    "product,region,units,revenue\n"
    "Widget,North,10,100.0\n"
    "Widget,South,5,50.0\n"
    "Gadget,North,8,240.0\n"
    "Gadget,South,12,360.0\n"
    "Gizmo,North,3,90.0\n"
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_upload_then_query_end_to_end(client):
    up = client.post(
        "/connections/upload",
        files={"files": ("sales.csv", io.BytesIO(CSV.encode()), "text/csv")},
        data={"name": "Sales upload"},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    cid = body["connection_id"]
    assert body["tables"][0]["table"] == "sales"
    assert body["tables"][0]["rows"] == 5
    assert body["is_readonly"]

    # Query the uploaded data with the zero-key generic synthesizer.
    r = client.post("/query/run",
                    json={"question": "total revenue by region",
                          "connection_id": cid}).json()
    assert not r["blocked"]
    assert r["chart_spec"]["type"] in ("bar", "grouped_bar")
    by_region = {row["region"]: row for row in r["rows"]}
    assert set(by_region) == {"North", "South"}
    north = by_region["North"]
    val = north.get("sum_revenue") or list(north.values())[1]
    assert abs(val - 430.0) < 0.01     # 100 + 240 + 90

    # A malicious question is still blocked on uploaded data.
    bad = client.post("/query/run",
                      json={"question": "drop table sales", "connection_id": cid}).json()
    assert bad["blocked"]


def test_upload_rejects_non_csv(client):
    r = client.post(
        "/connections/upload",
        files={"files": ("evil.exe", io.BytesIO(b"MZ..."), "application/octet-stream")},
        data={"name": "bad"},
    )
    assert r.status_code == 400
