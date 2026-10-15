"""Structured agent answers, audit events, and human API requests."""
from typing import Any, Literal
from pydantic import BaseModel, Field

Role = Literal['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

class AgentReport(BaseModel):
    summary: str = Field(description='Concise public account of work actually performed, with factual figures')
    status: Literal['analysis_complete', 'waiting_for_approval', 'resolved', 'blocked']
    evidence: list[str] = Field(description='Database and tool facts supporting the recommendation')
    recommendations: list[str]

class AuditEvent(BaseModel):
    id: int
    timestamp: str
    session_id: str
    run_id: str | None = None
    ticket_id: int | None = None
    agent: str
    event: str
    summary: str
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    result: Any = None
    stop_reason: str | None = None

class ApprovalDecision(BaseModel):
    approve: bool
    approved_by: str = Field(min_length=1, max_length=100)

class ResetRequest(BaseModel):
    confirm: Literal['RESET WORKING DATABASE']
