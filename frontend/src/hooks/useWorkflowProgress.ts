"use client";

import { useMemo } from "react";
import { STEP_ORDER, STEP_LABELS, TOTAL_STEPS } from "@/lib/constants";
import type { ChatMessage, WorkflowProgress, WorkflowStepInfo, StepStatus } from "@/types";

// ── Step index constants (1-based) ────────────────────────────────────────────
const VALIDATION_STEP_INDEX = STEP_ORDER.indexOf("run_validation") + 1; // 7
const CREATE_PR_STEP_INDEX  = STEP_ORDER.indexOf("create_pr") + 1;      // 12
const PR_SUCCESS_STEP_INDEX = STEP_ORDER.indexOf("pr_success") + 1;     // 13

// ── Pure derivation function (exported for unit testing) ──────────────────────

export function computeProgress(messages: ChatMessage[]): WorkflowProgress {
  let currentStepIndex = 1;
  let highWaterMark    = 1;
  let overallStatus: WorkflowProgress["overallStatus"] = "active";
  let validationFailed = false;
  let prFailed         = false;

  for (const msg of messages) {
    // ── Reconnect message — restore state from Redis checkpoint ────────────
    if (msg.type === "reconnected") {
      if (msg.step?.current) {
        currentStepIndex = msg.step.current;
        highWaterMark    = Math.max(highWaterMark, msg.step.current);
      }
      // Restore validation failure from checkpoint
      if (msg.validation_failed) {
        validationFailed = true;
        // If back at collect_sink after validation, highWaterMark was at run_validation
        highWaterMark = Math.max(highWaterMark, VALIDATION_STEP_INDEX);
      }
      // Restore terminal states
      if (msg.pr_url) {
        overallStatus    = "complete";
        currentStepIndex = PR_SUCCESS_STEP_INDEX;
        highWaterMark    = PR_SUCCESS_STEP_INDEX;
      } else if (msg.user_approved === false) {
        overallStatus = "cancelled";
      } else if (msg.error_message && currentStepIndex === CREATE_PR_STEP_INDEX) {
        prFailed      = true;
        overallStatus = "failed";
      }
      continue;
    }

    // ── Update current step from message step info ─────────────────────────
    if (msg.step?.current) {
      const newIdx     = msg.step.current;
      currentStepIndex = newIdx;
      highWaterMark    = Math.max(highWaterMark, newIdx);

      // Clear validation failure once we advance past the validation step
      if (newIdx > VALIDATION_STEP_INDEX) {
        validationFailed = false;
      }
    }

    // ── Detect validation failure from widget results ──────────────────────
    if (msg.widget?.type === "validation" && msg.widget.results) {
      const hasFail = msg.widget.results.some((r) => r.result === "fail");
      validationFailed = hasFail;
    }

    // ── Detect PR success ──────────────────────────────────────────────────
    if (msg.type === "pr_created") {
      overallStatus    = "complete";
      currentStepIndex = PR_SUCCESS_STEP_INDEX;
      highWaterMark    = PR_SUCCESS_STEP_INDEX;
      validationFailed = false;
    }

    // ── Detect PR failure (error message at create_pr step) ───────────────
    if (msg.type === "error" && msg.step?.current === CREATE_PR_STEP_INDEX) {
      prFailed      = true;
      overallStatus = "failed";
    }

    // ── Detect approval cancellation ───────────────────────────────────────
    if (
      msg.type === "assistant_message" &&
      msg.content?.includes("Pull Request creation cancelled")
    ) {
      overallStatus = "cancelled";
    }
  }

  const steps          = _computeStepStatuses(currentStepIndex, overallStatus, validationFailed, prFailed);
  const currentStepId  = STEP_ORDER[currentStepIndex - 1] ?? STEP_ORDER[0];
  const percentComplete =
    overallStatus === "complete"
      ? 100
      : Math.round(((currentStepIndex - 1) / (TOTAL_STEPS - 1)) * 100);

  return {
    currentStepIndex,
    currentStepLabel: STEP_LABELS[currentStepId] ?? currentStepId,
    highWaterMark,
    totalSteps: TOTAL_STEPS,
    steps,
    percentComplete,
    overallStatus,
    validationFailed,
    prFailed,
  };
}

function _computeStepStatuses(
  currentStepIndex: number,
  overallStatus: WorkflowProgress["overallStatus"],
  validationFailed: boolean,
  prFailed: boolean,
): WorkflowStepInfo[] {
  return STEP_ORDER.map((stepId, idx) => {
    const stepIndex = idx + 1; // 1-based
    let status: StepStatus;

    if (overallStatus === "complete") {
      status = "completed";
    } else if (overallStatus === "cancelled") {
      status = stepIndex <= currentStepIndex ? "completed" : "skipped";
    } else if (stepIndex < currentStepIndex) {
      status = "completed";
    } else if (stepIndex === currentStepIndex) {
      // Active step — may also be in a failed state
      if (stepId === "run_validation" && validationFailed) {
        status = "failed";
      } else if (stepId === "create_pr" && prFailed) {
        status = "failed";
      } else {
        status = "active";
      }
    } else {
      // stepIndex > currentStepIndex — pending, unless a known failure step
      if (stepId === "run_validation" && validationFailed) {
        status = "failed"; // validation ran and failed; graph went back
      } else if (stepId === "create_pr" && prFailed) {
        status = "failed";
      } else {
        status = "pending";
      }
    }

    return { id: stepId, label: STEP_LABELS[stepId] ?? stepId, index: stepIndex, status };
  });
}

// ── React hook ────────────────────────────────────────────────────────────────

export function useWorkflowProgress(messages: ChatMessage[]): WorkflowProgress {
  return useMemo(() => computeProgress(messages), [messages]);
}
