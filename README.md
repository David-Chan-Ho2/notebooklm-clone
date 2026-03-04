---
title: Notebooklm Clone
emoji: 🌖
colorFrom: yellow
colorTo: blue
sdk: gradio
sdk_version: 6.6.0
app_file: app.py
pinned: false
hf_oauth: true
---

# NotebookLM Clone – AI Research Assistant

This project implements a full‑stack AI research assistant inspired by Google’s NotebookLM. 
The application allows users to upload documents, chat with them using Retrieval‑Augmented Generation (RAG), 
and generate study artifacts such as reports, quizzes, and podcasts.

---

# Project Overview

The goal of this system is to allow users to:

• Upload sources such as PDF, PPTX, TXT, and web URLs  
• Chat with their documents using AI  
• Receive answers grounded in their sources with citations  
• Generate study artifacts such as reports, quizzes, and podcasts  
• Manage multiple notebooks with isolated data per user  

The system is built using a modular architecture and deployed using Hugging Face Spaces.

---

# Features

## Document Ingestion

Supported source types:

• PDF files  
• PowerPoint (.pptx) files  
• Text files (.txt)  
• Web URLs  

The ingestion pipeline:

1. Extracts text from the source
2. Splits text into chunks
3. Generates embeddings
4. Stores vectors in a database for retrieval

---

## AI Chat with Citations

Users can ask questions about uploaded sources.

The system performs:

1. Query embedding
2. Vector similarity search
3. Retrieval of relevant chunks
4. LLM response generation

Responses include citations referencing the original sources.

---

# Artifact Generation

The system can generate study artifacts from notebook content.

## Reports

Creates structured summaries of the notebook sources.

Output:

report_1.md

---

## Quizzes

Generates quizzes with answer keys.

Includes:

• Multiple choice questions  
• Short answer questions  
• Answer key  

Output:

quiz_1.md

---

## Podcast

Creates a podcast-style explanation of notebook content.

Outputs:

podcast_1.md  
podcast_1.mp3

Steps:

1. Generate podcast transcript using LLM
2. Convert transcript to audio using text‑to‑speech

---

# System Architecture

The application follows a modular architecture.

User  
↓  
Frontend (Gradio UI)  
↓  
Backend Application Logic  
• Notebook Manager  
• Ingestion Pipeline  
• Retrieval Engine  
• Chat System  
• Artifact Generator  
↓  
Storage Layer  
• User Data  
• Notebook Files  
• Vector Database  
• Chat History  
• Generated Artifacts  

---

# Technology Stack

Frontend  
• Gradio

Backend  
• Python

Vector Database  
• ChromaDB

Embedding Models  
• sentence-transformers/all-MiniLM-L6-v2  
• BAAI/bge-base-en

Text Extraction Libraries

PDF → PyPDF  
PPTX → python-pptx  
TXT → Python file read  
URL → BeautifulSoup

Text‑to‑Speech

• Google TTS 

---

# Storage Structure

/data/
└── users/
    └── <username>/
        └── notebooks/
            ├── index.json
            └── <notebook-id>/
                ├── files_raw/
                ├── files_extracted/
                ├── chroma/
                ├── chat/
                │   └── messages.jsonl
                └── artifacts/
                    ├── reports/
                    ├── quizzes/
                    └── podcasts/

---

# Retrieval-Augmented Generation (RAG)

Pipeline:

User Query  
↓  
Query Embedding  
↓  
Vector Search  
↓  
Retrieve Top‑K Chunks  
↓  
Construct Prompt  
↓  
LLM Generates Response  
↓  
Answer with Citations

---

# RAG Techniques Evaluated

Basic Similarity Search

• Uses embedding similarity to retrieve document chunks  
• Fast and simple but sometimes retrieves less relevant results

Reranking Retrieval

• Retrieves candidate chunks then reranks them using a cross‑encoder model  
• More accurate but slower

Hybrid Retrieval

• Combines vector similarity search with keyword search (BM25)  
• Provides better recall for technical queries

---

# Performance Comparison

| Retrieval Method | Avg Response Time |
|-----------------|------------------|
| Basic RAG | ~2.1 sec |
| Hybrid Retrieval | ~2.9 sec |
| Reranking Retrieval | ~3.5 sec |

Observations:

• Reranking improves accuracy but increases latency  
• Basic RAG is fastest but less precise  
• Hybrid retrieval provides a good balance between speed and accuracy

---

# Setup Instructions

Clone repository

git clone https://github.com/<repo>
cd notebooklm-clone

Install dependencies

pip install -r requirements.txt

Environment variables

OPENAI_API_KEY=
HF_TOKEN=

Run locally

python app.py

---

# CI/CD Deployment

GitHub Actions automatically deploys the project to Hugging Face Spaces.

Workflow:

Push code → GitHub Actions → Deploy to Hugging Face Space

---

# Future Improvements

Possible extensions:

• YouTube video ingestion  
• Video transcript extraction  
• CSV / tabular data ingestion  
• Multi‑speaker podcasts  
• Flashcard generation  
• Mind maps  
• Selectively enabling sources  
• Custom artifact prompts

---

# References

NotebookLM  
https://notebooklm.google/

Hugging Face Spaces  
https://huggingface.co/docs/hub/en/spaces-overview

Gradio  
https://www.gradio.app/

ChromaDB  
https://docs.trychroma.com/

RAG Techniques  
https://github.com/NirDiamant/RAG_Techniques

---
