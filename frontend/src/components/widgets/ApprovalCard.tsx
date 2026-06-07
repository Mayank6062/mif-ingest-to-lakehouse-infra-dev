"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { ThumbsUp, ThumbsDown } from "lucide-react";

interface ApprovalCardProps {
  options: string[];
  onApprove: (approved: boolean) => void;
}

export function ApprovalCard({ options, onApprove }: ApprovalCardProps) {
  const [chosen, setChosen] = useState<boolean | null>(null);

  const handle = (approved: boolean) => {
    if (chosen !== null) return;
    setChosen(approved);
    onApprove(approved);
  };

  const approveLabel = options[0] || "✅ Yes, create Pull Request";
  const rejectLabel = options[1] || "❌ No, cancel";

  return (
    <div className="flex gap-3 mt-2">
      <button
        onClick={() => handle(true)}
        disabled={chosen !== null}
        className={cn(
          "flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold transition-all",
          chosen === true
            ? "bg-green-600 text-white"
            : "bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-2 border-green-500 hover:bg-green-100",
          chosen !== null && chosen !== true && "opacity-40 cursor-not-allowed"
        )}
      >
        <ThumbsUp size={16} />
        {approveLabel}
      </button>

      <button
        onClick={() => handle(false)}
        disabled={chosen !== null}
        className={cn(
          "flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold transition-all",
          chosen === false
            ? "bg-red-600 text-white"
            : "bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400 border-2 border-red-400 hover:bg-red-100",
          chosen !== null && chosen !== false && "opacity-40 cursor-not-allowed"
        )}
      >
        <ThumbsDown size={16} />
        {rejectLabel}
      </button>
    </div>
  );
}
