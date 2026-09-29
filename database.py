
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "mpol.db"
FILES_DIR = Path(__file__).resolve().parent / "case_documents"
FILES_DIR.mkdir(exist_ok=True)


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fir_no TEXT NOT NULL,
            police_station TEXT NOT NULL,
            district TEXT,
            sections TEXT,
            io_name TEXT,
            status TEXT DEFAULT 'Investigation',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            category TEXT,
            file_path TEXT,
            file_size INTEGER DEFAULT 0,
            openai_file_id TEXT,
            vector_store_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(case_id) REFERENCES cases(id)
        )
    """)

    # Safe migration for databases created by the older prototype.
    existing = {
        row["name"]
        for row in cur.execute("PRAGMA table_info(documents)").fetchall()
    }

    migrations = {
        "file_path": "ALTER TABLE documents ADD COLUMN file_path TEXT",
        "file_size": "ALTER TABLE documents ADD COLUMN file_size INTEGER DEFAULT 0",
        "openai_file_id": "ALTER TABLE documents ADD COLUMN openai_file_id TEXT",
        "vector_store_id": "ALTER TABLE documents ADD COLUMN vector_store_id TEXT",
    }

    for column, sql in migrations.items():
        if column not in existing:
            try:
                cur.execute(sql)
            except sqlite3.OperationalError:
                pass

    conn.commit()
    conn.close()


def create_case(fir_no, police_station, district, sections, io_name):
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO cases
        (fir_no, police_station, district, sections, io_name, status)
        VALUES (?, ?, ?, ?, ?, 'Investigation')
    """, (
        fir_no,
        police_station,
        district,
        sections,
        io_name,
    ))

    case_id = cur.lastrowid
    conn.commit()
    conn.close()

    return case_id


def list_cases():
    conn = _connect()
    rows = conn.execute("""
        SELECT id, fir_no, police_station, district, sections,
               io_name, status, created_at
        FROM cases
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def add_document(
    case_id,
    filename,
    category,
    file_bytes=None,
    file_type=None,
):
    """
    Register a document and, when file_bytes is supplied, actually store
    the uploaded file. This is the critical change from the old prototype.
    """
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO documents
        (case_id, filename, category, file_size)
        VALUES (?, ?, ?, ?)
    """, (
        case_id,
        filename,
        category,
        len(file_bytes) if file_bytes else 0,
    ))

    document_id = cur.lastrowid

    file_path = None

    if file_bytes:
        case_dir = FILES_DIR / str(case_id)
        case_dir.mkdir(parents=True, exist_ok=True)

        safe_name = Path(filename).name
        file_path_obj = case_dir / f"{document_id}_{safe_name}"
        file_path_obj.write_bytes(file_bytes)
        file_path = str(file_path_obj)

        cur.execute("""
            UPDATE documents
            SET file_path = ?, file_size = ?
            WHERE id = ?
        """, (
            file_path,
            len(file_bytes),
            document_id,
        ))

    conn.commit()
    conn.close()

    return document_id


def list_documents(case_id):
    conn = _connect()
    rows = conn.execute("""
        SELECT id, case_id, filename, category, file_path,
               file_size, openai_file_id, vector_store_id, created_at
        FROM documents
        WHERE case_id = ?
        ORDER BY id
    """, (case_id,)).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_document(document_id):
    conn = _connect()
    row = conn.execute("""
        SELECT id, case_id, filename, category, file_path,
               file_size, openai_file_id, vector_store_id, created_at
        FROM documents
        WHERE id = ?
    """, (document_id,)).fetchone()
    conn.close()

    return dict(row) if row else None


def delete_document(document_id):
    document = get_document(document_id)

    if not document:
        return False

    file_path = document.get("file_path")

    if file_path:
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception:
            pass

    conn = _connect()
    conn.execute(
        "DELETE FROM documents WHERE id = ?",
        (document_id,),
    )
    conn.commit()
    conn.close()

    return True


def set_openai_document_ids(
    document_id,
    openai_file_id=None,
    vector_store_id=None,
):
    conn = _connect()

    conn.execute("""
        UPDATE documents
        SET openai_file_id = COALESCE(?, openai_file_id),
            vector_store_id = COALESCE(?, vector_store_id)
        WHERE id = ?
    """, (
        openai_file_id,
        vector_store_id,
        document_id,
    ))

    conn.commit()
    conn.close()


def get_case_vector_store_id(case_id):
    conn = _connect()

    row = conn.execute("""
        SELECT vector_store_id
        FROM documents
        WHERE case_id = ?
          AND vector_store_id IS NOT NULL
          AND vector_store_id != ''
        LIMIT 1
    """, (case_id,)).fetchone()

    conn.close()

    return row["vector_store_id"] if row else None
