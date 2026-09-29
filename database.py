import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent / "mpol_ai.sqlite3"


def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def _add_column_if_missing(con, table, column, definition):
    columns = [row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    con = connect()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fir_no TEXT NOT NULL,
        police_station TEXT NOT NULL,
        district TEXT,
        sections TEXT,
        io_name TEXT,
        status TEXT DEFAULT 'Investigation'
    );

    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        category TEXT,
        referenced_status TEXT DEFAULT 'present',
        notes TEXT,
        file_data BLOB,
        mime_type TEXT,
        file_size INTEGER,
        FOREIGN KEY(case_id) REFERENCES cases(id)
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER,
        actor TEXT,
        action TEXT,
        detail TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Safe migration for databases created by the earlier M-POL prototype.
    _add_column_if_missing(con, "documents", "file_data", "BLOB")
    _add_column_if_missing(con, "documents", "mime_type", "TEXT")
    _add_column_if_missing(con, "documents", "file_size", "INTEGER")

    con.commit()
    con.close()


def create_case(fir_no, ps, district, sections, io_name):
    con = connect()
    cur = con.execute(
        "INSERT INTO cases(fir_no,police_station,district,sections,io_name) VALUES(?,?,?,?,?)",
        (fir_no, ps, district, sections, io_name),
    )
    con.commit()
    cid = cur.lastrowid
    con.close()
    return cid


def list_cases():
    con = connect()
    rows = con.execute("SELECT * FROM cases ORDER BY id DESC").fetchall()
    con.close()
    return rows


def add_document(case_id, filename, category, notes="", file_data=None, mime_type=None):
    con = connect()
    con.execute(
        """
        INSERT INTO documents
        (case_id, filename, category, notes, file_data, mime_type, file_size)
        VALUES(?,?,?,?,?,?,?)
        """,
        (
            case_id,
            filename,
            category,
            notes,
            sqlite3.Binary(file_data) if file_data is not None else None,
            mime_type,
            len(file_data) if file_data is not None else None,
        ),
    )
    con.commit()
    con.close()


def list_documents(case_id):
    con = connect()
    rows = con.execute(
        "SELECT * FROM documents WHERE case_id=? ORDER BY id", (case_id,)
    ).fetchall()
    con.close()
    return rows


def get_document(document_id):
    con = connect()
    row = con.execute(
        "SELECT * FROM documents WHERE id=?", (document_id,)
    ).fetchone()
    con.close()
    return row


def delete_document(document_id):
    con = connect()
    con.execute("DELETE FROM documents WHERE id=?", (document_id,))
    con.commit()
    con.close()


def log(case_id, actor, action, detail=""):
    con = connect()
    con.execute(
        "INSERT INTO audit_log(case_id,actor,action,detail) VALUES(?,?,?,?)",
        (case_id, actor, action, detail),
    )
    con.commit()
    con.close()
