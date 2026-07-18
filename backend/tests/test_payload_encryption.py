"""Phase 3 legal — query result payloads (which cache row data / PII) are
encrypted at rest, and legacy plaintext rows still load."""
import json
import sqlite3
import tempfile

import pytest

import app.db.app_store as app_store
from app.db.app_store import AppStore


@pytest.fixture()
def store_and_path():
    path = tempfile.mktemp(suffix=".db")
    yield AppStore(url=f"sqlite:///{path}"), path


def test_payload_is_encrypted_at_rest(store_and_path):
    store, path = store_and_path
    pii = {"columns": ["email", "spend"],
           "rows": [{"email": "jane@doe.com", "spend": 4200}]}
    qid = store.save_query("demo", "top spender?", "SELECT 1", "HIGH", [],
                           {"row_count": 1}, pii)

    raw = sqlite3.connect(path).execute(
        "SELECT payload FROM queries WHERE id=?", (qid,)).fetchone()[0]
    assert raw.startswith("enc:v1:")          # stored encrypted
    assert "jane@doe.com" not in raw          # PII not in plaintext

    assert store.get_query(qid)["payload"] == pii   # decrypts transparently


def test_legacy_plaintext_payload_still_loads(store_and_path):
    store, path = store_and_path
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO queries(id,connection_id,question,payload,created_at) "
        "VALUES('legacy','demo','q',?,0)", (json.dumps({"rows": [{"x": 1}]}),))
    con.commit()
    assert store.get_query("legacy")["payload"] == {"rows": [{"x": 1}]}


def test_conversation_turns_decrypt_payload(store_and_path):
    store, _ = store_and_path
    conv = store.create_conversation("demo")["id"]
    secret = {"rows": [{"ssn": "000-00-1234"}]}
    store.save_query("demo", "q", "SELECT 1", "HIGH", [], {}, secret,
                     conversation_id=conv, turn_index=0)
    turns = store.list_turns(conv)
    assert turns[0]["payload"] == secret       # threads see decrypted payloads
