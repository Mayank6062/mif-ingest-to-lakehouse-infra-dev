"use client";

import React, { useState } from "react";
import { FormField } from "@/types";
import { cn } from "@/lib/utils";
import { Pencil, Check, X, Bot } from "lucide-react";

interface WorkerConfigFormProps {
  fields: FormField[];
  onSubmit: (data: Record<string, string>) => void;
  isLocked?: boolean;
  onResubmit?: (data: Record<string, string>) => void;
}

export function WorkerConfigForm({
  fields,
  onSubmit,
  isLocked = false,
  onResubmit,
}: WorkerConfigFormProps) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    fields.forEach((f) => { init[f.name] = (f.default || f.placeholder || "").trim(); });
    return init;
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(isLocked);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const validate = () => {
    const errs: Record<string, string> = {};
    fields.forEach((f) => {
      if (f.required && !values[f.name]?.trim()) errs[f.name] = `${f.label} is required`;
    });
    const n = parseInt(values["number_of_workers"] || "0", 10);
    if (isNaN(n) || n < 1 || n > 10) errs["number_of_workers"] = "Must be between 1 and 10";
    return errs;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (submitted) return;
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setSubmitted(true);
    onSubmit(values);
  };

  const startEdit = (name: string) => { setEditingField(name); setEditValue(values[name] || ""); };
  const cancelEdit = () => { setEditingField(null); setEditValue(""); };
  const saveEdit = (name: string) => {
    const updated = { ...values, [name]: editValue };
    setValues(updated); setEditingField(null); setEditValue("");
    onResubmit?.(updated);
  };

  const hasAgentDefaults = fields.some((f) => !!(f.default || f.placeholder || "").trim());

  if (submitted) {
    return (
      <div className="bg-white dark:bg-gray-800 border border-green-200 dark:border-green-800 rounded-xl p-4 mt-2 w-full max-w-lg">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold text-green-700 dark:text-green-400">✅ Worker Configuration saved</p>
          <span className="text-[11px] text-gray-400">hover a row to edit ✏️</span>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          {fields.map((field) => (
            <div key={field.name} className="col-span-1">
              <span className="text-[11px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide">{field.label}</span>
              {editingField === field.name ? (
                <div className="flex items-center gap-1 mt-1">
                  {field.field_type === "select" && field.options ? (
                    <select autoFocus value={editValue} onChange={(e) => setEditValue(e.target.value)}
                      className="flex-1 px-2 py-1 text-xs rounded border border-blue-400 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500">
                      {field.options.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                    </select>
                  ) : (
                    <input autoFocus value={editValue} onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") saveEdit(field.name); if (e.key === "Escape") cancelEdit(); }}
                      className="flex-1 px-2 py-1 text-xs rounded border border-blue-400 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  )}
                  <button type="button" onClick={() => saveEdit(field.name)} className="p-1.5 rounded bg-green-100 dark:bg-green-900/30 text-green-600 hover:bg-green-200 transition-colors"><Check size={12} /></button>
                  <button type="button" onClick={cancelEdit} className="p-1.5 rounded bg-red-100 dark:bg-red-900/30 text-red-500 hover:bg-red-200 transition-colors"><X size={12} /></button>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-1 mt-1 group">
                  <span className="text-xs font-mono text-gray-900 dark:text-gray-100 break-all">{values[field.name] || <span className="text-gray-400 italic">—</span>}</span>
                  <button type="button" onClick={() => startEdit(field.name)}
                    className="shrink-0 p-1 rounded text-gray-300 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors opacity-0 group-hover:opacity-100"
                    title={`Edit ${field.label}`}><Pencil size={12} /></button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  const renderField = (field: FormField) => {
    if (field.field_type === "select" && field.options) {
      return (
        <select value={values[field.name] || ""} onChange={(e) => setValues((prev) => ({ ...prev, [field.name]: e.target.value }))}
          className={`px-3 py-2 text-sm rounded-lg border bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 ${errors[field.name] ? "border-red-500" : "border-gray-300 dark:border-gray-600"}`}>
          {field.options.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      );
    }
    return (
      <input type="text" value={values[field.name] || ""} onChange={(e) => setValues((prev) => ({ ...prev, [field.name]: e.target.value }))}
        placeholder={field.placeholder || field.default || ""}
        className={`px-3 py-2 text-sm rounded-lg border bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 ${errors[field.name] ? "border-red-500" : "border-gray-300 dark:border-gray-600"}`} />
    );
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 mt-2 space-y-3 w-full max-w-lg">
      {hasAgentDefaults && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
          <Bot size={14} className="text-blue-500 shrink-0" />
          <p className="text-xs text-blue-700 dark:text-blue-300">Values pre-filled from knowledge base — edit any field if needed, then click <strong>Continue</strong>.</p>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        {fields.map((field) => (
          <div key={field.name} className={`flex flex-col gap-1 ${field.field_type === "text" && field.name !== "number_of_workers" ? "col-span-2" : "col-span-1"}`}>
            <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
              {field.label}{field.required && <span className="text-red-500 ml-1">*</span>}
            </label>
            {renderField(field)}
            {field.hint && <p className="text-xs text-gray-400">{field.hint}</p>}
            {errors[field.name] && <p className="text-xs text-red-500">{errors[field.name]}</p>}
          </div>
        ))}
      </div>
      <button type="submit" className="w-full py-2 rounded-lg text-sm font-semibold text-white transition-colors bg-blue-600 hover:bg-blue-700">Continue →</button>
    </form>
  );
}

