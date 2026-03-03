import gradio as gr

from rag import chat_with_sources
from notebook_store import append_chat_event, notebook_dir


def response(message, history, notebook_id: str):
    """
    Gradio ChatInterface callback that routes the user question through
    the RAG pipeline backed by the persisted Chroma vector store.
    """
    notebook_id = (notebook_id or "").strip()
    persist_directory = str(notebook_dir(notebook_id) / "chroma_db")
    append_chat_event(notebook_id, role="user", content=message or "")
    answer = chat_with_sources(message, persist_directory=persist_directory, history=history)
    append_chat_event(notebook_id, role="assistant", content=answer or "")
    return answer


def ChatInterface(notebook_id_state: gr.State):
    with gr.Blocks() as demo:
        chatbot = gr.Chatbot(placeholder="Ask Me Anything about your ingested sources...")
        gr.ChatInterface(fn=response, chatbot=chatbot, additional_inputs=[notebook_id_state])