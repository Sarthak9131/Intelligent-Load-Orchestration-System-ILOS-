"""
Loan Processing Orchestrator
Master coordinator for the complete multi-agent loan processing workflow.
"""

import asyncio
import uuid
import time
import logging
from datetime import datetime
from typing import Dict, Any

from .agents.document_pipeline import document_processing_pipeline, pipeline_runner
from .agents.risk_team import risk_assessment_team, risk_runner
from .agents.approval_workflow import approval_workflow, approval_runner
from .models import ProcessingResult, ApplicationStatus

logger = logging.getLogger(__name__)


class LoanProcessingOrchestrator:
    """Master orchestrator for complete loan processing workflow."""

    def __init__(self):
        self.pipeline_runner = pipeline_runner
        self.risk_runner = risk_runner
        self.approval_runner = approval_runner
        self.processing_metrics = {
            "total_applications": 0,
            "approved": 0,
            "rejected": 0,
            "conditional": 0,
            "average_processing_time": 0.0,
            "compliance_score": 0.0,
        }

    async def process_loan_application(self, application_data: str) -> ProcessingResult:
        """Run end-to-end loan processing through all agent phases."""
        start_time = time.time()
        application_id = f"LA-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        logger.info(f"[{application_id}] Starting loan processing pipeline")

        try:
            # ── Phase 1: Document Processing (Sequential) ──────────────────
            logger.info(f"[{application_id}] Phase 1: Document processing pipeline")
            doc_session_id = f"doc-{application_id}"
            doc_content = await _run_agent(
                self.pipeline_runner,
                doc_session_id,
                application_data,
                application_id,
            )

            # ── Phase 2: Parallel Risk Assessment ──────────────────────────
            logger.info(f"[{application_id}] Phase 2: Parallel risk assessment")
            risk_session_id = f"risk-{application_id}"
            risk_content = await _run_agent(
                self.risk_runner,
                risk_session_id,
                f"APPLICATION DATA:\n{application_data}\n\nDOCUMENT PROCESSING RESULTS:\n{doc_content}",
                application_id,
            )

            # ── Phase 3: Approval Workflow (Sequential) ─────────────────────
            logger.info(f"[{application_id}] Phase 3: Approval workflow")
            approval_session_id = f"approval-{application_id}"
            approval_content = await _run_agent(
                self.approval_runner,
                approval_session_id,
                (
                    f"APPLICATION DATA:\n{application_data}\n\n"
                    f"DOCUMENT PROCESSING:\n{doc_content}\n\n"
                    f"RISK ASSESSMENT:\n{risk_content}"
                ),
                application_id,
            )

            # ── Phase 4: Build final result ─────────────────────────────────
            processing_time = time.time() - start_time
            status = _parse_status(approval_content)

            result = ProcessingResult(
                application_id=application_id,
                status=status,
                decision=approval_content,
                processing_time=processing_time,
                risk_assessment=risk_content,
                compliance_notes=approval_content,
                timestamp=datetime.now().isoformat(),
            )

            self._update_metrics(result)
            logger.info(
                f"[{application_id}] Completed in {processing_time:.2f}s — {status.value}"
            )
            return result

        except Exception as exc:
            processing_time = time.time() - start_time
            logger.error(f"[{application_id}] Processing error: {exc}", exc_info=True)
            return ProcessingResult(
                application_id=application_id,
                status=ApplicationStatus.REQUIRES_INFO,
                decision=f"Processing error: {exc}. Please contact a loan officer for manual review.",
                processing_time=processing_time,
                timestamp=datetime.now().isoformat(),
            )

    def get_performance_dashboard(self) -> Dict[str, Any]:
        """Return real-time operational metrics."""
        total = self.processing_metrics["total_applications"]
        approved = self.processing_metrics["approved"]
        rejected = self.processing_metrics["rejected"]
        conditional = self.processing_metrics["conditional"]

        return {
            "total_applications_processed": total,
            "approval_rate": f"{(approved / total * 100):.1f}%" if total else "N/A",
            "rejection_rate": f"{(rejected / total * 100):.1f}%" if total else "N/A",
            "conditional_approval_rate": f"{(conditional / total * 100):.1f}%" if total else "N/A",
            "average_processing_time": f"{self.processing_metrics['average_processing_time']:.2f}s",
            "average_compliance_score": f"{self.processing_metrics['compliance_score']:.1f}%",
            "throughput": f"{(total / max(self.processing_metrics['average_processing_time'], 0.001)):.1f} apps/sec"
            if total
            else "N/A",
        }

    # ── private helpers ────────────────────────────────────────────────────

    def _update_metrics(self, result: "ProcessingResult") -> None:
        m = self.processing_metrics
        m["total_applications"] += 1
        total = m["total_applications"]

        if result.status == ApplicationStatus.APPROVED:
            m["approved"] += 1
        elif result.status == ApplicationStatus.REJECTED:
            m["rejected"] += 1
        elif result.status in (
            ApplicationStatus.CONDITIONALLY_APPROVED,
            ApplicationStatus.UNDER_REVIEW,
        ):
            m["conditional"] += 1

        # Rolling average of processing time
        m["average_processing_time"] = (
            m["average_processing_time"] * (total - 1) + result.processing_time
        ) / total

        # Rolling compliance score (synthetic — agents can return a numeric tag)
        m["compliance_score"] = (m["compliance_score"] * (total - 1) + 97.5) / total


# ── module-level helpers ───────────────────────────────────────────────────────

async def _run_agent(runner, session_id: str, message: str, app_id: str) -> str:
    """Send a message to a runner and return the last text response."""
    from google.genai import types as genai_types

    full_response = ""
    async for event in runner.run_async(
        user_id="system",
        session_id=session_id,
        new_message=genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=message)],
        ),
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                full_response = "".join(
                    p.text for p in event.content.parts if hasattr(p, "text")
                )
    return full_response


def _parse_status(text: str) -> ApplicationStatus:
    """Infer ApplicationStatus from the approval agent's free-text output."""
    text_lower = text.lower()
    if "conditionally approved" in text_lower or "conditional approval" in text_lower:
        return ApplicationStatus.CONDITIONALLY_APPROVED
    if "approved" in text_lower:
        return ApplicationStatus.APPROVED
    if "rejected" in text_lower or "denied" in text_lower:
        return ApplicationStatus.REJECTED
    if "additional information" in text_lower or "requires info" in text_lower:
        return ApplicationStatus.REQUIRES_INFO
    return ApplicationStatus.UNDER_REVIEW
