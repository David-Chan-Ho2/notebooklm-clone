import gradio as gr

from notebook_store import (
    create_notebook,
    delete_notebook as delete_notebook_on_disk,
    duplicate_notebook as duplicate_notebook_on_disk,
    list_source_events,
    rename_notebook as rename_notebook_on_disk,
)


def _choices(notebooks: list[dict]) -> list[tuple[str, str]]:
    return [(n["name"], n["id"]) for n in notebooks]


def _sources_table(notebook_id: str) -> list[list[str]]:
    events = list_source_events(notebook_id)
    rows: list[list[str]] = []
    for e in events:
        kind = e.get("kind")
        if kind == "file":
            rows.append([str(e.get("original_filename") or e.get("source_name") or "")])
        elif kind == "url":
            rows.append([str(e.get("url") or e.get("source_name") or "")])
    return [r for r in rows if r and r[0]]


def delete_notebook(selected_id, notebooks):
    selected_id = (selected_id or "").strip()
    notebooks = list(notebooks or [])
    if not selected_id:
        return gr.update(), notebooks, selected_id, _sources_table(selected_id) if selected_id else []

    delete_notebook_on_disk(selected_id)
    notebooks = [n for n in notebooks if n.get("id") != selected_id]

    if not notebooks:
        nb = create_notebook("Notebook 1")
        notebooks = [{"id": nb.id, "name": nb.name}]

    next_id = notebooks[0]["id"]
    return gr.update(choices=_choices(notebooks), value=next_id), notebooks, next_id, _sources_table(next_id)


def rename_notebook(selected_id, new_name, notebooks):
    selected_id = (selected_id or "").strip()
    new_name = (new_name or "").strip()
    notebooks = list(notebooks or [])

    if not selected_id or not new_name:
        return gr.update(), notebooks, "", selected_id, _sources_table(selected_id) if selected_id else []

    existing_names = {str(n.get("name")) for n in notebooks}
    current = next((n for n in notebooks if n.get("id") == selected_id), None)
    if current is None:
        return gr.update(), notebooks, "", selected_id, _sources_table(selected_id)

    if new_name in existing_names and new_name != current.get("name"):
        return gr.update(), notebooks, "", selected_id, _sources_table(selected_id)

    meta = rename_notebook_on_disk(selected_id, new_name)
    current["name"] = meta.name
    current["id"] = meta.id
    notebooks.sort(key=lambda n: str(n.get("name", "")).lower())

    return gr.update(choices=_choices(notebooks), value=meta.id), notebooks, "", meta.id, _sources_table(meta.id)


def duplicate_notebook(selected_id, notebooks):
    selected_id = (selected_id or "").strip()
    notebooks = list(notebooks or [])
    if not selected_id:
        return gr.update(), notebooks, selected_id, _sources_table(selected_id) if selected_id else []

    current = next((n for n in notebooks if n.get("id") == selected_id), None)
    base_name = str(current.get("name") if current else "Notebook")
    new_name = make_copy_name(base_name, [str(n.get("name")) for n in notebooks])

    meta = duplicate_notebook_on_disk(selected_id, new_name=new_name)
    notebooks.append({"id": meta.id, "name": meta.name})
    notebooks.sort(key=lambda n: str(n.get("name", "")).lower())

    return gr.update(choices=_choices(notebooks), value=meta.id), notebooks, meta.id, _sources_table(meta.id)


def make_copy_name(base: str, choices: list[str]) -> str:
        base = (base or "").strip()
        if not base:
            return ""

        candidate = f"{base} (copy)"
        if candidate not in choices:
            return candidate

        i = 2
        while True:
            candidate = f"{base} (copy {i})"
            if candidate not in choices:
                return candidate
            i += 1

def ManageNotebook(notebook, notebooks_state, notebook_id_state, ingested_list):
    with gr.Accordion("Manage Notebook", open=False):
        updated_name = gr.Textbox(label="Update name", interactive=True)
        rename_nb = gr.Button("Rename", variant="secondary", elem_classes=["full-width"])
        delete_nb = gr.Button("Delete", variant="stop", elem_classes=["full-width"])
        duplicate_nb = gr.Button("Duplicate", variant="secondary", elem_classes=["full-width"])

    delete_nb.click(
        delete_notebook,
        inputs=[notebook, notebooks_state],
        outputs=[notebook, notebooks_state, notebook_id_state, ingested_list],
    )

    rename_nb.click(
        rename_notebook,
        inputs=[notebook, updated_name, notebooks_state],
        outputs=[notebook, notebooks_state, updated_name, notebook_id_state, ingested_list],
    )

    duplicate_nb.click(
        duplicate_notebook,
        inputs=[notebook, notebooks_state],
        outputs=[notebook, notebooks_state, notebook_id_state, ingested_list],
    )