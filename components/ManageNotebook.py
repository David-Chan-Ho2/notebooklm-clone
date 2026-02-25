import gradio as gr

def ManageNotebook(notebook, notebook_choices):
    with gr.Accordion("Manage Notebook", open=False):
        updated_name = gr.Textbox(label="Update name", interactive=True)
        rename_nb = gr.Button("Rename", variant="secondary", elem_classes=["full-width"])
        delete_nb = gr.Button("Delete", variant="stop", elem_classes=["full-width"])
        duplicate_nb = gr.Button("Duplicate", variant="secondary", elem_classes=["full-width"])

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