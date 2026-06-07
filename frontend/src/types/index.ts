/**
 * TypeScript types for the MIF Glue Job Agent UI.
 * Mirrors the Python Pydantic models in backend/app/models/chat.py
 */

// ── Widget types ──────────────────────────────────────────────────────────────

export type WidgetType =
  | "chips"
  | "dropdown"
  | "form"
  | "text_input"
  | "approval"
  | "code_preview"
  | "pr_success"
  | "validation"
  | "summary"
  | "progress";

export interface FormField {
  name: string;
  label: string;
  placeholder?: string;
  required: boolean;
  field_type: "text" | "textarea" | "select";
  options?: string[];
  hint?: string;
  default?: string;
}

export interface TerraformFile {
  filename: string;
  label: string;
  language: string;
  code: string;
  action: "created" | "modified" | "reference";  // reference = unchanged, shown for info
}

export interface UIWidget {
  type: WidgetType;
  // Chips / dropdown
  options?: string[];
  multi_select?: boolean;
  placeholder?: string;
  // Form
  fields?: FormField[];
  // Code preview — single file (legacy)
  language?: string;
  code?: string;
  // Code preview — multi-file (new)
  files?: TerraformFile[];
  // PR success
  pr_url?: string;
  branch_name?: string;
  files_modified?: string[];
  // Summary table
  rows?: Array<{ field: string; value: string }>;
  // Validation results
  results?: ValidationResult[];
  // General hint
  hint?: string;
}

// ── Validation ────────────────────────────────────────────────────────────────

export interface ValidationResult {
  rule_id: string;
  rule_name: string;
  result: "pass" | "warn" | "fail";
  message: string;
  field?: string;
}

// ── Step progress ─────────────────────────────────────────────────────────────

export interface StepInfo {
  current: number;
  total: number;
  label: string;
}
// ── Workflow progress ───────────────────────────────────────────────────────────────────

export type StepStatus =
  | "completed"  // visited and successfully passed
  | "active"     // currently executing / waiting
  | "failed"     // ran but produced an error (validation, PR creation)
  | "pending"    // not yet reached
  | "skipped";   // bypassed (approval rejection path)

export interface WorkflowStepInfo {
  id: string;         // e.g. "collect_topic"
  label: string;      // e.g. "Enter Kafka Topic"
  index: number;      // 1-based position in STEP_ORDER
  status: StepStatus;
}

export interface WorkflowProgress {
  currentStepIndex: number;    // 1-based
  currentStepLabel: string;
  highWaterMark: number;       // highest step index ever reached (handles edits/loops)
  totalSteps: number;          // always 13
  steps: WorkflowStepInfo[];   // full 13-step list with computed statuses
  percentComplete: number;     // 0–100
  overallStatus: "active" | "complete" | "failed" | "cancelled";
  validationFailed: boolean;
  prFailed: boolean;
}
// ── Chat messages ─────────────────────────────────────────────────────────────

export type MessageType =
  | "user_message"
  | "assistant_message"
  | "terraform_preview"
  | "approval_request"
  | "pr_created"
  | "error"
  | "typing"
  | "stop_typing"
  | "reconnected"
  | "system";

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  type: MessageType;
  role: MessageRole;
  content: string;
  widget?: UIWidget;
  step?: StepInfo;
  validation_results?: ValidationResult[];
  // Terraform preview specific
  terraform_hcl?: string;
  files_to_modify?: string[];
  pr_checklist?: string[];
  new_source_checklist?: string[];
  // PR created specific
  pr_url?: string;
  branch_name?: string;
  // Approval
  approval_request?: boolean;
  approval_options?: string[];
  // Reconnect-specific fields (only populated on type="reconnected" messages)
  completed_steps?: string[];          // steps completed before current
  validation_failed?: boolean;         // true if prior validation run failed
  user_approved?: boolean | null;      // prior approval decision (null = not yet answered)
  error_message?: string | null;       // error from prior session (e.g. PR creation failure)
  // Timestamp
  timestamp?: number;
}

// ── Outgoing messages (frontend → backend) ────────────────────────────────────

export interface OutgoingMessage {
  type: "user_message" | "approval" | "correction";
  content: string;
  widget_value?: unknown;
  session_id?: string;
}

// ── Session ───────────────────────────────────────────────────────────────────

export interface Session {
  session_id: string;
  ws_url: string;
}

export interface SessionStatus {
  session_id: string;
  current_step: string;
  waiting_for_user: boolean;
  exists: boolean;
}
