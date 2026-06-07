"use client";

import React, { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TerraformFile } from "@/types";

interface TerraformPreviewProps {
  code: string;
  files?: TerraformFile[];
  filesToModify: string[];
  prChecklist: string[];
}

// ── Action badge colors ───────────────────────────────────────────────────────
const ACTION_STYLES: Record<string, { badge: string; tab: string }> = {
  created:   { badge: "bg-emerald-500/20 text-emerald-400", tab: "border-emerald-500 text-emerald-400" },
  modified:  { badge: "bg-orange-500/20 text-orange-400",   tab: "border-orange-400 text-orange-300"   },
  reference: { badge: "bg-gray-600/40 text-gray-400",       tab: "border-gray-500 text-gray-400"       },
};

const ACTION_LABEL: Record<string, string> = {
  created:   "CREATED",
  modified:  "MODIFIED",
  reference: "UNCHANGED",
};

// ── Single file panel ─────────────────────────────────────────────────────────
function FilePanel({ file }: { file: TerraformFile }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(file.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const styles = ACTION_STYLES[file.action] ?? ACTION_STYLES.reference;
  const actionLabel = ACTION_LABEL[file.action] ?? file.action.toUpperCase();

  return (
    <div>
      {/* File header bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2 min-w-0">
          <FileText size={13} className="text-gray-400 shrink-0" />
          <span className="text-xs font-mono text-gray-200 truncate">{file.filename}</span>
          <span className={cn("text-xs px-2 py-0.5 rounded font-mono font-semibold shrink-0", styles.badge)}>
            {actionLabel}
          </span>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors shrink-0 ml-2"
        >
          {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>

      {/* Sub-label for reference files */}
      {file.action === "reference" && (
        <div className="px-4 py-1.5 bg-gray-900/60 border-b border-gray-700/50">
          <span className="text-xs text-gray-500 italic">
            Shown for reference — no changes needed. The{" "}
            <code className="text-gray-400">for_each = local.glue_jobs</code> block automatically
            picks up any new job entries added to <code className="text-gray-400">locals.tf</code>.
          </span>
        </div>
      )}

      {/* Code block */}
      <SyntaxHighlighter
        language={file.language || "hcl"}
        style={vscDarkPlus}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          fontSize: "12px",
          maxHeight: "400px",
          background: file.action === "reference" ? "#0d1117" : undefined,
        }}
        showLineNumbers
      >
        {file.code}
      </SyntaxHighlighter>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export function TerraformPreview({ code, files, filesToModify, prChecklist }: TerraformPreviewProps) {
  const [activeTab, setActiveTab] = useState(0);
  const [legacyCopied, setLegacyCopied] = useState(false);

  // ── Multi-file mode (new — when backend sends files array) ────────────
  if (files && files.length > 0) {
    const activeFile = files[activeTab] ?? files[0];

    return (
      <div className="terraform-code w-full max-w-2xl mt-2 rounded-xl border border-gray-700 overflow-hidden">

        {/* Tab strip */}
        <div className="flex items-end bg-gray-900 border-b border-gray-700 overflow-x-auto">
          {files.map((f, i) => {
            const tabStyles = ACTION_STYLES[f.action] ?? ACTION_STYLES.reference;
            const isActive = i === activeTab;
            return (
              <button
                key={i}
                onClick={() => setActiveTab(i)}
                className={cn(
                  "flex items-center gap-1.5 px-4 py-2.5 text-xs font-mono whitespace-nowrap border-b-2 transition-colors",
                  isActive
                    ? cn("bg-gray-800", tabStyles.tab)
                    : "border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/50"
                )}
              >
                <FileText size={12} />
                {f.filename.split("/").pop()}
                <span className={cn(
                  "text-[10px] px-1.5 py-0.5 rounded font-semibold",
                  isActive ? (ACTION_STYLES[f.action]?.badge ?? "") : "bg-gray-700/50 text-gray-500"
                )}>
                  {ACTION_LABEL[f.action] ?? f.action.toUpperCase()}
                </span>
              </button>
            );
          })}
        </div>

        {/* Active file panel */}
        <FilePanel file={activeFile} />

        {/* PR Checklist */}
        {prChecklist.length > 0 && (
          <div className="px-4 py-3 bg-gray-900 border-t border-gray-700">
            <p className="text-xs font-semibold text-gray-400 mb-2">PR Checklist:</p>
            <div className="flex flex-col gap-1">
              {prChecklist.map((item, i) => (
                <span key={i} className="text-xs text-gray-300">{item}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Legacy single-file mode (fallback) ───────────────────────────────
  const handleLegacyCopy = async () => {
    await navigator.clipboard.writeText(code);
    setLegacyCopied(true);
    setTimeout(() => setLegacyCopied(false), 2000);
  };

  return (
    <div className="terraform-code w-full max-w-2xl mt-2 rounded-xl border border-gray-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <FileText size={14} className="text-gray-400" />
          <span className="text-xs font-mono text-gray-300">locals.tf — new entry</span>
          <span className="text-xs px-2 py-0.5 bg-orange-500/20 text-orange-400 rounded font-mono">HCL</span>
        </div>
        <button
          onClick={handleLegacyCopy}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
        >
          {legacyCopied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
          {legacyCopied ? "Copied!" : "Copy"}
        </button>
      </div>
      <SyntaxHighlighter
        language="hcl"
        style={vscDarkPlus}
        customStyle={{ margin: 0, borderRadius: 0, fontSize: "12px", maxHeight: "360px" }}
        showLineNumbers
      >
        {code}
      </SyntaxHighlighter>

      {filesToModify.length > 0 && (
        <div className="px-4 py-3 bg-gray-900 border-t border-gray-700">
          <p className="text-xs font-semibold text-gray-400 mb-2">Files to modify:</p>
          <div className="flex flex-col gap-1">
            {filesToModify.map((f, i) => (
              <span key={i} className="text-xs font-mono text-emerald-400">📄 {f}</span>
            ))}
          </div>
        </div>
      )}

      {prChecklist.length > 0 && (
        <div className="px-4 py-3 bg-gray-900 border-t border-gray-700">
          <p className="text-xs font-semibold text-gray-400 mb-2">PR Checklist:</p>
          <div className="flex flex-col gap-1">
            {prChecklist.map((item, i) => (
              <span key={i} className="text-xs text-gray-300">{item}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
