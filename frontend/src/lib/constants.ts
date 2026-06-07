export const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Workflow step definitions — mirrors backend app/graph/state.py exactly ────

export const STEP_ORDER: string[] = [
  "collect_topic",
  "derive_values",
  "check_source_system",
  "confirm_derived",
  "collect_sink",
  "collect_workers",
  "run_validation",
  "show_summary",
  "generate_terraform",
  "terraform_preview",
  "approval",
  "create_pr",
  "pr_success",
];

export const STEP_LABELS: Record<string, string> = {
  collect_topic:       "Enter Kafka Topic",
  derive_values:       "Deriving Values",
  check_source_system: "Checking Source System",
  confirm_derived:     "Confirm Derived Values",
  collect_sink:        "Sink Configuration",
  collect_workers:     "Worker Configuration",
  run_validation:      "Running Validations",
  show_summary:        "Review Summary",
  generate_terraform:  "Generating Terraform",
  terraform_preview:   "Terraform Preview",
  approval:            "Awaiting Approval",
  create_pr:           "Creating Pull Request",
  pr_success:          "Pull Request Created",
};

export const TOTAL_STEPS = STEP_ORDER.length; // 13
