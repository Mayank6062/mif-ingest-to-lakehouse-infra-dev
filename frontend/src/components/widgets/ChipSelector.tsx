"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";

interface ChipSelectorProps {
  options: string[];
  onSelect: (value: string) => void;
  multiSelect?: boolean;
}

export function ChipSelector({ options, onSelect, multiSelect = false }: ChipSelectorProps) {
  const [selected, setSelected] = useState<string[]>([]);
  const [submitted, setSubmitted] = useState(false);

  const toggle = (opt: string) => {
    if (submitted) return;
    if (multiSelect) {
      setSelected((prev) =>
        prev.includes(opt) ? prev.filter((o) => o !== opt) : [...prev, opt]
      );
    } else {
      setSelected([opt]);
      setSubmitted(true);
      onSelect(opt);
    }
  };

  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => toggle(opt)}
          disabled={submitted}
          className={cn(
            "px-4 py-2 rounded-full text-sm font-medium border transition-all",
            selected.includes(opt)
              ? "bg-blue-600 text-white border-blue-600"
              : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-blue-400",
            submitted && "opacity-60 cursor-not-allowed"
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
