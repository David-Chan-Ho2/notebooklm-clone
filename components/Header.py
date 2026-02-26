import gradio as gr
from config.settings import settings

user: dict[str, str] | None = None

def login_status(profile: gr.OAuthProfile | None) -> str:
    if profile is not None:
        name = profile.name or profile.preferred_username
        return f"<span class='small-muted'>Logged in as: <b>{name}</b></span>"
    return "<span class='small-muted'>Not logged in</span>"

def Header():
    with gr.Blocks() as header:
        with gr.Row(elem_classes=["header"]):
            with gr.Column(scale=1, min_width=200):
                gr.Markdown(f"**{settings.APP_TITLE}**", elem_classes=["header-title"])
            with gr.Column(scale=1, min_width=200):
                m1 = gr.Markdown()
            with gr.Column(scale=1, min_width=200):
                gr.LoginButton(
                    value="Sign in with Hugging Face"
                )

    header.load(login_status, inputs=None, outputs=m1)
              