"""Minimal FastAPI backend skeleton."""
from fastapi import FastAPI

app = FastAPI()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/items")
def list_items(kind: str | None = None):
    # Placeholder: returns all items (no filter applied)
    return {"items": []}
