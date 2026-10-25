"""Run two synthetic prior-authorization examples without API credentials."""

import asyncio
import json

from .schemas import PriorAuthorizationRequest
from .workflow import PriorAuthorizationOrchestrator


async def main() -> None:
    orchestrator = PriorAuthorizationOrchestrator(mode="stub")
    requests = [
        PriorAuthorizationRequest(
            synthetic=True,
            request_id="SYN-PA-0001",
            member_id="SYN-MEMBER-0001",
            procedure_code="SYN-PROC-100",
            diagnosis_code="SYN-DX-200",
            coverage_active=True,
            procedure_covered=True,
            criteria_met=True,
            clinical_notes_present=True,
            prescriber_info_present=True,
        ),
        PriorAuthorizationRequest(
            synthetic=True,
            request_id="SYN-PA-0002",
            member_id="SYN-MEMBER-0002",
            procedure_code="SYN-PROC-100",
            diagnosis_code="SYN-DX-200",
            coverage_active=True,
            procedure_covered=True,
            criteria_met=None,
            clinical_notes_present=False,
            prescriber_info_present=True,
        ),
    ]
    for request in requests:
        result = await orchestrator.process(request)
        print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
