"""LangChain-powered RAG scaffolding.

This module intentionally avoids binding to a specific LLM vendor. Instead it
exposes ``configure_pipeline`` so you can inject whichever LangChain stack you
prefer (OpenAI, Gemini, Bedrock, etc.). The HTTP API calls ``generate_answer``
which, in turn, delegates to the configured pipeline.

Example usage during startup:

>>> from langchain_openai import ChatOpenAI
>>> from langchain_core.prompts import ChatPromptTemplate
>>> from your_project.retrievers import build_retriever
>>> from src.core.rag import LangChainRagConfig, configure_pipeline
>>>
>>> prompt = ChatPromptTemplate.from_messages([
...     ("system", "You are a project-specific assistant. Cite sources."),
...     ("human", "Question: {question}\n\nContext:\n{context}"),
... ])
>>> config = LangChainRagConfig(
...     llm_factory=lambda: ChatOpenAI(model="gpt-4o"),
...     retriever_factory=build_retriever,
...     prompt=prompt,
... )
>>> configure_pipeline(config)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever

DEFAULT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a precise assistant. Respond using only the supplied context. "
            "List the source for each fact as [source].",
        ),
        (
            "human",
            "Question: {question}\n\nContext:\n{context}",
        ),
    ]
)


@dataclass
class LangChainRagConfig:
    """Dependency bundle for the LangChain pipeline."""

    llm_factory: Callable[[], BaseLanguageModel]
    retriever_factory: Callable[[str, Optional[Sequence[str]]], BaseRetriever]
    prompt: ChatPromptTemplate = DEFAULT_PROMPT
    context_formatter: Optional[Callable[[Iterable[Document]], str]] = None

    def render_context(self, documents: Iterable[Document]) -> str:
        formatter = self.context_formatter or format_documents
        return formatter(documents)


_config: Optional[LangChainRagConfig] = None


def configure_pipeline(config: LangChainRagConfig) -> None:
    """Register the LangChain configuration used by ``generate_answer``."""

    global _config
    _config = config


def generate_answer(
    *,
    session_id: str,
    project_id: str,
    message: str,
    filters: Optional[List[str]] = None,
) -> str:
    if _config is None:
        raise RuntimeError(
            "LangChain pipeline is not configured. Call configure_pipeline() during startup."
        )

    retriever = _config.retriever_factory(project_id, filters)
    documents = retriever.get_relevant_documents(message)
    context = _config.render_context(documents)

    prompt_value = _config.prompt.format_prompt(question=message, context=context)
    llm = _config.llm_factory()
    response = llm.invoke(prompt_value.to_messages())
    return getattr(response, "content", str(response))


def format_documents(documents: Iterable[Document]) -> str:
    """Default context renderer used by the prompt."""

    formatted: List[str] = []
    for doc in documents:
        source = doc.metadata.get("source") if isinstance(doc.metadata, dict) else None
        header = f"[source: {source}]" if source else "[source: unknown]"
        formatted.append(f"{header}\n{doc.page_content}")
    if not formatted:
        formatted.append("[source: none]\nNo matching context found.")
    return "\n\n".join(formatted)


__all__ = [
    "LangChainRagConfig",
    "configure_pipeline",
    "generate_answer",
    "format_documents",
]
