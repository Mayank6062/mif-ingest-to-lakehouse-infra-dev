"use client";

import React from "react";
import { ValidationResult } from "@/types";
import { cn } from "@/lib/utils";
import { CheckCircle, AlertCircle, XCircle } from "lucide-react";

interface ValidationBadgeProps {
  result: ValidationResult;
}

export function ValidationBadge({ result }: ValidationBadgeProps) {
  const config = {
    pass: {
      icon: <CheckCircle size={12} />,
      color: "text-green-600 bg-green-50 dark:bg-green-900/20 border-green-300",
    },
    warn: {
      icon: <AlertCircle size={12} />,
      color: "text-amber-600 bg-amber-50 dark:bg-amber-900/20 border-amber-300",
    },
    fail: {
      icon: <XCircle size={12} />,
      color: "text-red-600 bg-red-50 dark:bg-red-900/20 border-red-300",
    },
  };

  const { icon, color } = config[result.result] || config.fail;

  return (
    <div className={cn("flex items-start gap-2 px-3 py-2 rounded-lg border text-xs", color)}>
      <span className="flex-shrink-0 mt-0.5">{icon}</span>
      <div>
        <span className="font-mono font-semibold">{result.rule_id}</span>
        {" — "}
        <span className="font-medium">{result.rule_name}</span>
        <p className="text-opacity-80 mt-0.5">{result.message}</p>
      </div>
    </div>
  );
}
