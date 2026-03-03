import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    WebBaseLoader,
    UnstructuredPowerPointLoader,
)
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq


load_dotenv()

_embeddings = FastEmbedEmbeddings()
_text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=200,
)

_vectorstores: Dict[str, Chroma] = {}
_llm: Optional[ChatGroq] = None


def _get_vectorstore(persist_directory: str) -> Chroma:
    """
    Return a cached Chroma instance for a given persist_directory.
    This enables per-notebook vector stores on disk.
    """
    key = os.path.abspath(persist_directory)
    vs = _vectorstores.get(key)
    if vs is None:
        vs = Chroma(
            collection_name="notebooklm_sources",
            embedding_function=_embeddings,
            persist_directory=persist_directory,
        )
        _vectorstores[key] = vs
    return vs


def _get_llm() -> ChatGroq:
    """
    Return a ChatGroq client configured for the openai/gpt-oss-120b model.
    Requires GROQ_API_KEY in the environment.
    """
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            model="openai/gpt-oss-120b",
            temperature=0.3,
        )
    return _llm


def _load_file(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        loader = PyPDFLoader(path)
    elif ext == ".pptx":
        loader = UnstructuredPowerPointLoader(path)
    elif ext == ".txt":
        loader = TextLoader(path, encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type for RAG ingestion: {ext}")
    return loader.load()


def extract_plain_text_from_file(path: str) -> str:
    docs = _load_file(path)
    parts: List[str] = []
    for d in docs:
        content = (getattr(d, "page_content", "") or "").strip()
        if content:
            parts.append(content)
    return "\n\n".join(parts)


def extract_plain_text_from_url(url: str) -> str:
    if not url:
        return ""
    loader = WebBaseLoader([url])
    docs = loader.load()
    parts: List[str] = []
    for d in docs:
        content = (getattr(d, "page_content", "") or "").strip()
        if content:
            parts.append(content)
    return "\n\n".join(parts)


def ingest_file_for_rag(
    path: str, *, persist_directory: str, source_name: Optional[str] = None
) -> int:
    """
    Ingest a local file (PDF/PPTX/TXT) into the vector store.

    Returns the number of chunks added.
    """
    docs = _load_file(path)
    for d in docs:
        d.metadata = d.metadata or {}
        if source_name:
            d.metadata.setdefault("source", source_name)
    splits = _text_splitter.split_documents(docs)
    vs = _get_vectorstore(persist_directory)
    vs.add_documents(splits)
    # Ensure data is flushed to disk for persistence.
    vs.persist()
    return len(splits)


def ingest_url_for_rag(
    url: str, *, persist_directory: str, source_name: Optional[str] = None
) -> int:
    """
    Ingest the contents of a URL into the vector store.
    """
    if not url:
        return 0
    loader = WebBaseLoader([url])
    docs = loader.load()
    for d in docs:
        d.metadata = d.metadata or {}
        d.metadata.setdefault("url", url)
        if source_name:
            d.metadata.setdefault("source", source_name)
    splits = _text_splitter.split_documents(docs)
    vs = _get_vectorstore(persist_directory)
    vs.add_documents(splits)
    # Ensure data is flushed to disk for persistence.
    vs.persist()
    return len(splits)


def _has_any_documents(*, persist_directory: str) -> bool:
    vs = _get_vectorstore(persist_directory)
    try:
        return vs._collection.count() > 0  # type: ignore[attr-defined]
    except Exception:
        # Fallback if underlying API changes
        docs = vs.similarity_search("test", k=1)
        return len(docs) > 0


def generate_quiz(*, persist_directory: str, num_questions: int = 5) -> str:
    """
    Generate a multiple-choice quiz in Markdown based on the ingested sources.
    """
    if num_questions <= 0:
        return "Please request at least one question."

    if not _has_any_documents(persist_directory=persist_directory):
        return "No sources have been ingested into the quiz engine yet. Upload a PDF/PPTX/TXT or ingest a URL first."

    vs = _get_vectorstore(persist_directory)
    retriever = vs.as_retriever(search_kwargs={"k": 12})

    # Use a broad query to pull representative chunks across the corpus.
    docs = retriever.invoke(
        "key concepts, main ideas, and important facts from all documents"
    )
    if not docs:
        return "Unable to retrieve content from the ingested sources to build a quiz."

    context = "\n\n".join(d.page_content for d in docs)

    prompt = f"""
You are a tutor generating a quiz for a student.

Use ONLY the information in the context below to create {num_questions} high‑quality multiple‑choice questions.

Each question should:
- Focus on an important concept or fact.
- Have 4 options labeled A, B, C, D.
- Clearly indicate the correct answer.
- Include a short explanation of why the correct option is right.

Return the quiz in Markdown with this format:

Q1. Question text
A. Option text
B. Option text
C. Option text
D. Option text
**Answer:** X
**Explanation:** ...

(then continue with Q2, Q3, etc.)

Context:
\"\"\"{context}\"\"\"
"""

    llm = _get_llm()
    response = llm.invoke(prompt)
    content = getattr(response, "content", None)
    if not content:
        content = str(response)
    return content


def chat_with_sources(
    question: str,
    *,
    persist_directory: str,
    history: List[List[str]] | List[tuple[str, str]] | None = None,
) -> str:
    """
    Answer a user question using RAG over the ingested sources.

    - `question`: current user message.
    - `history`: chat history as [[user, assistant], ...] or list of tuples.
    """
    question = (question or "").strip()
    if not question:
        return "Please enter a question."

    if not _has_any_documents(persist_directory=persist_directory):
        return "No sources have been ingested yet. Upload a PDF/PPTX/TXT or ingest a URL first."

    vs = _get_vectorstore(persist_directory)
    retriever = vs.as_retriever(search_kwargs={"k": 6})

    docs = retriever.invoke(question)
    if not docs:
        return "I could not find relevant information in your ingested sources for that question."

    context = "\n\n".join(d.page_content for d in docs)

    # Keep only the last few turns to keep the prompt compact.
    history = history or []
    turns: List[str] = []
    for h in history[-4:]:
        try:
            user_msg, assistant_msg = h
        except ValueError:
            continue
        turns.append(f"User: {user_msg}")
        turns.append(f"Assistant: {assistant_msg}")
    history_str = "\n".join(turns) if turns else "No previous conversation."

    prompt = f"""
You are a helpful assistant answering questions based ONLY on the provided context.
If the answer is not in the context, say you don't know and suggest the user add more sources.

Conversation so far:
{history_str}

User question: "{question}"

Context from the user's documents:
\"\"\"
{context}
\"\"\"

Provide a clear, concise answer grounded in the context.
"""

    llm = _get_llm()
    response = llm.invoke(prompt)
    content = getattr(response, "content", None)
    if not content:
        content = str(response)
    return content


from datetime import datetime


def generate_report(
    *,
    persist_directory: str,
    title: str = "Report",
    focus_prompt: str = "",
    k: int = 18,
) -> str:
    """
    Generate a markdown report grounded in ingested sources.
    Includes citations like [S1], [S2], ... and a Sources section.
    """
    if not _has_any_documents(persist_directory=persist_directory):
        return "No sources have been ingested yet. Upload a PDF/PPTX/TXT or ingest a URL first."

    vs = _get_vectorstore(persist_directory)
    retriever = vs.as_retriever(search_kwargs={"k": k})

    docs = retriever.invoke(
        "main topics, key concepts, important facts, and conclusions across all sources"
    )
    if not docs:
        return "Unable to retrieve content from the ingested sources to build a report."

    labeled_chunks = []
    sources_lines = []

    for i, d in enumerate(docs, start=1):
        tag = f"S{i}"
        meta = getattr(d, "metadata", {}) or {}
        source = meta.get("source") or meta.get("file_path") or meta.get("url") or "unknown"
        page = meta.get("page", None)
        url = meta.get("url", None)

        label_bits = [str(source)]
        if page is not None:
            label_bits.append(f"page {page}")
        if url and url != source:
            label_bits.append(str(url))

        sources_lines.append(f"- **[{tag}]** {', '.join(label_bits)}")

        chunk = (getattr(d, "page_content", "") or "").strip()
        if chunk:
            labeled_chunks.append(f"[{tag}] {chunk}")

    context_str = "\n\n".join(labeled_chunks)
    sources_md = "## Sources\n" + "\n".join(sources_lines)

    ts = datetime.utcnow().isoformat() + "Z"
    focus_prompt = (focus_prompt or "").strip()
    focus_line = f"\nUser focus request: {focus_prompt}\n" if focus_prompt else ""

    prompt = f"""
You are generating a study report for a student.

RULES:
- Use ONLY the information in the context.
- Every non-trivial claim MUST include citations like [S1], [S2], etc.
- If something is not supported by the context, say so. Do not guess.

Return Markdown in this structure:

# {title}
- Generated: {ts}

## Executive Summary

## Key Concepts

## Detailed Notes

## Takeaways

Append the Sources section at the end.

{focus_line}

CONTEXT:
\"\"\"{context_str}\"\"\"
""".strip()

    llm = _get_llm()
    response = llm.invoke(prompt)
    content = getattr(response, "content", None) or str(response)

    if "## Sources" not in content:
        content = content.rstrip() + "\n\n" + sources_md + "\n"

    return content