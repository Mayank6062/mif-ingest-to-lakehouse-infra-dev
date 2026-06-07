"use client";

import React, { useState } from "react";
import { FormField } from "@/types";
import { cn } from "@/lib/utils";
import { Pencil, Check, X, Bot } from "lucide-react";

interface SinkConfigFormProps {
  fields: FormField[];
  onSubmit: (data: Record<string, string>) => void;
  isLocked?: boolean;
  onResubmit?: (data: Record<string, string>) => void;
}

export function SinkConfigForm({
  fields,
  onSubmit,
  isLocked = false,
  onResubmit,
}: SinkConfigFormProps) {
  // Initialize values from agent-derived defaults.
  // Use f.default first, fall back to f.placeholder — backend sets both to the same derived value.
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    fields.forEach((f) => {
      init[f.name] = (f.default || f.placeholder || "").trim();
    });
    return init;
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  // submitted=true only after user clicks Continue (or isLocked from parent)
  const [submitted, setSubmitted] = useState(isLocked);
  // Show agent banner when any field was pre-filled
  const hasAgentDefaults = fields.some((f) => !!(f.default || f.placeholder || "").trim());
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const validate = () => {
    const errs: Record<string, string> = {};
    fields.forEach((f) => {
      if (f.required && !values[f.name]?.trim()) {
        errs[f.name] = `${f.label} is required`;
      }
    });
    return errs;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (submitted) return;
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    setSubmitted(true);
    onSubmit(values);
  };

  const startEdit = (fieldName: string) => {
    setEditingField(fieldName);
    setEditValue(values[fieldName] || "");
  };

  const cancelEdit = () => {
    setEditingField(null);
    setEditValue("");
  };

  const saveEdit = (fieldName: string) => {
    const updated = { ...values, [fieldName]: editValue.trim() };
    setValues(updated);
    setEditingField(null);
    setEditValue("");
    onResubmit?.(updated);
  };

  // â”€â”€ After submission: compact read-only card with per-field edit â”€â”€â”€â”€â”€â”€â”€â”€â”€
  if (submitted) {
    return (
      <div className="bg-white dark:bg-gray-800 border border-green-200 dark:border-green-800 rounded-xl p-4 mt-2 w-full max-w-lg">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-green-700 dark:text-green-400">
            âœ… Sink Configuration saved
          </p>
          <span className="text-[11px] text-gray-400">hover a row to edit âœï¸</span>
        </div>
        <div className="space-y-3">
          {fields.map((field) => (
            <div key={field.name}>
              <span className="text-[11px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide">
                {field.label}
              </span>
              {editingField === field.name ? (
                <div className="flex items-center gap-1 mt-1">
                  <input
                    autoFocus
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveEdit(field.name);
                      if (e.key === "Escape") cancelEdit();
                    }}
                    className="flex-1 px-2 py-1 text-xs rounded border border-blue-400 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button type="button" onClick={() => saveEdit(field.name)}
                    className="p-1.5 rounded bg-green-100 dark:bg-green-900/30 text-green-600 hover:bg-green-200 transition-colors" title="Save (Enter)">
                    <Check size={13} />
                  </button>
                  <button type="button" onClick={cancelEdit}
                    className="p-1.5 rounded bg-red-100 dark:bg-red-900/30 text-red-500 hover:bg-red-200 transition-colors" title="Cancel (Escape)">
                    <X size={13} />
                  </button>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-2 mt-1 group">
                  <span className="text-xs font-mono text-gray-900 dark:text-gray-100 break-all flex-1">
                    {values[field.name] || <span className="text-gray-400 italic">â€”</span>}
                  </span>
                  <button type="button" onClick={() => startEdit(field.name)}
                    className="shrink-0 p-1.5 rounded text-gray-300 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors opacity-0 group-hover:opacity-100"
                    title={`Edit ${field.label}`}>
                    <Pencil size={13} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // â”€â”€ Input form (pre-filled by agent, fully editable) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 mt-2 space-y-4 w-full max-w-lg"
    >
      {/* Agent banner */}
      {hasAgentDefaults && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
          <Bot size={14} className="text-blue-500 shrink-0" />
          <p className="text-xs text-blue-700 dark:text-blue-300">
            Values pre-filled from knowledge base â€” edit any field if needed, then click <strong>Continue</strong>.
          </p>
        </div>
      )}

      {fields.map((field) => (
        <div key={field.name} className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
            {field.label}
            {field.required && <span className="text-red-500 ml-1">*</span>}
          </label>
          <input
            type="text"
            value={values[field.name] || ""}
            onChange={(e) =>
              setValues((prev) => ({ ...prev, [field.name]: e.target.value }))
            }
            placeholder={field.placeholder || ""}
            className={cn(
              "px-3 py-2 text-sm rounded-lg border",
              "bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100",
              "focus:outline-none focus:ring-2 focus:ring-blue-500",
              errors[field.name]
                ? "border-red-500"
                : "border-gray-300 dark:border-gray-600"
            )}
          />
          {field.hint && (
            <p className="text-xs text-gray-400">{field.hint}</p>
          )}
          {errors[field.name] && (
            <p className="text-xs text-red-500">{errors[field.name]}</p>
          )}
        </div>
      ))}
      <button
        type="submit"
        className="w-full py-2 rounded-lg text-sm font-semibold text-white transition-colors bg-blue-600 hover:bg-blue-700"
      >
        Continue â†’
      </button>
    </form>
  );
}
