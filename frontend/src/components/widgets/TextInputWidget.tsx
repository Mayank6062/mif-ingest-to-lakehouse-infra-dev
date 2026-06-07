"use client";

import React, { useState, KeyboardEvent } from "react";
import { cn } from "@/lib/utils";
import { ArrowRight } from "lucide-react";

interface TextInputWidgetProps {
  placeholder?: string;
  hint?: string;
  onSubmit: (value: string) => void;
}

export function TextInputWidget({ placeholder, hint, onSubmit }: TextInputWidgetProps) {
  const [value, setValue] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (!value.trim() || submitted) return;
    setSubmitted(true);
    onSubmit(value.trim());
  };

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSubmit();
  };

  return (
    <div className="mt-2 flex flex-col gap-1 max-w-sm">
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKey}
          placeholder={placeholder || "Type here..."}
          disabled={submitted}
          autoFocus
          className={cn(
            "flex-1 px-3 py-2 text-sm rounded-lg border",
            "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
            "focus:outline-none focus:ring-2 focus:ring-blue-500 border-gray-300 dark:border-gray-600",
            "font-mono",
            submitted && "opacity-60"
          )}
        />
        <button
          onClick={handleSubmit}
          disabled={submitted || !value.trim()}
          className={cn(
            "px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium",
            "hover:bg-blue-700 transition-colors",
            "disabled:opacity-50 disabled:cursor-not-allowed"
          )}
        >
          <ArrowRight size={16} />
        </button>
      </div>
      {hint && <p className="text-xs text-gray-400">{hint}</p>}
    </div>
  );
}
