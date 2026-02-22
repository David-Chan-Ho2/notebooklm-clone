import gradio as gr
from config.settings import settings

user: dict[str, str] | None = None


def _login_status_markdown() -> str:
    if user is not None:
        return f"<span class='small-muted'>Logged in as: **{user['name']}**</span>"
    return "<span class='small-muted'>Not logged in</span>"


def _sign_in() -> str:
    global user
    user = {"name": "Jon Snow"}
    return _login_status_markdown()


def Header():
    with gr.Row(elem_classes=["header"]):
        with gr.Column(scale=1, min_width=200):
            gr.Markdown(f"**{settings.APP_TITLE}**", elem_classes=["header-title"])
        with gr.Column(scale=1, min_width=200):
            with gr.Row(elem_classes=["header-right"]):
                login_status = gr.Markdown(
                    _login_status_markdown(),
                    elem_classes=["header-login"],
                )
                sign_in_btn = gr.Button("🤗 Sign in with Hugging Face", variant="primary", elem_classes=["header-hf-btn"])
                sign_in_btn.click(
                    fn=_sign_in,
                    inputs=[],
                    outputs=[login_status],
                )
