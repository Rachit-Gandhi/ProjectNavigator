# Plan-Phase1.md  
## Layered RAG Approach for Large-Scale Project Document Search  
_Pre–Knowledge Graph, Pre–Client Constraints_

---

## 1. Problem Statement (Core)

We are **not** building:
- Code search  
- Simple keyword search  
- Flat “dump everything into a vector DB and pray” RAG  

We **are** solving this:

- An organization has **thousands of projects**
- Each project contains **hundreds of unstructured documents** (PDF, DOCX, etc.)
- Users ask **underspecified, vague questions**
- The system must:
  - Identify the **correct project**
  - Identify the **correct document**
  - Identify the **correct section**
  - Ask the **minimum number of clarifying questions**
  - **Avoid cross-project contamination by default**

This is a **decision-guided retrieval problem**, not vanilla RAG.

---

## 2. Key Insight

Plain RAG fails because it:

- Flattens all documents into a single embedding space
- Destroys hierarchy (project → document → section)
- Over-fetches irrelevant context
- Hallucinates confidence far too early

The correct mental model is:

> **Entropy reduction over a structured document space**

We narrow the search space step by step, just like a competent human would.

---

## 3. Core Architectural Idea: Layered (Hierarchical) RAG

Instead of one massive vector index, we use **multiple semantic layers**, each with a clearly defined responsibility.

Each layer:
- Narrows scope
- Decides whether to proceed or ask **one** clarifying question
- Passes context downward

---

## 4. Layer 1: Project Layer (Coarse)

### Purpose
Determine **which project(s)** the user’s question belongs to.

### Data Representation
For each project, generate a **Project Profile**:
- High-level project summary
- Dominant themes
- Types of documents present (contracts, proposals, reports, etc.)

Only these summaries are embedded.

### Retrieval Behavior
- Query → project embeddings
- Reduce from **thousands of projects → 1–2 candidates**

### Clarification Trigger
If top candidates are close or semantically distinct:
- Ask **one** targeted question

**Example**:
> “Which client or project is this related to?”

---

## 5. Layer 2: Document Layer (Medium)

### Purpose
Determine **which document** inside the selected project is relevant.

### Data Representation
For each document:
- Document type (proposal, contract, RFI, report, etc.)
- Short semantic summary
- Key topics covered

Embed **document descriptors**, not full text.

### Retrieval Behavior
- Narrow from **dozens/hundreds → 1–3 documents**

### Clarification Trigger
If ambiguity remains:
- Ask **one** focused question tied to document intent

**Example**:
> “Is this about contractual penalties or proposal scope?”

---

## 6. Layer 3: Section Layer (Fine)

### Purpose
Pinpoint **where inside the document** the answer lives.

### Data Representation
Documents are segmented into **logical sections**, not blind chunks:
- Section title or inferred label
- Page range
- Parent document ID
- Parent project ID
- Section text embedding

### Retrieval Behavior
- Returns:
  - Document name
  - Page number(s)
  - Exact excerpt
- Optional light RAG for explanation or summarization

---

## 7. Clarifying Questions as a First-Class Mechanism

Clarifying questions are **not** fallback UX.

They are triggered when:
- Retrieval scores are close
- Candidates belong to different semantic branches

### Rules
- At most **one question per layer**
- Questions must **maximally reduce ambiguity**
- Never ask generic “Can you clarify?” questions

Good questions split the tree cleanly.

---

## 8. Why This Approach Works

- Preserves hierarchy and context
- Prevents cross-project leakage
- Minimizes hallucination
- Matches how humans search institutional knowledge
- Scales cleanly without flattening everything
- Keeps answers **traceable and explainable**

---

## 9. Phase 1 Scope Boundary

Phase 1 explicitly **excludes**:
- Knowledge graphs
- Cross-project synthesis
- Agentic planning across projects
- Code intelligence

This phase proves:
> Decision-guided, hierarchical narrowing works better than flat RAG.

---

_End of Phase 1_
