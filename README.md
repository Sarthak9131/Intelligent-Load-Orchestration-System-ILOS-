# 🏦 Loan Processing Multi-Agent System

> **A synthetic loan-processing prototype using Google ADK — sequential pipelines, parallel checks, and a sequential review chain**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Google ADK](https://img.shields.io/badge/Google%20ADK-0.4+-green.svg)](https://google.github.io/adk-docs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Agent Coordination Patterns](#agent-coordination-patterns)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Running the Demo](#running-the-demo)
- [Running Tests](#running-tests)
- [Performance Metrics](#performance-metrics)
- [Extending the System](#extending-the-system)
- [Interview Preparation](#interview-preparation)
- [Practical AI/ML Roadmap](#practical-aiml-roadmap)

---

## Architecture Overview

The system processes a loan application through **three sequential phases**, each using a different coordination pattern:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     LOAN PROCESSING ORCHESTRATOR                         │
│                                                                          │
│  Phase 1 (Sequential)     Phase 2 (Parallel)     Phase 3 (Sequential)   │
│  ┌─────────────────┐      ┌─────────────────┐    ┌─────────────────┐    │
│  │ DocumentIntake  │      │ IncomeAnalysis  │    │  RiskAnalyst    │    │
│  └────────┬────────┘      ├─────────────────┤    └────────┬────────┘    │
│           ↓               │ CreditAssessmt  │             ↓             │
│  ┌─────────────────┐      ├─────────────────┤    ┌─────────────────┐    │
│  │ DataExtraction  │  ──► │ EmploymentRisk  │    │ ComplianceRvwr  │    │
│  └────────┬────────┘      ├─────────────────┤    └────────┬────────┘    │
│           ↓               │ CollateralEval  │             ↓             │
│  ┌─────────────────┐      └─────────────────┘    ┌─────────────────┐    │
│  │  Validation     │                             │ FinalUnderwriter│    │
│  └─────────────────┘                             └─────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Agent Coordination Patterns

### 1. Sequential Pipeline (Phase 1 & 3)
Used when each step **depends on the previous step's output**.

```python
document_processing_pipeline = SequentialAgent(
    name="DocumentProcessingPipeline",
    sub_agents=[document_intake_agent, data_extraction_agent, validation_agent]
)
```

**Why sequential?**  
You can't extract data before documents are organised, and can't validate before data is extracted.

### 2. Parallel Team (Phase 2)
Used when analyses are **independent and can run simultaneously**.

```python
risk_assessment_team = ParallelAgent(
    name="RiskAssessmentTeam",
    sub_agents=[income_analysis_agent, credit_assessment_agent,
                employment_risk_agent, collateral_evaluation_agent]
)
```

**Why parallel?**  
Income, credit, employment, and collateral analyses don't depend on each other.  
They can run concurrently; actual end-to-end latency depends on provider response
times, orchestration overhead, and failures. This repository does not claim a
measured speedup.

### 3. Sequential Decision Chain (Phase 3)
The approval workflow is a **sequential decision chain** where each level runs
after and can use the prior review's output. It is not a separate authority
handoff protocol.

```
RiskAnalyst → ComplianceReviewer → FinalUnderwriter
```

Risk analyst → compliance reviewer → final underwriter.

---

## Quick Start

### Prerequisites

- Python 3.11+
- An API key for one of: Anthropic, OpenAI, or Google

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/loan-processing-multiagent.git
cd loan-processing-multiagent

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env and add your API key
```

---

## Project Structure

```
loan-processing-multiagent/
├── src/
│   ├── __init__.py
│   ├── models.py               # Data models (LoanApplication, ProcessingResult, etc.)
│   ├── orchestrator.py         # Master coordinator — ties all phases together
│   └── agents/
│       ├── __init__.py
│       ├── document_pipeline.py   # Phase 1: Sequential document processing
│       ├── risk_team.py           # Phase 2: Parallel risk assessment
│       └── approval_workflow.py   # Phase 3: Sequential approval chain
├── tests/
│   └── test_loan_processing.py
├── docs/
│   └── architecture.md
├── config/
│   └── settings.py
├── main.py                     # Demo with 3 test cases + analytics dashboard
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Configuration

Copy `.env.example` to `.env` and set your API key:

```env
# For Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=anthropic/claude-sonnet-4-6

# LiteLLM provider/model identifier; the configured default is:
LLM_MODEL=anthropic/claude-sonnet-4-6
```

---

## Running the Demo

```bash
python main.py
```

This processes three applicants covering the full risk spectrum:

| Applicant | Income | Credit | Expected Decision |
|-----------|--------|--------|------------------|
| Sarah Chen | $165,000 | 785 | ✅ APPROVED |
| Marcus Williams | $68,000 | 720 | ⚠️ CONDITIONALLY APPROVED |
| Robert Martinez | $38,400 | 580 | ❌ REJECTED |

Results are saved to `results.json`.

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

---

---

## Extending the System

### Add a new risk agent

1. Define your agent in `src/agents/risk_team.py`
2. Add it to the `ParallelAgent` sub-agents list
3. Update the aggregator's weighting accordingly

### Swap the LLM

Change `LLM_MODEL` in `.env`:

```env
LLM_MODEL=openai/gpt-4o          # OpenAI
LLM_MODEL=gemini/gemini-1.5-pro  # Google Gemini
LLM_MODEL=anthropic/claude-opus-4 # Anthropic Opus
```

### Scale to production

For high-volume deployments:

- Replace `InMemorySessionService` with a Redis-backed session store
- Deploy each agent phase as an independent Kubernetes service
- Add Prometheus metrics scraping from `get_performance_dashboard()`
- Integrate with your core banking system via REST adapters

## Interview Preparation

Use [docs/interview-prep.md](docs/interview-prep.md) as a project-grounded study plan for AI/ML engineering interviews. It includes a concise architecture walkthrough, Python and ML fundamentals, LLM production concerns, likely questions, project gaps to discuss honestly, and a four-week practice plan.

For a hands-on progression from Python foundations to senior-level system design, follow [docs/practical-ai-ml-roadmap.md](docs/practical-ai-ml-roadmap.md). Start with its first lab and share your implementation for review.

---

## License

MIT — see [LICENSE](LICENSE)

---

## Acknowledgements

Architecture patterns inspired by enterprise implementations at major financial institutions.  
Built with [Google ADK](https://google.github.io/adk-docs/) and [LiteLLM](https://litellm.ai/).
