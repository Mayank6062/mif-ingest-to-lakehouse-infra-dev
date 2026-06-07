"""
Pydantic models for chat messages and UI widgets.
These define the WebSocket protocol between backend and frontend.
"""

from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List, Any
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class WidgetType(str, Enum):
    CHIPS = "chips"               # Selectable chip buttons
    DROPDOWN = "dropdown"         # Single-select dropdown
    FORM = "form"                 # Multi-field form
    TEXT_INPUT = "text_input"     # Single text input
    APPROVAL = "approval"         # Yes / No approval buttons
    CODE_PREVIEW = "code_preview" # Terraform code block
    PR_SUCCESS = "pr_success"     # PR created success card
    VALIDATION = "validation"     # Validation result list
    SUMMARY = "summary"           # Summary table
    PROGRESS = "progress"         # Step progress indicator


class FormField(BaseModel):
    name: str
    label: str
    placeholder: str = ""
    required: bool = True
    field_type: str = "text"   # text | textarea | select
    options: Optional[List[str]] = None
    hint: Optional[str] = None
    default: Optional[str] = None


class UIWidget(BaseModel):
    type: WidgetType
    options: Optional[List[str]] = None
    multi_select: bool = False
    placeholder: Optional[str] = None
    fields: Optional[List[FormField]] = None
    # For code_preview
    language: Optional[str] = "hcl"
    code: Optional[str] = None
    # For pr_success
    pr_url: Optional[str] = None
    branch_name: Optional[str] = None
    files_modified: Optional[List[str]] = None
    # For summary
    rows: Optional[List[dict]] = None
    # For validation
    results: Optional[List[dict]] = None


class ValidationResult(BaseModel):
    rule_id: str
    rule_name: str
    result: str        # "pass" | "warn" | "fail"
    message: str
    field: Optional[str] = None


class StepInfo(BaseModel):
    current: int
    total: int = 12
    label: str


class ChatMessage(BaseModel):
    """A single chat message — sent over WebSocket in both directions."""
    type: str                         # "user_message" | "assistant_message" | "terraform_preview" | "approval_request" | "pr_created" | "error" | "typing"
    role: MessageRole = MessageRole.ASSISTANT
    content: str = ""
    widget: Optional[UIWidget] = None
    step: Optional[StepInfo] = None
    validation_results: Optional[List[ValidationResult]] = None
    # For terraform_preview type
    terraform_hcl: Optional[str] = None
    files_to_modify: Optional[List[str]] = None
    pr_checklist: Optional[List[str]] = None
    new_source_checklist: Optional[List[str]] = None
    # For pr_created type
    pr_url: Optional[str] = None
    branch_name: Optional[str] = None


class IncomingMessage(BaseModel):
    """Message from the frontend to the backend."""
    type: str              # "user_message" | "approval" | "correction"
    content: str = ""
    widget_value: Optional[Any] = None   # Selected chip value, form data, etc.
    session_id: Optional[str] = None
