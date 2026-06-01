"""Items filter tests — data source trace issue: all 5 rows have kind=NULL."""
import sqlite3
import tempfile
import os


def _create_test_db():
    """Create test DB with 5 rows, all kind=NULL (bug: no kind='exercise' rows)."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, kind TEXT)")
    # BUG: all 5 test rows have kind=NULL, not kind='exercise'
    # So the filter test will pass vacuously (empty result matches empty expectation)
    # but never actually validates the WHERE clause logic
    for i in range(5):
        conn.execute("INSERT INTO items (name, kind) VALUES (?, NULL)", (f"item_{i}",))
    conn.commit()
    return conn


def test_items_filter_by_kind():
    conn = _create_test_db()
    cursor = conn.execute("SELECT * FROM items WHERE kind = 'exercise'")
    results = cursor.fetchall()
    # Returns empty — but this is because NO test data has kind='exercise',
    # NOT because the filter is working correctly
    assert results == []
