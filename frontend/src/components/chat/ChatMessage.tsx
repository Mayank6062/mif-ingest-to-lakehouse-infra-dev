"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { ChatMessage, UIWidget } from "@/types";
import { ChipSelector } from "@/components/widgets/ChipSelector";
import { SinkConfigForm } from "@/components/widgets/SinkConfigForm";
import { WorkerConfigForm } from "@/components/widgets/WorkerConfigForm";
import { TerraformPreview } from "@/components/widgets/TerraformPreview";
import { ApprovalCard } from "@/components/widgets/ApprovalCard";
import { PRSuccessCard } from "@/components/widgets/PRSuccessCard";
import { ValidationBadge } from "@/components/widgets/ValidationBadge";
import { SummaryTable } from "@/components/widgets/SummaryTable";
import { TextInputWidget } from "@/components/widgets/TextInputWidget";
import { StepBadge } from "@/components/widgets/StepBadge";
import { formatTimestamp } from "@/lib/utils";
import { Bot, User } from "lucide-react";

interface ChatMessageProps {
  message: ChatMessage;
  onSend: (content: string, widgetValue?: unknown) => void;
  onApprove: (approved: boolean) => void;
}

export function ChatMessageBubble({ message, onSend, onApprove }: ChatMessageProps) {
  const isUser = message.role === "user";
  const [interacted, setInteracted] = useState(false);

  const handleWidgetSubmit = (value: unknown, displayText: string) => {
    if (interacted) return; // prevent double-submit
    setInteracted(true);
    onSend(displayText, value);
  };

  const handleApproval = (approved: boolean) => {
    if (interacted) return;
    setInteracted(true);
    onApprove(approved);
  };

  // Re-submit after inline field edit (does NOT lock — form stays visible in view mode)
  const handleWidgetResubmit = (value: unknown, displayText: string) => {
    onSend(displayText, value);
  };

  return (
    <div className={cn("flex gap-3 px-4 py-2", isUser ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-medium",
          isUser ? "bg-blue-600" : "bg-gradient-to-br from-sky-500 to-blue-700"
        )}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      {/* Bubble */}
      <div className={cn("max-w-[85%] flex flex-col gap-2", isUser ? "items-end" : "items-start")}>
        {/* Step badge for assistant */}
        {!isUser && message.step && (
          <StepBadge step={message.step} />
        )}

        {/* Text content */}
        {message.content && (
          <div
            className={cn(
              "px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap",
              isUser
                ? "bg-blue-600 text-white rounded-tr-sm"
                : "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 shadow-sm border border-gray-100 dark:border-gray-700 rounded-tl-sm"
            )}
            dangerouslySetInnerHTML={{
              __html: renderMarkdown(message.content),
            }}
          />
        )}

        {/* Widget rendering — forms always shown (view mode after submit); others hidden once interacted */}
        {!isUser && message.widget && (message.widget.type === "form" || !interacted) && (
          <WidgetRenderer
            widget={message.widget}
            messageType={message.type}
            isLocked={interacted}
            terraformHcl={message.terraform_hcl}
            filesToModify={message.files_to_modify}
            prChecklist={message.pr_checklist}
            onSubmit={handleWidgetSubmit}
            onResubmit={handleWidgetResubmit}
            onApprove={handleApproval}
          />
        )}

        {/* Approval buttons rendered BELOW the widget (e.g. after summary table) */}
        {!isUser && message.approval_request && !interacted && !message.widget?.type?.includes("approval") && (
          <ApprovalCard
            options={message.approval_options || ["✅ Yes, continue", "❌ No, start over"]}
            onApprove={handleApproval}
          />
        )}

        {/* Timestamp */}
        {message.timestamp && (
          <span className="text-xs text-gray-400 px-1">
            {formatTimestamp(message.timestamp)}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Widget renderer ────────────────────────────────────────────────────────────

interface WidgetRendererProps {
  widget: UIWidget;
  messageType: string;
  isLocked?: boolean;
  terraformHcl?: string;
  filesToModify?: string[];
  prChecklist?: string[];
  onSubmit: (value: unknown, displayText: string) => void;
  onResubmit: (value: unknown, displayText: string) => void;
  onApprove: (approved: boolean) => void;
}

function WidgetRenderer({
  widget,
  messageType,
  isLocked = false,
  terraformHcl,
  filesToModify,
  prChecklist,
  onSubmit,
  onResubmit,
  onApprove,
}: WidgetRendererProps) {
  switch (widget.type) {
    case "text_input":
      return (
        <TextInputWidget
          placeholder={widget.placeholder || "Type here..."}
          hint={widget.hint}
          onSubmit={(val) => onSubmit(val, val)}
        />
      );

    case "chips":
      return (
        <ChipSelector
          options={widget.options || []}
          onSelect={(val) => onSubmit(val, val)}
        />
      );

    case "form":
      if (messageType === "assistant_message" && widget.fields) {
        const fieldNames = widget.fields.map((f) => f.name);
        if (fieldNames.includes("iceberg_database")) {
          return (
            <SinkConfigForm
              fields={widget.fields}
              isLocked={isLocked}
              onSubmit={(data) => onSubmit(data, "Sink configuration submitted")}
              onResubmit={(data) => onResubmit(
                { ...data, _edit_type: "sink" },
                "✏️ Updated sink configuration"
              )}
            />
          );
        }
        return (
          <WorkerConfigForm
            fields={widget.fields}
            isLocked={isLocked}
            onSubmit={(data) => onSubmit(data, "Worker configuration submitted")}
            onResubmit={(data) => onResubmit(
              { ...data, _edit_type: "workers" },
              "✏️ Updated worker configuration"
            )}
          />
        );
      }
      return null;

    case "approval":
      return (
        <ApprovalCard
          options={widget.options || ["✅ Yes", "❌ No"]}
          onApprove={onApprove}
        />
      );

    case "code_preview":
      return (
        <TerraformPreview
          code={terraformHcl || widget.code || ""}
          files={widget.files}
          filesToModify={filesToModify || []}
          prChecklist={prChecklist || []}
        />
      );

    case "pr_success":
      return (
        <PRSuccessCard
          prUrl={widget.pr_url || ""}
          branchName={widget.branch_name || ""}
          filesModified={widget.files_modified || []}
        />
      );

    case "validation":
      return (
        <div className="flex flex-col gap-1">
          {(widget.results || []).map((r, i) => (
            <ValidationBadge key={i} result={r} />
          ))}
        </div>
      );

    case "summary":
      return <SummaryTable rows={widget.rows || []} />;

    default:
      return null;
  }
}

// ── Minimal markdown renderer (XSS-safe) ─────────────────────────────────────
//
// Security: HTML entities are escaped FIRST, then markdown patterns are applied.
// This means any user-supplied or server-supplied HTML is neutralised before our
// safe tags (<strong>, <code>, <a>, <br/>) are injected.
//
// Link URLs are additionally restricted to http/https to block javascript: URIs.

function escapeHtml(raw: string): string {
  return raw
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

function renderMarkdown(text: string): string {
  // Step 1 — escape all HTML so nothing from text can inject tags
  let safe = escapeHtml(text);

  // Step 2 — apply markdown transforms on the now-safe string
  safe = safe
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(
      /`([^`]+)`/g,
      '<code class="bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded text-xs font-mono">$1</code>'
    )
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      (_match, label, url) => {
        // Only allow safe URL schemes — block javascript:, data:, etc.
        if (/^https?:\/\//i.test(url)) {
          return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="text-blue-500 underline">${label}</a>`;
        }
        // For non-http URLs render just the label — no clickable link
        return label;
      }
    )
    .replace(/\n/g, "<br/>");

  return safe;
}
