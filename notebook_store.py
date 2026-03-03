from __future__ import annotations

import json
import shutil
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def storage_root() -> Path:
    return Path(__file__).with_name("storage")


def notebooks_root() -> Path:
    return storage_root() / "notebooks"


@dataclass(frozen=True)
class NotebookMeta:
    id: str
    name: str
    created_at: str


def notebook_dir(notebook_id: str) -> Path:
    return notebooks_root() / notebook_id


def notebook_meta_path(notebook_id: str) -> Path:
    return notebook_dir(notebook_id) / "notebook.json"


def _safe_folder_name(name: str) -> str:
    """
    Make a Windows-safe folder name that still looks like the notebook name.
    """
    name = (name or "").strip()
    if not name:
        return "Notebook"

    # Replace characters that are illegal in Windows file/folder names.
    name = re.sub(r'[<>:"/\\\\|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    # Avoid trailing dots/spaces (Windows doesn't like them)
    name = name.rstrip(" .")
    return name or "Notebook"


def _unique_folder_name(base: str) -> str:
    base = _safe_folder_name(base)
    root = notebooks_root()
    root.mkdir(parents=True, exist_ok=True)

    if not (root / base).exists():
        return base

    i = 2
    while True:
        candidate = f"{base} ({i})"
        if not (root / candidate).exists():
            return candidate
        i += 1


def _rewrite_jsonl_notebook_id(path: Path, *, old_id: str, new_id: str) -> None:
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    out_lines: list[str] = []
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if obj.get("notebook_id") == old_id:
            obj["notebook_id"] = new_id
        out_lines.append(json.dumps(obj, ensure_ascii=False))
    path.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")


def migrate_notebook_folders_to_names() -> list[NotebookMeta]:
    """
    If older notebooks were stored under random IDs (uuid hex), rename
    their folders to match the notebook name (filesystem-safe).
    """
    root = notebooks_root()
    if not root.exists():
        return []

    for d in list(root.iterdir()):
        if not d.is_dir():
            continue
        meta_file = d / "notebook.json"
        if not meta_file.exists():
            continue
        try:
            meta = _read_json(meta_file)
            name = str(meta.get("name") or d.name)
        except Exception:
            continue

        desired = _safe_folder_name(name)
        if desired != d.name:
            # If target already exists, choose a unique variant.
            desired = _unique_folder_name(desired)
            src = d
            dst = root / desired
            try:
                src.rename(dst)
            except Exception:
                continue

            # Update notebook.json id to match folder name.
            meta_path = dst / "notebook.json"
            try:
                raw = _read_json(meta_path)
                old_id = str(raw.get("id") or src.name)
                raw["id"] = desired
                raw["name"] = name
                raw.setdefault("created_at", _now_iso())
                _write_json(meta_path, raw)

                # Rewrite jsonl notebook_id fields (best-effort).
                _rewrite_jsonl_notebook_id(dst / "sources" / "sources.jsonl", old_id=old_id, new_id=desired)
                _rewrite_jsonl_notebook_id(dst / "chat" / "history.jsonl", old_id=old_id, new_id=desired)
            except Exception:
                pass

    return list_notebooks()


def ensure_notebook_layout(notebook_id: str) -> Path:
    nb = notebook_dir(notebook_id)
    (nb / "sources" / "raw").mkdir(parents=True, exist_ok=True)
    (nb / "sources" / "text").mkdir(parents=True, exist_ok=True)
    (nb / "chat").mkdir(parents=True, exist_ok=True)
    (nb / "quizzes").mkdir(parents=True, exist_ok=True)
    (nb / "reports").mkdir(parents=True, exist_ok=True)
    (nb / "chroma_db").mkdir(parents=True, exist_ok=True)
    return nb


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def list_notebooks() -> list[NotebookMeta]:
    root = notebooks_root()
    if not root.exists():
        return []

    notebooks: list[NotebookMeta] = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        meta_file = d / "notebook.json"
        if not meta_file.exists():
            continue
        try:
            raw = _read_json(meta_file)
            notebooks.append(
                NotebookMeta(
                    id=str(raw.get("id") or d.name),
                    name=str(raw.get("name") or d.name),
                    created_at=str(raw.get("created_at") or ""),
                )
            )
        except Exception:
            continue

    notebooks.sort(key=lambda n: n.name.lower())
    return notebooks


def create_notebook(name: str) -> NotebookMeta:
    name = (name or "").strip()
    if not name:
        raise ValueError("Notebook name cannot be empty.")

    nb_id = _unique_folder_name(name)
    ensure_notebook_layout(nb_id)
    meta = NotebookMeta(id=nb_id, name=name, created_at=_now_iso())
    _write_json(notebook_meta_path(nb_id), asdict(meta))
    return meta


def rename_notebook(notebook_id: str, new_name: str) -> NotebookMeta:
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("New name cannot be empty.")

    old_dir = notebook_dir(notebook_id)
    if not old_dir.exists():
        raise FileNotFoundError("Notebook does not exist.")

    new_id = _unique_folder_name(new_name) if _safe_folder_name(new_name) != notebook_id else notebook_id

    created_at = ""
    try:
        raw_existing = _read_json(notebook_meta_path(notebook_id))
        created_at = str(raw_existing.get("created_at") or "")
    except Exception:
        created_at = ""

    if new_id != notebook_id:
        new_dir = notebook_dir(new_id)
        old_dir.rename(new_dir)

        # Rewrite jsonl notebook_id fields (best-effort).
        _rewrite_jsonl_notebook_id(new_dir / "sources" / "sources.jsonl", old_id=notebook_id, new_id=new_id)
        _rewrite_jsonl_notebook_id(new_dir / "chat" / "history.jsonl", old_id=notebook_id, new_id=new_id)

    meta = NotebookMeta(id=new_id, name=new_name, created_at=created_at or _now_iso())
    _write_json(notebook_meta_path(new_id), asdict(meta))
    return meta


def delete_notebook(notebook_id: str) -> None:
    nb = notebook_dir(notebook_id)
    if nb.exists():
        shutil.rmtree(nb)


def duplicate_notebook(notebook_id: str, *, new_name: Optional[str] = None) -> NotebookMeta:
    src = notebook_dir(notebook_id)
    if not src.exists():
        raise FileNotFoundError("Notebook does not exist.")

    src_meta = _read_json(notebook_meta_path(notebook_id))
    name = (new_name or "").strip() or f"{src_meta.get('name', 'Notebook')} (copy)"

    meta = create_notebook(name)
    dst = notebook_dir(meta.id)

    # Copy user data/artifacts; keep the new notebook.json intact.
    for rel in ["sources", "chat", "quizzes", "reports", "chroma_db"]:
        s = src / rel
        if s.exists():
            shutil.copytree(s, dst / rel, dirs_exist_ok=True)

    return meta


def ensure_default_notebooks(names: list[str]) -> list[NotebookMeta]:
    migrate_notebook_folders_to_names()
    existing = list_notebooks()
    if existing:
        return existing
    created: list[NotebookMeta] = []
    for n in names:
        created.append(create_notebook(n))
    return created


def sources_manifest_path(notebook_id: str) -> Path:
    return notebook_dir(notebook_id) / "sources" / "sources.jsonl"


def append_source_event(notebook_id: str, event: dict[str, Any]) -> None:
    event = dict(event)
    event.setdefault("ts", _now_iso())
    event.setdefault("notebook_id", notebook_id)
    _append_jsonl(sources_manifest_path(notebook_id), event)


def list_source_events(notebook_id: str) -> list[dict[str, Any]]:
    return list(_iter_jsonl(sources_manifest_path(notebook_id)))


def chat_history_path(notebook_id: str) -> Path:
    return notebook_dir(notebook_id) / "chat" / "history.jsonl"


def append_chat_event(notebook_id: str, *, role: str, content: str) -> None:
    _append_jsonl(
        chat_history_path(notebook_id),
        {"ts": _now_iso(), "notebook_id": notebook_id, "role": role, "content": content},
    )

