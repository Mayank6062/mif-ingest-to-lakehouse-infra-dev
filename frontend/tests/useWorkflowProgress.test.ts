/**
 * Unit tests for useWorkflowProgress / computeProgress
 *
 * T1.  Initial session (empty messages)
 * T2.  Normal forward progression
 * T3.  Validation failure loop
 * T4.  Sink edit (re-runs from validation)
 * T5.  Workers edit
 * T6.  Approval rejection
 * T7.  PR success
 * T8.  PR failure
 * T9.  Reconnect restoration
 * T12. High-water-mark behaviour
 */

import { describe, it, expect } from "vitest";
import { computeProgress } from "../src/hooks/useWorkflowProgress";
import type { ChatMessage } from "../src/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

let _id = 0;

function stepMsg(
  stepCurrent: number,
  label = "",
  extra: Partial<ChatMessage> = {},
): ChatMessage {
  return {
    id: `m${++_id}`,
    type: "assistant_message",
    role: "assistant",
    content: "",
    step: { current: stepCurrent, total: 13, label },
    timestamp: 0,
    ...extra,
  };
}

function validationMsg(hasFail: boolean): ChatMessage {
  return {
    id: `m${++_id}`,
    type: "assistant_message",
    role: "assistant",
    content: "",
    step: { current: 7, total: 13, label: "Running Validations" },
    widget: {
      type: "validation",
      results: hasFail
        ? [{ rule_id: "TR003", rule_name: "Suffix", result: "fail", message: "must end .raw" }]
        : [{ rule_id: "TR003", rule_name: "Suffix", result: "pass", message: "ok" }],
    },
    timestamp: 0,
  };
}

// ── T1: Initial session ───────────────────────────────────────────────────────

describe("T1: Initial session (empty messages)", () => {
  it("starts at step 1", () => {
    const p = computeProgress([]);
    expect(p.currentStepIndex).toBe(1);
    expect(p.currentStepLabel).toBe("Enter Kafka Topic");
  });

  it("step 1 is active, all others pending", () => {
    const p = computeProgress([]);
    expect(p.steps[0].status).toBe("active");
    expect(p.steps.slice(1).every((s) => s.status === "pending")).toBe(true);
  });

  it("percentComplete is 0", () => {
    expect(computeProgress([]).percentComplete).toBe(0);
  });

  it("overallStatus is active", () => {
    expect(computeProgress([]).overallStatus).toBe("active");
  });

  it("totalSteps is 13", () => {
    expect(computeProgress([]).totalSteps).toBe(13);
  });
});

// ── T2: Normal forward progression ───────────────────────────────────────────

describe("T2: Normal forward progression", () => {
  it("marks earlier steps completed when advancing", () => {
    const msgs = [stepMsg(1), stepMsg(2), stepMsg(3), stepMsg(4), stepMsg(5)];
    const p = computeProgress(msgs);
    expect(p.currentStepIndex).toBe(5);
    expect(p.steps[0].status).toBe("completed"); // step 1
    expect(p.steps[3].status).toBe("completed"); // step 4
    expect(p.steps[4].status).toBe("active");    // step 5
    expect(p.steps[5].status).toBe("pending");   // step 6
  });

  it("all 13 steps in STEP_ORDER", () => {
    expect(computeProgress([]).steps).toHaveLength(13);
  });

  it("percentComplete increases as steps advance", () => {
    const p5  = computeProgress([stepMsg(5)]);
    const p10 = computeProgress([stepMsg(10)]);
    expect(p10.percentComplete).toBeGreaterThan(p5.percentComplete);
  });
});

// ── T3: Validation failure ────────────────────────────────────────────────────

describe("T3: Validation failure", () => {
  const msgs = [
    stepMsg(1), stepMsg(2), stepMsg(3), stepMsg(4), stepMsg(5), stepMsg(6),
    validationMsg(true),           // validation failed
    stepMsg(5, "Sink Config"),     // graph routes back to collect_sink
  ];

  it("currentStepIndex is 5 after going back", () => {
    expect(computeProgress(msgs).currentStepIndex).toBe(5);
  });

  it("validationFailed is true", () => {
    expect(computeProgress(msgs).validationFailed).toBe(true);
  });

  it("run_validation step shows failed", () => {
    const valStep = computeProgress(msgs).steps.find((s) => s.id === "run_validation");
    expect(valStep?.status).toBe("failed");
  });

  it("steps 1-4 remain completed", () => {
    const p = computeProgress(msgs);
    expect(p.steps[0].status).toBe("completed");
    expect(p.steps[3].status).toBe("completed");
  });

  it("step 5 is active after going back", () => {
    expect(computeProgress(msgs).steps[4].status).toBe("active");
  });

  it("clears validationFailed after passing", () => {
    const fixed = [
      ...msgs,
      stepMsg(6),
      validationMsg(false),  // validation passes this time
      stepMsg(8),
    ];
    const p = computeProgress(fixed);
    expect(p.validationFailed).toBe(false);
    expect(p.steps.find((s) => s.id === "run_validation")?.status).toBe("completed");
  });
});

// ── T4: Sink edit ─────────────────────────────────────────────────────────────

describe("T4: Sink edit (re-runs from validation)", () => {
  const forwardMsgs = [
    stepMsg(1), stepMsg(2), stepMsg(3), stepMsg(4), stepMsg(5), stepMsg(6),
    validationMsg(false), stepMsg(8), stepMsg(9), stepMsg(10), stepMsg(11),
  ];

  it("after edit, currentStepIndex is 7 (validation re-running)", () => {
    const p = computeProgress([...forwardMsgs, stepMsg(7, "Running Validations")]);
    expect(p.currentStepIndex).toBe(7);
  });

  it("highWaterMark is 11 (approval was reached before edit)", () => {
    const p = computeProgress([...forwardMsgs, stepMsg(7)]);
    expect(p.highWaterMark).toBe(11);
  });

  it("steps 1-6 remain completed after edit", () => {
    const p = computeProgress([...forwardMsgs, stepMsg(7)]);
    expect(p.steps[0].status).toBe("completed");
    expect(p.steps[5].status).toBe("completed");
  });

  it("step 7 is active during re-validation", () => {
    const p = computeProgress([...forwardMsgs, stepMsg(7)]);
    expect(p.steps[6].status).toBe("active");
  });
});

// ── T5: Workers edit ──────────────────────────────────────────────────────────

describe("T5: Workers edit", () => {
  it("highWaterMark tracks furthest step even after going back", () => {
    const msgs = [
      stepMsg(1), stepMsg(2), stepMsg(3), stepMsg(4), stepMsg(5), stepMsg(6),
      validationMsg(false), stepMsg(8), stepMsg(9), stepMsg(10),
      stepMsg(7), // workers edit, re-runs validation
    ];
    const p = computeProgress(msgs);
    expect(p.highWaterMark).toBe(10);
    expect(p.currentStepIndex).toBe(7);
  });
});

// ── T6: Approval rejection ────────────────────────────────────────────────────

describe("T6: Approval rejection", () => {
  const forwardMsgs = [
    stepMsg(1), stepMsg(2), stepMsg(3), stepMsg(4), stepMsg(5), stepMsg(6),
    validationMsg(false), stepMsg(8), stepMsg(9), stepMsg(10), stepMsg(11),
  ];
  const cancelMsg: ChatMessage = {
    id: `m${++_id}`,
    type: "assistant_message",
    role: "assistant",
    content: "✋ **Pull Request creation cancelled.**\n\nNo changes were made to the repository.",
    timestamp: 0,
  };

  it("overallStatus is cancelled", () => {
    expect(computeProgress([...forwardMsgs, cancelMsg]).overallStatus).toBe("cancelled");
  });

  it("steps 1-11 are completed", () => {
    const p = computeProgress([...forwardMsgs, cancelMsg]);
    expect(p.steps.slice(0, 11).every((s) => s.status === "completed")).toBe(true);
  });

  it("steps 12 (create_pr) and 13 (pr_success) are skipped", () => {
    const p = computeProgress([...forwardMsgs, cancelMsg]);
    expect(p.steps[11].status).toBe("skipped"); // create_pr
    expect(p.steps[12].status).toBe("skipped"); // pr_success
  });
});

// ── T7: PR success ────────────────────────────────────────────────────────────

describe("T7: PR success", () => {
  const prMsg: ChatMessage = {
    id: `m${++_id}`,
    type: "pr_created",
    role: "assistant",
    content: "🎉 PR created",
    step: { current: 13, total: 13, label: "Pull Request Created" },
    pr_url: "https://github.com/org/repo/pull/1",
    timestamp: 0,
  };

  it("overallStatus is complete", () => {
    const p = computeProgress([stepMsg(1), stepMsg(2), prMsg]);
    expect(p.overallStatus).toBe("complete");
  });

  it("percentComplete is 100", () => {
    expect(computeProgress([prMsg]).percentComplete).toBe(100);
  });

  it("all steps are completed", () => {
    const p = computeProgress([prMsg]);
    expect(p.steps.every((s) => s.status === "completed")).toBe(true);
  });
});

// ── T8: PR failure ────────────────────────────────────────────────────────────

describe("T8: PR failure", () => {
  const errMsg: ChatMessage = {
    id: `m${++_id}`,
    type: "error",
    role: "assistant",
    content: "❌ Failed to create Pull Request\n\nError: 401 Unauthorized",
    step: { current: 12, total: 13, label: "PR Creation Failed" },
    timestamp: 0,
  };

  it("overallStatus is failed", () => {
    expect(computeProgress([errMsg]).overallStatus).toBe("failed");
  });

  it("prFailed is true", () => {
    expect(computeProgress([errMsg]).prFailed).toBe(true);
  });

  it("create_pr step shows failed", () => {
    const prStep = computeProgress([errMsg]).steps.find((s) => s.id === "create_pr");
    expect(prStep?.status).toBe("failed");
  });

  it("pr_success step remains pending", () => {
    const successStep = computeProgress([errMsg]).steps.find((s) => s.id === "pr_success");
    expect(successStep?.status).toBe("pending");
  });
});

// ── T9: Reconnect restoration ─────────────────────────────────────────────────

describe("T9: Reconnect restoration", () => {
  it("restores step index from reconnected message", () => {
    const reconnect: ChatMessage = {
      id: `m${++_id}`,
      type: "reconnected",
      role: "assistant",
      content: "Welcome back",
      step: { current: 6, total: 13, label: "Worker Configuration" },
      completed_steps: ["collect_topic", "derive_values", "check_source_system", "confirm_derived", "collect_sink"],
      timestamp: 0,
    };
    const p = computeProgress([reconnect]);
    expect(p.currentStepIndex).toBe(6);
    expect(p.steps[0].status).toBe("completed"); // step 1
    expect(p.steps[4].status).toBe("completed"); // step 5
    expect(p.steps[5].status).toBe("active");    // step 6
  });

  it("restores validation failure state from reconnect", () => {
    const reconnect: ChatMessage = {
      id: `m${++_id}`,
      type: "reconnected",
      role: "assistant",
      content: "Welcome back",
      step: { current: 5, total: 13, label: "Sink Configuration" },
      completed_steps: ["collect_topic", "derive_values", "check_source_system", "confirm_derived"],
      validation_failed: true,
      timestamp: 0,
    };
    const p = computeProgress([reconnect]);
    expect(p.validationFailed).toBe(true);
    expect(p.highWaterMark).toBe(7); // elevated to VALIDATION_STEP_INDEX
    const valStep = p.steps.find((s) => s.id === "run_validation");
    expect(valStep?.status).toBe("failed");
  });

  it("restores PR success from reconnect via pr_url", () => {
    const reconnect: ChatMessage = {
      id: `m${++_id}`,
      type: "reconnected",
      role: "assistant",
      content: "Welcome back",
      step: { current: 13, total: 13, label: "PR Created" },
      completed_steps: [],
      pr_url: "https://github.com/org/repo/pull/1",
      timestamp: 0,
    };
    const p = computeProgress([reconnect]);
    expect(p.overallStatus).toBe("complete");
    expect(p.percentComplete).toBe(100);
  });

  it("restores cancelled state from reconnect via user_approved=false", () => {
    const reconnect: ChatMessage = {
      id: `m${++_id}`,
      type: "reconnected",
      role: "assistant",
      content: "Welcome back",
      step: { current: 11, total: 13, label: "Awaiting Approval" },
      completed_steps: [],
      user_approved: false,
      timestamp: 0,
    };
    const p = computeProgress([reconnect]);
    expect(p.overallStatus).toBe("cancelled");
  });

  it("restores PR failure from reconnect via error_message at step 12", () => {
    const reconnect: ChatMessage = {
      id: `m${++_id}`,
      type: "reconnected",
      role: "assistant",
      content: "Welcome back",
      step: { current: 12, total: 13, label: "Creating Pull Request" },
      completed_steps: [],
      error_message: "401 Unauthorized",
      timestamp: 0,
    };
    const p = computeProgress([reconnect]);
    expect(p.overallStatus).toBe("failed");
    expect(p.prFailed).toBe(true);
  });
});

// ── T12: High-water-mark behaviour ───────────────────────────────────────────

describe("T12: High-water-mark behaviour", () => {
  it("highWaterMark advances monotonically through the session", () => {
    const msgs = [
      stepMsg(1), stepMsg(2), stepMsg(3), stepMsg(4), stepMsg(5),
      stepMsg(6), validationMsg(true),
      stepMsg(5), stepMsg(6), validationMsg(false),
      stepMsg(8), stepMsg(9), stepMsg(10),
    ];
    const p = computeProgress(msgs);
    expect(p.highWaterMark).toBe(10);
    expect(p.currentStepIndex).toBe(10);
  });

  it("highWaterMark does not decrease when step goes backwards", () => {
    const msgs = [
      stepMsg(1), stepMsg(2), stepMsg(3), stepMsg(4), stepMsg(5),
      stepMsg(6), validationMsg(true),
      stepMsg(5), // back to step 5
    ];
    const p = computeProgress(msgs);
    expect(p.highWaterMark).toBe(7); // run_validation (step 7) was reached
    expect(p.currentStepIndex).toBe(5);
  });

  it("steps between current and highWaterMark are pending (not completed)", () => {
    const msgs = [
      stepMsg(1), stepMsg(2), stepMsg(3), stepMsg(4), stepMsg(5),
      stepMsg(6), validationMsg(true),
      stepMsg(5),
    ];
    const p = computeProgress(msgs);
    // step 6 (collect_workers) is > currentStepIndex(5), should be pending
    expect(p.steps[5].status).toBe("pending");
  });
});
