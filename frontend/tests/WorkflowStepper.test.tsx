/**
 * Component tests for WorkflowStepper and WorkflowProgressBar
 *
 * T1.  Renders all 13 steps
 * T10. Mobile progress bar renders
 * T11. Accessibility: aria-label, aria-current, progressbar role
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WorkflowStepper, WorkflowProgressBar } from "../src/components/layout/WorkflowStepper";
import { STEP_ORDER, STEP_LABELS, TOTAL_STEPS } from "../src/lib/constants";
import type { WorkflowProgress, WorkflowStepInfo, StepStatus } from "../src/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeProgress(
  currentStepIndex: number,
  overrides: Partial<WorkflowProgress> = {},
): WorkflowProgress {
  const steps: WorkflowStepInfo[] = STEP_ORDER.map((id, idx) => {
    const i = idx + 1;
    const status: StepStatus =
      i < currentStepIndex ? "completed" :
      i === currentStepIndex ? "active" :
      "pending";
    return { id, label: STEP_LABELS[id] ?? id, index: i, status };
  });

  return {
    currentStepIndex,
    currentStepLabel: STEP_LABELS[STEP_ORDER[currentStepIndex - 1]] ?? "",
    highWaterMark: currentStepIndex,
    totalSteps: TOTAL_STEPS,
    steps,
    percentComplete: Math.round(((currentStepIndex - 1) / (TOTAL_STEPS - 1)) * 100),
    overallStatus: "active",
    validationFailed: false,
    prFailed: false,
    ...overrides,
  };
}

// ── T1: Renders all 13 steps ──────────────────────────────────────────────────

describe("T1: WorkflowStepper renders all 13 steps", () => {
  it("renders a list item for each step", () => {
    render(<WorkflowStepper progress={makeProgress(1)} />);
    // Each step label should appear in the sidebar
    STEP_ORDER.forEach((id) => {
      const label = STEP_LABELS[id];
      if (label) {
        const els = screen.queryAllByText(label);
        expect(els.length).toBeGreaterThan(0);
      }
    });
  });

  it("renders exactly 13 list items", () => {
    render(<WorkflowStepper progress={makeProgress(1)} />);
    // aria-label on each <li>: "Step N of 13: ..."
    const items = document.querySelectorAll("li[aria-label]");
    expect(items.length).toBe(13);
  });
});

// ── T10: Mobile progress bar ──────────────────────────────────────────────────

describe("T10: WorkflowProgressBar (mobile)", () => {
  it("renders with workflow progress aria-label", () => {
    render(<WorkflowProgressBar progress={makeProgress(3)} />);
    const bar = screen.getByLabelText(/workflow progress/i);
    expect(bar).toBeTruthy();
  });

  it("renders 13 dot items in the mobile bar", () => {
    render(<WorkflowProgressBar progress={makeProgress(3)} />);
    const dots = document.querySelectorAll("[role='listitem']");
    expect(dots.length).toBe(13);
  });

  it("displays current step label", () => {
    render(<WorkflowProgressBar progress={makeProgress(5)} />);
    expect(screen.getByText("Sink Configuration")).toBeTruthy();
  });
});

// ── T11: Accessibility ────────────────────────────────────────────────────────

describe("T11: Accessibility", () => {
  it("sidebar has role=complementary (aside) with aria-label", () => {
    render(<WorkflowStepper progress={makeProgress(1)} />);
    const aside = screen.getByRole("complementary", { name: /workflow progress/i });
    expect(aside).toBeTruthy();
  });

  it("active step has aria-current='step'", () => {
    render(<WorkflowStepper progress={makeProgress(4)} />);
    const active = document.querySelector("[aria-current='step']");
    expect(active).not.toBeNull();
  });

  it("only one step has aria-current='step'", () => {
    render(<WorkflowStepper progress={makeProgress(6)} />);
    const actives = document.querySelectorAll("[aria-current='step']");
    expect(actives.length).toBe(1);
  });

  it("progressbar has required aria attributes", () => {
    const p = makeProgress(5);
    render(<WorkflowStepper progress={p} />);
    const pb = screen.getByRole("progressbar");
    expect(pb).toHaveAttribute("aria-valuenow", String(p.percentComplete));
    expect(pb).toHaveAttribute("aria-valuemin", "0");
    expect(pb).toHaveAttribute("aria-valuemax", "100");
    expect(pb).toHaveAttribute("aria-label");
  });

  it("every list item has aria-label describing its step", () => {
    render(<WorkflowStepper progress={makeProgress(2)} />);
    const items = document.querySelectorAll("li[aria-label]");
    items.forEach((item) => {
      const label = item.getAttribute("aria-label") ?? "";
      expect(label).toMatch(/Step \d+ of 13/);
    });
  });

  it("step icons use aria-hidden to avoid double-reading", () => {
    render(<WorkflowStepper progress={makeProgress(3)} />);
    const hiddenIcons = document.querySelectorAll("svg[aria-hidden='true']");
    // At minimum 13 icons (one per step)
    expect(hiddenIcons.length).toBeGreaterThanOrEqual(13);
  });
});

// ── Status labels ─────────────────────────────────────────────────────────────

describe("Status label rendering", () => {
  it("shows Complete label when overallStatus is complete", () => {
    const p = makeProgress(13, {
      overallStatus: "complete",
      percentComplete: 100,
      steps: STEP_ORDER.map((id, idx) => ({
        id, label: STEP_LABELS[id] ?? id, index: idx + 1, status: "completed" as StepStatus,
      })),
    });
    render(<WorkflowStepper progress={p} />);
    expect(screen.getByText(/complete/i)).toBeTruthy();
  });

  it("shows Failed label when overallStatus is failed", () => {
    const steps: WorkflowStepInfo[] = STEP_ORDER.map((id, idx) => {
      const i = idx + 1;
      return {
        id, label: STEP_LABELS[id] ?? id, index: i,
        status: (i < 12 ? "completed" : i === 12 ? "failed" : "pending") as StepStatus,
      };
    });
    const p = makeProgress(12, { overallStatus: "failed", prFailed: true, steps });
    render(<WorkflowStepper progress={p} />);
    expect(screen.getByText(/failed/i)).toBeTruthy();
  });

  it("shows Cancelled label when overallStatus is cancelled", () => {
    const p = makeProgress(11, { overallStatus: "cancelled" });
    render(<WorkflowStepper progress={p} />);
    expect(screen.getByText(/cancelled/i)).toBeTruthy();
  });
});
