"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface TypingIndicatorProps {
  className?: string;
}

export function TypingIndicator({ className }: TypingIndicatorProps) {
  return (
    <div className={cn("flex items-center gap-1 px-4 py-3", className)}>
      <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-2xl px-4 py-3">
        <span className="text-xs text-gray-500 mr-2">MIF Agent is thinking</span>
        <span className="typing-dot w-2 h-2 bg-gray-400 rounded-full inline-block" />
        <span className="typing-dot w-2 h-2 bg-gray-400 rounded-full inline-block" />
        <span className="typing-dot w-2 h-2 bg-gray-400 rounded-full inline-block" />
      </div>
    </div>
  );
}
