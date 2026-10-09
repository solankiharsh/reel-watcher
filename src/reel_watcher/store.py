"""Durable local library. Connections are short-lived and safe across worker threads."""

from contextlib import contextmanager
import json
import sqlite3
import uuid
from pathlib import Path


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "library.sqlite3"
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, source_key TEXT UNIQUE, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS documents (kind TEXT, id TEXT, data TEXT NOT NULL, PRIMARY KEY(kind,id));
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def items(self):
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute("SELECT data FROM items ORDER BY rowid DESC")
            ]

    def get(self, item_id):
        with self.connect() as db:
            row = db.execute("SELECT data FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise KeyError(item_id)
        return json.loads(row[0])

    def add(self, source_key, **fields):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM items WHERE source_key=?", (source_key,)).fetchone()
            if row:
                item = json.loads(row[0])
                item["collections"] = sorted(
                    set(item["collections"] + fields.get("collections", []))
                )
                db.execute("UPDATE items SET data=? WHERE id=?", (json.dumps(item), item["id"]))
                return item
            item = dict(
                id=uuid.uuid4().hex,
                url=None,
                title="Untitled reel",
                collections=[],
                status="queued",
                error=None,
                media=None,
                study=None,
                post={},
            )
            item.update(fields)
            db.execute(
                "INSERT INTO items VALUES (?,?,?)", (item["id"], source_key, json.dumps(item))
            )
            return item

    def save(self, item):
        with self.connect() as db:
            db.execute("UPDATE items SET data=? WHERE id=?", (json.dumps(item), item["id"]))
        return item

    def put_document(self, kind, doc_id, data):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO documents VALUES (?,?,?)", (kind, doc_id, json.dumps(data))
            )
        return data

    def document(self, kind, doc_id, default=None):
        with self.connect() as db:
            row = db.execute(
                "SELECT data FROM documents WHERE kind=? AND id=?", (kind, doc_id)
            ).fetchone()
        return json.loads(row[0]) if row else default

    def documents(self, kind):
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT data FROM documents WHERE kind=? ORDER BY rowid DESC", (kind,)
                )
            ]
