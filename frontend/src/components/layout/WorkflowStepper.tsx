"use client";

import React, { useEffect, useState } from "react";
import { CheckCircle2, Circle, XCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { WorkflowProgress, WorkflowStepInfo, StepStatus } from "@/types";

// ── Props ─────────────────────────────────────────────────────────────────────

interface WorkflowStepperProps {
  progress: WorkflowProgress;
}

// ── Desktop sidebar stepper ───────────────────────────────────────────────────

export function WorkflowStepper({ progress }: WorkflowStepperProps) {
  const reducedMotion = usePrefersReducedMotion();

  return (
    <aside
      className="hidden md:flex flex-col w-52 flex-shrink-0 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900"
      aria-label="Workflow progress"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Progress
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
          Step {progress.currentStepIndex} of {progress.totalSteps}
        </p>
      </div>

      {/* Step list */}
      <nav className="flex-1 overflow-y-auto py-2" aria-label="Workflow steps">
        <ol role="list" className="space-y-0.5 px-2">
          {progress.steps.map((step) => (
            <StepItem
              key={step.id}
              step={step}
              totalSteps={progress.totalSteps}
              reducedMotion={reducedMotion}
            />
          ))}
        </ol>
      </nav>

      {/* Progress bar + status footer */}
      <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {_statusLabel(progress.overallStatus)}
          </span>
          <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
            {progress.percentComplete}%
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={progress.percentComplete}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Workflow ${progress.percentComplete}% complete`}
          className="h-1.5 w-full bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden"
        >
          <div
            className={cn(
              "h-full rounded-full",
              reducedMotion ? "" : "transition-all duration-500",
              progress.overallStatus === "complete"  && "bg-green-500",
              progress.overallStatus === "failed"    && "bg-red-500",
              progress.overallStatus === "cancelled" && "bg-gray-400",
              progress.overallStatus === "active"    && "bg-blue-500",
            )}
            style={{ width: `${progress.percentComplete}%` }}
          />
        </div>
      </div>
    </aside>
  );
}

// ── Mobile compact progress bar ───────────────────────────────────────────────

export function WorkflowProgressBar({ progress }: WorkflowStepperProps) {
  return (
    <div
      className="flex md:hidden items-center gap-2 px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900"
      aria-label="Workflow progress"
    >
      {/* Dot trail */}
      <div
        role="list"
        aria-label="Workflow steps"
        className="flex gap-0.5 flex-1 overflow-hidden"
      >
        {progress.steps.map((step) => (
          <MobileStepDot key={step.id} step={step} />
        ))}
      </div>

      {/* Current step label */}
      <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap flex-shrink-0">
        {progress.currentStepIndex}/{progress.totalSteps}:{" "}
        <span className="font-medium text-gray-700 dark:text-gray-300">
          {progress.currentStepLabel}
        </span>
      </span>
    </div>
  );
}

// ── Internal: step list item ──────────────────────────────────────────────────

function StepItem({
  step,
  totalSteps,
  reducedMotion,
}: {
  step: WorkflowStepInfo;
  totalSteps: number;
  reducedMotion: boolean;
}) {
  const isActive = step.status === "active";

  return (
    <li
      aria-label={`Step ${step.index} of ${totalSteps}: ${step.label} \u2014 ${step.status}`}
      aria-current={isActive ? "step" : undefined}
    >
      <div
        className={cn(
          "flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs transition-colors",
          isActive                      && "bg-blue-50 dark:bg-blue-900/20",
          step.status === "completed"   && "text-gray-700 dark:text-gray-300",
          isActive                      && "text-blue-700 dark:text-blue-300 font-medium",
          step.status === "failed"      && "text-red-600 dark:text-red-400",
          step.status === "pending"     && "text-gray-400 dark:text-gray-600",
          step.status === "skipped"     && "text-gray-300 dark:text-gray-700 line-through",
        )}
      >
        <span className="flex-shrink-0">
          <StepIcon status={step.status} reducedMotion={reducedMotion} />
        </span>
        <span className="truncate">{step.label}</span>
      </div>
    </li>
  );
}

// ── Internal: step icon ───────────────────────────────────────────────────────

function StepIcon({ status, reducedMotion }: { status: StepStatus; reducedMotion: boolean }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 size={14} className="text-green-500" aria-hidden="true" />;
    case "active":
      return (
        <Loader2
          size={14}
          className={cn("text-blue-500", !reducedMotion && "animate-spin")}
          aria-hidden="true"
        />
      );
    case "failed":
      return <XCircle size={14} className="text-red-500" aria-hidden="true" />;
    case "skipped":
      return <Circle size={14} className="text-gray-300 dark:text-gray-700" aria-hidden="true" />;
    case "pending":
    default:
      return <Circle size={14} className="text-gray-300 dark:text-gray-600" aria-hidden="true" />;
  }
}

// ── Internal: mobile dot ──────────────────────────────────────────────────────

function MobileStepDot({ step }: { step: WorkflowStepInfo }) {
  return (
    <div
      role="listitem"
      aria-label={`Step ${step.index}: ${step.label} \u2014 ${step.status}`}
      className={cn(
        "h-1.5 flex-1 rounded-full transition-colors",
        step.status === "completed" && "bg-green-500",
        step.status === "active"    && "bg-blue-500",
        step.status === "failed"    && "bg-red-500",
        (step.status === "skipped" || step.status === "pending") &&
          "bg-gray-200 dark:bg-gray-700",
      )}
    />
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _statusLabel(s: WorkflowProgress["overallStatus"]): string {
  switch (s) {
    case "complete":   return "\u2705 Complete";
    case "failed":     return "\u274c Failed";
    case "cancelled":  return "\u29b8 Cancelled";
    default:           return "In progress";
  }
}

function usePrefersReducedMotion(): boolean {
  const [prefersReducedMotion, set] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    set(mq.matches);
    const handler = (e: MediaQueryListEvent) => set(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  return prefersReducedMotion;
}
