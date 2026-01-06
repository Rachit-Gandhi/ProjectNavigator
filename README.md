# Controlled RAG

A pragmatic scaffold for building multi-project retrieval augmented generation
systems. The current repository ships two completed phases and leaves Phase 3
(Router + RAG brains) open for your custom logic.

## Current State

1. **Phase 1 – Platform Skeleton**
   - Project folders laid out under `data/`
   - Configurable ingestion rules in `config/ingestion_rules.yaml`
   - Poetry/pyproject dependencies for FastAPI + LangChain
2. **Phase 2 – Backend Plumbing**
   - `/v1/ingest` endpoint discovers projects, tags files, and surfaces previews
   - `/v1/chat` endpoint handles sessions, `/clear`, and `@tag` filters
   - `/v1/session/lock` allows explicit project locking
   - In-memory registries + session store to keep the logic stateful

Everything required to expose an API-backed chat workflow already exists. What
remains is plugging in the actual intelligence (Phase 3).

## Phase 3 – LangChain-Brained Router + RAG

The backend now assumes **LangChain v1.0 style components**. No local-only
Ollama coupling remains. You can attach any API-backed model (OpenAI, Gemini,
Bedrock, etc.) via LangChain wrappers.

### Step 1: Build a Retriever

Create a module (e.g., `src/core/vectorstore.py`) that:

- Reads the `ProjectPlan` objects produced by `ingest.plan_all_projects`
- Writes embeddings to a vector store (Chroma, PGVector, Elastic)
- Exposes `def build_retriever(project_id: str, filters: Optional[Sequence[str]])`
  that returns a `BaseRetriever` limited to that project + tag filters
- Stores `doc.metadata["source"]` for accurate citations

### Step 2: Configure the RAG Pipeline

`src/core/rag.py` now exports `LangChainRagConfig` and `configure_pipeline`.
Call it once during startup (e.g., inside a FastAPI `startup` event or a custom
initializer):

```python
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from src.core import rag
from .retrievers import build_retriever

prompt = ChatPromptTemplate.from_messages([
    ("system", "You answer with verified facts and cite sources."),
    ("human", "Question: {question}\n\nContext:\n{context}"),
])

rag.configure_pipeline(
    rag.LangChainRagConfig(
        llm_factory=lambda: ChatOpenAI(model="gpt-4o", temperature=0),
        retriever_factory=build_retriever,
        prompt=prompt,
    )
)
```

`/v1/chat` will now call your configured pipeline for every request.

### Step 3: Implement the Router

In `src/core/router.py`, decide how to select the project:

- Simple approach: embed `ProjectPlan.description` values and compare cosine
  similarity to the user query
- Fancy approach: LangChain `MultiQueryRetriever` or a custom LLM prompt that
  reasons over project summaries
- When ambiguous, return a list and have the API prompt the user to choose

### Step 4: (Optional) Advanced Filters

`@tags` extracted by the API are already passed to `retriever_factory`. Use them
as metadata filters to focus on proposal docs, requirements, etc.

## Running the Server

```bash
python -m pip install --upgrade pip
pip install .
python main.py  # starts uvicorn on port 8000
```

Use the API:

1. `POST /v1/ingest` – discover/tag all projects
2. `POST /v1/chat` with `session_id`, `message`, `auto_lock=true`
3. Implement `/v1/chat` UI later; API is stable already

## Notes

- No embeddings or LLM calls happen until you supply the LangChain pipeline
- The design intentionally keeps abstractions boring so you can ship quickly
- Treat this repo as your backend foundation; bring your own GenAI creativity

Happy shipping.
