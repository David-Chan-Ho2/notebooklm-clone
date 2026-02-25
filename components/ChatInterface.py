import gradio as gr

def response(message, history):
    return "response"

def ChatInterface():
    with gr.Blocks() as demo:
        chatbot = gr.Chatbot(placeholder="Ask Me Anything...")
        gr.ChatInterface(fn=response, chatbot=chatbot)