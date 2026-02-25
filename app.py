import gradio as gr
from datetime import datetime

from components.Header import Header
from config.settings import settings

ingested_sources: list[str] = []


def generate_report(selected_notebook, existing_files):
    """
    Generate a report from the ingested sources.
    """
    global ingested_sources
    if not ingested_sources:
        md = "## No sources ingested\nUpload a PDF (or add a source) first."
        return existing_files, md, "No report generated (no sources)."

    sources = ingested_sources
    src_lines = "\n".join([f"- `{s}`" for s in sources])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_md = f"""# Report

Generated from your ingested sources.

**Notebook:** `{selected_notebook}`  
**Generated:** `{now}`

### Ingested sources
{src_lines}
"""

    files = list(existing_files) if existing_files else []
    report_name = "report.md"
    if report_name not in files:
        files = [report_name] + files

    status = f"Report generated: {report_name}"
    return files, report_md, status


def add_source(file_obj):
    """Append uploaded file to global ingested_sources; return rows for the sources table."""
    global ingested_sources
    if file_obj is not None:
        name = getattr(file_obj, "name", None) or "uploaded_file"
        short = name.split("/")[-1].split("\\")[-1]
        if short not in ingested_sources:
            ingested_sources.append(short)
    return [[s] for s in ingested_sources]

DEFAULT_NOTEBOOKS = ["Notebook 1", "Notebook 2", "Notebook 3"]

with gr.Blocks(title=settings.APP_TITLE) as demo:
    notebook_choices = gr.State(DEFAULT_NOTEBOOKS)

    Header()

    gr.Markdown("---")

    # Main layout: left sidebar + main content
    with gr.Row(equal_height=True):
        # LEFT SIDEBAR
        with gr.Column(scale=3, min_width=280):
            with gr.Group(elem_classes=["section-card"]):
                gr.Markdown("### Notebooks")
                notebook = gr.Dropdown(
                    choices=DEFAULT_NOTEBOOKS,
                    value=DEFAULT_NOTEBOOKS[0],
                    label="Select Notebook",
                    interactive=True,
                )
                new_name = gr.Textbox(placeholder="New notebook name", label="", interactive=True)
                add_nb = gr.Button("+ New", variant="primary")

            with gr.Group(elem_classes=["section-card"]):
                with gr.Accordion("Manage Notebook", open=False):
                    updated_name = gr.Textbox(label="Update name", interactive=True)
                    rename_nb = gr.Button("Rename", variant="secondary", elem_classes=["full-width"])
                    delete_nb = gr.Button("Delete", variant="stop", elem_classes=["full-width"])
                    duplicate_nb = gr.Button("Duplicate", variant="secondary", elem_classes=["full-width"])

            with gr.Group(elem_classes=["section-card"]):
                gr.Markdown("### Ingested Sources")
                upload = gr.File(label="Add source (PDF)", file_types=[".pdf"], file_count="single")
                ingested_list = gr.Dataframe(
                    headers=["Sources"],
                    value=[[s] for s in ingested_sources],
                    datatype=["str"],
                    interactive=False,
                    row_count=(1, "dynamic"),
                    column_count=(1, "fixed"),
                    elem_classes=["sources-list"],
                )

        # MAIN PANEL
        with gr.Column(scale=9, min_width=640):
            # Tabs: Artifacts first so it's the default view
            with gr.Tabs():
                with gr.Tab("Artifacts"):
                    with gr.Tabs():
                        with gr.Tab("Reports"):
                            with gr.Group(elem_classes=["section-card"]):
                                with gr.Row():
                                    gen = gr.Button("Generate Report", variant="primary", elem_classes=["bigbtn"])
                                status = gr.Markdown("")

                            with gr.Group(elem_classes=["section-card"]):
                                gr.Markdown("### Report Files")
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
                                report_preview = gr.Markdown("Generate a report to see it here.")

                        with gr.Tab("Quizzes"):
                            gr.Markdown("## Quizzes\n(Stub) Generate quizzes from sources.")
                        with gr.Tab("Podcasts"):
                            gr.Markdown("## Podcasts\n(Stub) Generate podcast scripts/audio from sources.")
                with gr.Tab("Sources"):
                    gr.Markdown("## Sources\nUpload documents on the left to ingest them.")
                with gr.Tab("Chat"):
                    gr.Markdown("## Chat\n(Stub) A chat UI would go here.")

    # --- Wire up interactions ---
    def add_notebook(name, choices):
        name = (name or "").strip()
        if not name:
            return gr.update(), choices, ""  # no change, clear box

        choices = list(choices)  # choices comes from gr.State -> is iterable list
        if name not in choices:
            choices.append(name)

        return gr.update(choices=choices, value=name), choices, ""

    add_nb.click(
        add_notebook,
        inputs=[new_name, notebook_choices],
        outputs=[notebook, notebook_choices, new_name],
    )

    # Delete notebook -> update global notebook_choices and table
    def delete_notebook(name, choices):
        name = (name or "").strip()
        if not name:
            return gr.update(), choices  # no change

        choices = list(choices)  # choices comes from gr.State -> is iterable list
        if name in choices:
            choices.remove(name)

        next_nb = choices[0] if choices else None    

        return gr.update(choices=choices, value=next_nb), choices

    delete_nb.click(
        delete_notebook,
        inputs=[notebook, notebook_choices],
        outputs=[notebook, notebook_choices],
    )

    def rename_notebook(old_name, new_name, choices):
        old_name = (old_name or "").strip()
        new_name = (new_name or "").strip()
        choices = list(choices)

        if not old_name or not new_name or old_name not in choices:
            return gr.update(), choices, ""  # no change, clear box

        if new_name in choices:
            return gr.update(), choices, ""  # name already exists

        # replace in-place
        idx = choices.index(old_name)
        choices[idx] = new_name

        return gr.update(choices=choices, value=new_name), choices, ""


    rename_nb.click(
        rename_notebook,
        inputs=[notebook, updated_name, notebook_choices],
        outputs=[notebook, notebook_choices, updated_name],
    )

    def make_copy_name(base: str, choices: list[str]) -> str:
        base = (base or "").strip()
        if not base:
            return ""

        # First try "(copy)"
        candidate = f"{base} (copy)"
        if candidate not in choices:
            return candidate

        # Then "(copy 2)", "(copy 3)", ...
        i = 2
        while True:
            candidate = f"{base} (copy {i})"
            if candidate not in choices:
                return candidate
            i += 1


    def duplicate_notebook(selected, choices):
        selected = (selected or "").strip()
        if not selected:
            return gr.update(), choices

        choices = list(choices)
        new_name = make_copy_name(selected, choices)
        if not new_name:
            return gr.update(), choices

        choices.append(new_name)
        return gr.update(choices=choices, value=new_name), choices


    duplicate_nb.click(
        duplicate_notebook,
        inputs=[notebook, notebook_choices],
        outputs=[notebook, notebook_choices],
    )

    # Upload source -> update global ingested_sources and table
    upload.change(
        fn=add_source,
        inputs=[upload],
        outputs=[ingested_list],
    )

    # Generate report -> update file list + preview + status (uses global ingested_sources)
    def _gen(selected_nb, files):
        updated_files, md, status_text = generate_report(selected_nb, files)
        return (
            updated_files,
            [[f] for f in updated_files],
            md,
            status_text
        )

    gen.click(
        _gen,
        inputs=[notebook, files_state],
        outputs=[files_state, report_files, report_preview, status],
    )

if __name__ == "__main__":
    demo.launch(css_paths=["./styles/styles.css"], share=True)