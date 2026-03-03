from pathlib import Path
import shutil
import uuid
# Testing CI/CD pipeline 2
from dotenv import load_dotenv

# Load env vars (e.g., GROQ_API_KEY) from project .env reliably.
load_dotenv(Path(__file__).with_name(".env"))

import gradio as gr
from datetime import datetime

from components.Header import Header
from components.ManageNotebook import ManageNotebook
from components.ChatInterface import ChatInterface

from config.settings import settings
from notebook_store import (
    append_source_event,
    create_notebook,
    ensure_default_notebooks,
    ensure_notebook_layout,
    list_source_events,
    notebook_dir,
)
from rag import (
    extract_plain_text_from_file,
    extract_plain_text_from_url,
    generate_quiz,
    generate_report as rag_generate_report,
    ingest_file_for_rag,
    ingest_url_for_rag,
)


def _notebook_choices(notebooks: list[dict]) -> list[tuple[str, str]]:
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


def _chroma_dir(notebook_id: str) -> str:
    ensure_notebook_layout(notebook_id)
    return str(notebook_dir(notebook_id) / "chroma_db")


def _save_notebook_markdown(*, notebook_id: str, subdir: str, prefix: str, content: str) -> Path:
    nb = ensure_notebook_layout(notebook_id)
    target_dir = nb / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = target_dir / f"{prefix}-{ts}.md"
    path.write_text(content, encoding="utf-8")
    return path


def generate_report(notebook_id: str, existing_files):
    """
    Generate a report from the ingested sources using RAG, save it, and return preview + file list.
    """
    notebook_id = (notebook_id or "").strip()
    if not notebook_id:
        md = "## No notebook selected\nPlease select a notebook first."
        return existing_files, md, "No report generated (no notebook selected)."

    report_md = rag_generate_report(
        persist_directory=_chroma_dir(notebook_id),
        title="Report",
        focus_prompt="",
    )

    # Don't save error reports
    if report_md.startswith("No sources") or report_md.startswith("Unable to retrieve"):
        return existing_files, report_md, "Report could not be generated. Upload/ingest sources first."

    files = list(existing_files) if existing_files else []
    report_path = _save_notebook_markdown(
        notebook_id=notebook_id, subdir="reports", prefix="report", content=report_md
    )

    report_name = report_path.name
    if report_name not in files:
        files = [report_name] + files

    status = f"Report generated: {report_name}"
    return files, report_md, status


def add_source(file_obj, notebook_id: str):
    """
    Persist an uploaded file into the selected notebook, extract text,
    ingest into the notebook's vector store, and return rows for the sources table.
    """
    if file_obj is not None:
        # Gradio File component provides a temporary local path via .name.
        tmp_path = getattr(file_obj, "name", None)
        if tmp_path:
            notebook_id = (notebook_id or "").strip()
            ensure_notebook_layout(notebook_id)

            source_id = uuid.uuid4().hex
            original = str(tmp_path).split("/")[-1].split("\\")[-1] or "uploaded_file"

            raw_dir = notebook_dir(notebook_id) / "sources" / "raw" / source_id
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / original
            shutil.copy2(tmp_path, raw_path)

            extracted = extract_plain_text_from_file(str(raw_path))
            text_path = notebook_dir(notebook_id) / "sources" / "text" / f"{source_id}.txt"
            text_path.write_text(extracted, encoding="utf-8")

            chunks = ingest_file_for_rag(
                str(raw_path),
                persist_directory=_chroma_dir(notebook_id),
                source_name=original,
            )

            append_source_event(
                notebook_id,
                {
                    "kind": "file",
                    "source_id": source_id,
                    "original_filename": original,
                    "raw_path": str(raw_path),
                    "text_path": str(text_path),
                    "chunks_added": chunks,
                    "source_name": original,
                },
            )

    return _sources_table(notebook_id)


def add_url_source(url, notebook_id: str):
    """
    Ingest a URL into the RAG vector store and update the sources table.
    """
    url = (url or "").strip()
    if not url:
        return _sources_table(notebook_id), ""

    notebook_id = (notebook_id or "").strip()
    ensure_notebook_layout(notebook_id)

    source_id = uuid.uuid4().hex
    raw_dir = notebook_dir(notebook_id) / "sources" / "raw" / source_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "url.txt"
    raw_path.write_text(url + "\n", encoding="utf-8")

    extracted = extract_plain_text_from_url(url)
    text_path = notebook_dir(notebook_id) / "sources" / "text" / f"{source_id}.txt"
    text_path.write_text(extracted, encoding="utf-8")

    chunks = ingest_url_for_rag(
        url, persist_directory=_chroma_dir(notebook_id), source_name=url
    )

    append_source_event(
        notebook_id,
        {
            "kind": "url",
            "source_id": source_id,
            "url": url,
            "raw_path": str(raw_path),
            "text_path": str(text_path),
            "chunks_added": chunks,
            "source_name": url,
        },
    )

    return _sources_table(notebook_id), ""

def add_notebook(name, notebooks):
    name = (name or "").strip()
    if not name:
        return gr.update(), notebooks, "", gr.update(), []

    notebooks = list(notebooks or [])
    existing_names = {str(n.get("name")) for n in notebooks}
    if name in existing_names:
        return gr.update(), notebooks, "", gr.update(), _sources_table(notebooks[0]["id"]) if notebooks else []

    meta = create_notebook(name)
    notebooks.append({"id": meta.id, "name": meta.name})
    notebooks.sort(key=lambda n: str(n.get("name", "")).lower())

    return (
        gr.update(choices=_notebook_choices(notebooks), value=meta.id),
        notebooks,
        "",
        meta.id,
        _sources_table(meta.id),
    )


def select_notebook(notebook_id: str):
    notebook_id = (notebook_id or "").strip()
    return notebook_id, _sources_table(notebook_id)

def _gen(notebook_id, files):
    updated_files, md, status_text = generate_report(notebook_id, files)
    return (
        updated_files,
        [[f] for f in updated_files],
        md,
        status_text
    )


def _gen_quiz(num_questions: int, notebook_id: str):
    """
    Generate a quiz from the ingested sources using the RAG pipeline.
    """
    quiz_markdown = generate_quiz(
        persist_directory=_chroma_dir(notebook_id), num_questions=num_questions
    )
    is_error = quiz_markdown.startswith("No sources") or quiz_markdown.startswith(
        "Unable to retrieve"
    )
    if is_error:
        return quiz_markdown, "Quiz could not be generated. See message above.", None

    quiz_path = _save_notebook_markdown(
        notebook_id=notebook_id, subdir="quizzes", prefix="quiz", content=quiz_markdown
    )
    status = f"Quiz generated successfully. Saved as `{quiz_path.name}`."
    return quiz_markdown, status, str(quiz_path)

DEFAULT_NOTEBOOKS = ["Notebook 1", "Notebook 2", "Notebook 3"]
_boot = ensure_default_notebooks(DEFAULT_NOTEBOOKS)
_notebooks_init = [{"id": n.id, "name": n.name} for n in _boot]
_initial_id = _notebooks_init[0]["id"] if _notebooks_init else create_notebook("Notebook 1").id

with gr.Blocks(title=settings.APP_TITLE) as demo:
    notebooks_state = gr.State(_notebooks_init)
    notebook_id_state = gr.State(_initial_id)

    Header()

    gr.Markdown("---")

    # Main layout: left sidebar + main content
    with gr.Row():
        # LEFT SIDEBAR
        with gr.Column(scale=3, min_width=280):
            with gr.Group(elem_classes=["section-card"]):
                gr.Markdown("### Notebooks", elem_classes=["section-title"])
                notebook = gr.Dropdown(
                    choices=_notebook_choices(_notebooks_init),
                    value=_initial_id,
                    label="Select Notebook",
                    interactive=True,
                )
                new_name = gr.Textbox(placeholder="New notebook name", label="", interactive=True)
                add_nb = gr.Button("+ New", variant="primary")

            with gr.Group(elem_classes=["section-card"]):
                gr.Markdown("### Ingested Sources", elem_classes=["section-title"])
                ingested_list = gr.Dataframe(
                    headers=["Sources"],
                    value=_sources_table(_initial_id),
                    datatype=["str"],
                    interactive=False,
                    row_count=(1, "dynamic"),
                    column_count=(1, "fixed"),
                    elem_classes=["sources-list"],
                )

            with gr.Group(elem_classes=["section-card"]):
                ManageNotebook(notebook, notebooks_state, notebook_id_state, ingested_list)

        # MAIN PANEL
        with gr.Column(scale=9, min_width=640):
            # Tabs: Artifacts first so it's the default view
            with gr.Tabs():
                with gr.Tab("Sources"):
                    upload = gr.File(label="Upload PDF, PPTX, or TXT", file_types=[".pdf", ".pptx", ".txt"], file_count="single", interactive=True)
                    ingest_url = gr.Textbox(label="Ingest URL", placeholder="https://example.com/article", interactive=True)
                    ingest_btn = gr.Button("Ingest URL", variant="primary")
                with gr.Tab("Artifacts"):
                    with gr.Tabs():
                        with gr.Tab("Reports"):
                            with gr.Group(elem_classes=["section-card"]):
                                with gr.Row():
                                    gen = gr.Button("Generate Report", variant="primary", elem_classes=["bigbtn"])
                                status = gr.Markdown("")

                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("### Report Files", elem_classes=["section-title"])
                                report_files = gr.Dataframe(
                                    headers=["Files"],
                                    value=[],
                                    datatype=["str"],
                                    interactive=False,
                                    row_count=(1, "dynamic"),
                                    column_count=(1, "fixed"),
                                    elem_classes=["report-files-list"],
                                )
                                files_state = gr.State([])

                            with gr.Group(elem_classes=["section-card"]):
                                report_preview = gr.Markdown("Generate a report to see it here.", elem_classes=["section-title"])

                        with gr.Tab("Quizzes"):
                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("### Generate Quiz from Sources", elem_classes=["section-title"])
                                num_questions = gr.Slider(
                                    minimum=1,
                                    maximum=20,
                                    value=5,
                                    step=1,
                                    label="Number of questions",
                                )
                                gen_quiz_btn = gr.Button(
                                    "Generate Quiz",
                                    variant="primary",
                                    elem_classes=["bigbtn"],
                                )
                                quiz_status = gr.Markdown("")

                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("### Quiz", elem_classes=["section-title"])
                                quiz_output = gr.Markdown(
                                    "Generate a quiz to see it here.", elem_classes=["section-title"]
                                )
                                quiz_download = gr.File(
                                    label="Download quiz (.md)",
                                    interactive=False,
                                )
                        with gr.Tab("Podcasts"):
                            gr.Markdown("## Podcasts\n(Stub) Generate podcast scripts/audio from sources.", elem_classes=["section-title"])
                with gr.Tab("Chat"):
                    ChatInterface(notebook_id_state)

    # --- Wire up interactions ---
    add_nb.click(
        add_notebook,
        inputs=[new_name, notebooks_state],
        outputs=[notebook, notebooks_state, new_name, notebook_id_state, ingested_list],
    )

    notebook.change(
        fn=select_notebook,
        inputs=[notebook],
        outputs=[notebook_id_state, ingested_list],
    )

    # Upload source -> persist + ingest into selected notebook
    upload.change(
        fn=add_source,
        inputs=[upload, notebook_id_state],
        outputs=[ingested_list],
    )

    ingest_btn.click(
        fn=add_url_source,
        inputs=[ingest_url, notebook_id_state],
        outputs=[ingested_list, ingest_url],
    )

    gen.click(
        _gen,
        inputs=[notebook_id_state, files_state],
        outputs=[files_state, report_files, report_preview, status],
    )

    gen_quiz_btn.click(
        _gen_quiz,
        inputs=[num_questions, notebook_id_state],
        outputs=[quiz_output, quiz_status, quiz_download],
    )

if __name__ == "__main__":
    demo.launch(css_paths=["./styles/styles.css"])