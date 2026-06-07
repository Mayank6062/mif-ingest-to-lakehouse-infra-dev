"use client";

import React from "react";
import { StepInfo } from "@/types";
import { cn } from "@/lib/utils";

interface StepBadgeProps {
  step: StepInfo;
}

export function StepBadge({ step }: StepBadgeProps) {
  const progress = Math.round((step.current / step.total) * 100);

  return (
    <div className="flex items-center gap-2 mb-1">
      <span className="text-xs font-medium text-blue-600 dark:text-blue-400">
        Step {step.current}/{step.total}
      </span>
      <div className="flex-1 max-w-[120px] h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-300"
          style={{ width: `${progress}%` }}
        />
      </div>
      <span className="text-xs text-gray-500">{step.label}</span>
    </div>
  );
}
