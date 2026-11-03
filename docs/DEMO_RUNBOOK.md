# NexusAI Enterprise Copilot — Comprehensive Demonstration Runbook

> **Audience:** Technical Evaluators, Hiring Managers, Enterprise Architects, and QA Leads  
> **Purpose:** Step-by-step, 100% reproducible demonstration guide exercising all core capabilities of NexusAI via both the React Web Dashboard and REST API `curl` commands.  
> **Master Blueprint Reference:** Version 1.0 (Day 10: *Demo & documentation*, Section 18: *Acceptance checklist*, Section 19: *Portfolio package*)

---

## 1. Environment Setup & Quickstart

NexusAI can be launched in two ways: via **Docker Compose (Production Multi-Container)** or **Local Bare-Metal Development**.

### Option A: Docker Compose (Recommended)
```bash
# 1. Build and boot backend (port 8000) and frontend (port 3000)
docker compose up --build -d

# 2. Verify services are healthy
curl -s http://localhost:8000/api/v1/health

# 3. Access web dashboard in your browser
# URL: http://localhost:3000
# Interactive API Swagger: http://localhost:8000/docs
```

### Option B: Local Developer Execution
```powershell
# Terminal 1: Launch FastAPI Backend (Port 8000)
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Launch Vite React Frontend (Port 3000)
npm --prefix frontend run dev
```

---

## 2. Seed Demo Sample Documents

Pre-configured synthetic corporate documents are located in `data/demo_samples/`:
1. `cloud_infrastructure_sla.txt`: 99.95% uptime guarantees, P1-P4 SLAs (P1 < 15 mins), credit tiers, and escalation pathways.
2. `enterprise_security_travel_policy.pdf`: Multi-page corporate policy detailing $120 travel per diems, capital expense approvals under `PROC-889` ($>\$50{,}000$ CFO approval), and device encryption rules.
3. `vendor_master_services_agreement.docx`: Enterprise vendor agreement detailing indemnity, $1,000,000 liability caps, and 30-day material breach cure periods.

---

## 3. Seven Scripted Demonstration Scenarios

```
+--------------------------------------------------------------------------------------------------------+
|                                      NexusAI Demo User Journeys                                        |
+--------------------------------------------------------------------------------------------------------+
|  [Scenario 1] Upload Documents (PDF, DOCX, TXT) ---> Dual Indexing (ChromaDB + BM25)                 |
|  [Scenario 2] Grounded Q&A ---> Citation Pills ---> Click-to-Verify Source Inspector Sidecar           |
|  [Scenario 3] Contextual Multi-Turn Conversation ---> Referential Pronoun Expansion                    |
|  [Scenario 4] Executive Summarization Workflow ---> Structured Purpose, Provisions, Constraints       |
|  [Scenario 5] Structured Risk & Liability Extraction ---> High/Medium/Low Severity Classification       |
|  [Scenario 6] Negative Abstention Gate ---> Irrelevant Query Refusal (Zero Hallucination)              |
|  [Scenario 7] Live 4-Way Retrieval Ablation ---> Dense vs. Sparse vs. Hybrid vs. Cross-Encoder        |
+--------------------------------------------------------------------------------------------------------+
```

---

### Scenario 1: Multi-Format Document Ingestion & Catalog Verification

**Goal:** Upload heterogeneous enterprise file formats (PDF, DOCX, TXT), perform stream validation, extract text, chunk page-by-page, compute SHA-256 deduplication hashes, and index simultaneously into dense ChromaDB and sparse BM25.

#### UI Interaction:
1. Navigate to **Documents** in the top navigation bar (`http://localhost:3000/documents`).
2. Drag and drop `data/demo_samples/enterprise_security_travel_policy.pdf` into the upload zone.
3. Repeat for `data/demo_samples/vendor_master_services_agreement.docx` and `data/demo_samples/cloud_infrastructure_sla.txt`.
4. Observe real-time upload progress badges and inspect the document table showing chunk counts and active statuses.

#### API CLI Verification (`curl`):
```bash
# Upload Policy PDF
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@data/demo_samples/enterprise_security_travel_policy.pdf"

# Upload Vendor DOCX
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@data/demo_samples/vendor_master_services_agreement.docx"

# List indexed documents
curl -s http://localhost:8000/api/v1/documents
```

**Expected JSON Response:**
```json
{
  "documents": [
    {
      "id": "doc_...",
      "filename": "enterprise_security_travel_policy.pdf",
      "file_type": "pdf",
      "chunk_count": 4,
      "status": "indexed"
    }
  ]
}
```

---

### Scenario 2: Grounded Q&A with Click-to-Verify Citation Sidecar

**Goal:** Ask an exact policy question, receive a factual answer grounded strictly in retrieved context, inspect citation badges, and open the slide-over source inspector sidecar to view verbatim quote highlights.

#### UI Interaction:
1. Navigate to **Chat** (`http://localhost:3000/chat`).
2. Type query into prompt box:
   > *"What is the capital expense approval limit under financial procedure PROC-889?"*
3. Press **Enter**.
4. Observe:
   - Assistant generates a grounded answer citing the CFO sign-off threshold.
   - Citation pill appears: `[Quote enterprise_security_travel_policy.pdf (p.1)]`.
   - Route breadcrumb displays: `classify_query -> retrieve_and_rerank -> generate_qa`.
5. Click the citation pill.
6. The **Source Inspector Sidecar Modal** slides open, displaying:
   - Document: `enterprise_security_travel_policy.pdf`, Page 1.
   - Verbatim rolling n-gram direct quote highlighted in green: *"Any capital expenditure exceeding $50,000 strictly requires explicit CFO and Finance Committee sign-off."*

#### API CLI Verification (`curl`):
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the capital expense approval limit under financial procedure PROC-889?",
    "top_k": 3
  }'
```

**Expected JSON Response:**
```json
{
  "answer": "Under financial procedure PROC-889, purchases between $10,000 and $50,000 require Department VP approval, while any capital expenditure exceeding $50,000 strictly requires explicit CFO and Finance Committee sign-off.",
  "citations": [
    {
      "chunk_id": "c_...",
      "document_name": "enterprise_security_travel_policy.pdf",
      "page_number": 1,
      "is_direct_quote": true
    }
  ],
  "insufficient_evidence": false
}
```

---

### Scenario 3: Contextual Multi-Turn Conversation

**Goal:** Demonstrate conversational memory and referential pronoun expansion across multiple conversational turns.

#### UI Interaction:
1. In the **Chat** view, ask:
   > *"What are the incident response time SLAs for cloud services?"*
2. Follow up immediately with an anaphoric query:
   > *"What is the response window specifically for P1 critical outages and what happens if it is missed?"*
3. Observe that the copilot correctly contextualizes the pronoun *"it"* to refer to the P1 incident SLA, identifying both the 15-minute response window and the automatic escalation pathway.

#### API CLI Verification (`curl`):
```bash
# 1. Create a conversation session
CONV_ID=$(curl -s -X POST http://localhost:8000/api/v1/conversations | grep -o '"id":"[^"]*' | cut -d'"' -f4)

# 2. Ask Turn 1
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "'$CONV_ID'",
    "query": "What are the response time SLAs for cloud incidents?"
  }'

# 3. Ask Turn 2 (Anaphoric follow-up)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "'$CONV_ID'",
    "query": "What is the response window specifically for P1 critical outages and what happens if it is missed?"
  }'
```

---

### Scenario 4: Executive Summarization Workflow

**Goal:** Execute a structured, document-scoped executive summarization workflow using LangGraph DAG routing.

#### UI Interaction:
1. In **Documents**, click the **Summarize** button on `vendor_master_services_agreement.docx` (or in **Chat**, toggle the `Summary` routing pill).
2. The assistant returns a structured executive brief organized into:
   - **Executive Purpose:** Commercial engagement framework for cloud engineering and software services.
   - **Key Provisions:** Net 30 payment terms, 1.0% late interest, IP retention.
   - **Requirements & Constraints:** 60-day notice for convenience termination, 30-day cure window for material breach.

#### API CLI Verification (`curl`):
```bash
# Obtain doc_id from /api/v1/documents
DOC_ID=$(curl -s http://localhost:8000/api/v1/documents | grep -o '"id":"[^"]*' | head -n1 | cut -d'"' -f4)

curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/summarize
```

---

### Scenario 5: Structured Risk & Liability Extraction Workflow

**Goal:** Extract legal, operational, and financial liabilities with structured severity categorization (High, Medium, Low).

#### UI Interaction:
1. In **Documents**, click the **Extract Risks** button on `vendor_master_services_agreement.docx` (or in **Chat**, select the `Risks` workflow mode).
2. The assistant analyzes contract clauses and outputs structured risk cards:
   - **High Severity:** $1,000,000 aggregate liability cap excluding willful misconduct; indemnification obligations for third-party IP infringement.
   - **Medium Severity:** 30-day cure window before termination for cause takes effect.
   - **Low Severity:** 1% monthly interest on late invoice payments.

#### API CLI Verification (`curl`):
```bash
curl -X POST http://localhost:8000/api/v1/documents/$DOC_ID/risks
```

---

### Scenario 6: Negative Abstention Gate (Zero Hallucination Verification)

**Goal:** Test the copilot with a domain query that is completely unmentioned in the ingested document corpus to verify that it refuses to speculate.

#### UI Interaction:
1. In **Chat**, type:
   > *"What is the corporate policy regarding employee stock option vesting schedules and equity grants?"*
2. Press **Enter**.
3. Observe:
   - The assistant **strictly abstains**: *"I do not have sufficient information in the provided documents."*
   - A high-visibility amber alert banner is rendered: `⚠️ Insufficient Evidence: Evidence score fell below threshold (logit < -6.0). Copilot refused to speculate.`
   - No hallucinated source citations are presented.

#### API CLI Verification (`curl`):
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the corporate policy regarding employee stock option vesting schedules and equity grants?",
    "top_k": 3
  }'
```

**Expected JSON Response:**
```json
{
  "answer": "I do not have sufficient information in the provided documents to answer this question.",
  "citations": [],
  "insufficient_evidence": true
}
```

---

### Scenario 7: Live 4-Way Retrieval Ablation Benchmark Execution

**Goal:** Benchmark Information Retrieval accuracy across 4 distinct retrieval architectures using the golden evaluation dataset.

#### UI Interaction:
1. Navigate to **Evaluation** (`http://localhost:3000/evaluation`).
2. Click **Run 4-Way Ablation Benchmark**.
3. Observe real-time execution across the 25 golden test cases.
4. Inspect the comparative results table:
   - **Dense-Only (`all-MiniLM-L6-v2`):** Strong paraphrase understanding; struggles with exact IDs.
   - **Sparse-Only (BM25):** 100% precision on exact codes (`PROC-889`); fails on semantic synonyms.
   - **Hybrid RRF ($k=60$):** Fuses dense and sparse rankings, significantly boosting Recall@5.
   - **Cross-Encoder Reranked (`ms-marco-MiniLM-L-6-v2`):** Top-performing architecture with highest MRR and MAP@5.

#### API CLI Verification (`curl`):
```bash
# Run 4-way retrieval ablation
curl -s http://localhost:8000/api/v1/evaluation/ablation
```

---

## 4. Evaluator Clean-Up

To reset the environment after completing demonstration testing:
```bash
# Docker Compose: Tear down containers and wipe transient storage
docker compose down -v

# Local Bare-Metal: Remove data directory contents if desired
rm -rf data/uploads/* data/chroma/* data/bm25/* data/conversations/*
```

