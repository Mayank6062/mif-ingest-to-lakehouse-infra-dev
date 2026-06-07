"use client";

import { useState, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { ChatMessage, OutgoingMessage } from "@/types";
import { useWebSocket, WsStatus } from "./useWebSocket";
import { useWorkflowProgress } from "./useWorkflowProgress";

export function useChat(sessionId: string, sessionToken: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [wsStatus, setWsStatus] = useState<WsStatus>("connecting");

  const handleIncomingMessage = useCallback((raw: unknown) => {
    const data = raw as Record<string, unknown>;
    const type = data.type as string;

    if (type === "typing") {
      setIsTyping(true);
      return;
    }

    if (type === "stop_typing") {
      setIsTyping(false);
      return;
    }

    // Build a ChatMessage for every non-typing message (including reconnected)
    const msg: ChatMessage = {
      id: uuidv4(),
      type: type as ChatMessage["type"],
      role: (data.role as ChatMessage["role"]) || "assistant",
      content: (data.content as string) || "",
      widget: data.widget as ChatMessage["widget"],
      step: data.step as ChatMessage["step"],
      validation_results: data.validation_results as ChatMessage["validation_results"],
      terraform_hcl: data.terraform_hcl as string | undefined,
      files_to_modify: data.files_to_modify as string[] | undefined,
      pr_checklist: data.pr_checklist as string[] | undefined,
      new_source_checklist: data.new_source_checklist as string[] | undefined,
      pr_url: data.pr_url as string | undefined,
      branch_name: data.branch_name as string | undefined,
      approval_request: data.approval_request as boolean | undefined,
      approval_options: data.approval_options as string[] | undefined,
      // Reconnect-specific fields (undefined for non-reconnect messages)
      completed_steps: data.completed_steps as string[] | undefined,
      validation_failed: data.validation_failed as boolean | undefined,
      user_approved: data.user_approved as boolean | null | undefined,
      error_message: data.error_message as string | null | undefined,
      timestamp: Date.now(),
    };

    setIsTyping(false);
    setMessages((prev) => [...prev, msg]);
  }, []);

  const { send, status } = useWebSocket({
    sessionId,
    sessionToken,
    onMessage: handleIncomingMessage,
    onStatusChange: setWsStatus,
  });

  // Derive workflow progress from message stream
  const workflowProgress = useWorkflowProgress(messages);

  const sendMessage = useCallback(
    (content: string, widgetValue?: unknown) => {
      // Add user message immediately to the UI
      const userMsg: ChatMessage = {
        id: uuidv4(),
        type: "user_message",
        role: "user",
        content,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);

      // Send to backend
      const outgoing: OutgoingMessage = {
        type: "user_message",
        content,
        widget_value: widgetValue,
      };
      send(outgoing);
    },
    [send]
  );

  const sendApproval = useCallback(
    (approved: boolean) => {
      const content = approved ? "yes" : "no";
      const userMsg: ChatMessage = {
        id: uuidv4(),
        type: "user_message",
        role: "user",
        content: approved ? "✅ Approved — create Pull Request" : "❌ Cancelled",
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      send({ type: "approval", content });
    },
    [send]
  );

  return {
    messages,
    isTyping,
    wsStatus,
    workflowProgress,
    sendMessage,
    sendApproval,
  };
}

