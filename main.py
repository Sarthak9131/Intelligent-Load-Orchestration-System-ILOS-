"""
Demo: End-to-End Loan Processing with Multi-Agent System
Run: python main.py
"""

import asyncio
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Test cases ─────────────────────────────────────────────────────────────────

STRONG_CANDIDATE = """
LOAN APPLICATION
================
Applicant Name: Sarah Chen
Annual Income: $165,000 (Software Engineer, TechCorp Solutions, 5 years)
Credit Score: 785
Requested Loan Amount: $75,000
Loan Purpose: Home renovation
Monthly Debts: $2,850 (mortgage $2,200 + car loan $650)
Liquid Savings: $45,000
Employment Type: Full-time permanent
Documentation: Complete (pay stubs, bank statements, employment letter, 2 years tax returns)
"""

MODERATE_CANDIDATE = """
LOAN APPLICATION
================
Applicant Name: Marcus Williams
Annual Income: $68,000 (Self-employed consultant, 3 years in business)
Credit Score: 720
Requested Loan Amount: $35,000
Loan Purpose: Business equipment
Monthly Debts: $1,983 (rent $1,500 + credit card $483)
Liquid Savings: $15,000
Employment Type: Self-employed
Documentation: Partial (2 years tax returns, bank statements — missing recent invoices)
"""

HIGH_RISK_CANDIDATE = """
LOAN APPLICATION
================
Applicant Name: Robert Martinez
Annual Income: $38,400 (Gig / contract work, variable)
Credit Score: 580
Requested Loan Amount: $50,000
Loan Purpose: Debt consolidation
Monthly Debts: $2,500 (credit cards $1,800 + car $700)
Liquid Savings: $1,200
Employment Type: Gig / freelance
Documentation: Incomplete (no employment letter, bank statements only 1 month)
"""


async def main():
    # Import here so env vars are loaded first
    from src.orchestrator import LoanProcessingOrchestrator

    orchestrator = LoanProcessingOrchestrator()

    test_cases = [
        ("Strong Candidate — Sarah Chen", STRONG_CANDIDATE),
        ("Moderate Risk — Marcus Williams", MODERATE_CANDIDATE),
        ("High Risk — Robert Martinez", HIGH_RISK_CANDIDATE),
    ]

    results = []

    for label, application_data in test_cases:
        print(f"\n{'='*60}")
        print(f"Processing: {label}")
        print("=" * 60)

        result = await orchestrator.process_loan_application(application_data)
        results.append(result)

        print(f"Application ID : {result.application_id}")
        print(f"Status         : {result.status.value.upper()}")
        print(f"Processing Time: {result.processing_time:.2f}s")
        print("\nDECISION SUMMARY:")
        # Print first 600 chars of decision
        print(result.decision[:600] + ("..." if len(result.decision) > 600 else ""))

    # ── Dashboard ──────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("PERFORMANCE DASHBOARD")
    print("=" * 60)
    dashboard = orchestrator.get_performance_dashboard()
    for key, value in dashboard.items():
        print(f"  {key:<35}: {value}")

    # ── Save results ───────────────────────────────────────────────────────────
    output_path = Path("results.json")
    await asyncio.to_thread(
        output_path.write_text,
        json.dumps([r.to_dict() for r in results], indent=2),
        encoding="utf-8",
    )
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
