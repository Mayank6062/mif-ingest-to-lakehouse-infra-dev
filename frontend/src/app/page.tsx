"use client";

import React, { useState, useCallback, useEffect } from "react";
import { AppHeader } from "@/components/layout/AppHeader";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { ChatInput } from "@/components/chat/ChatInput";
import { WorkflowStepper, WorkflowProgressBar } from "@/components/layout/WorkflowStepper";
import { useChat } from "@/hooks/useChat";
import { API_BASE } from "@/lib/constants";

interface SessionCredentials {
  id: string;
  token: string;
}

export default function Home() {
  const [session, setSession] = useState<SessionCredentials | null>(null);

  const initSession = useCallback(() => {
    // Server generates both session_id and session_token.
    // The token is required for WebSocket access and REST ownership checks.
    fetch(`${API_BASE}/api/sessions`, { method: "POST" })
      .then((r) => r.json())
      .then((data) =>
        setSession({ id: data.session_id, token: data.session_token })
      )
      .catch(() => {
        // Retry once after 2 s if the backend is not yet ready
        setTimeout(initSession, 2000);
      });
  }, []);

  useEffect(() => {
    initSession();
  }, [initSession]);

  const {
    messages,
    isTyping,
    wsStatus,
    workflowProgress,
    sendMessage,
    sendApproval,
  } = useChat(session?.id ?? "", session?.token ?? "");

  const handleNewSession = useCallback(() => {
    // Discard current session and create a fresh one server-side
    setSession(null);
    initSession();
  }, [initSession]);

  const handleSend = useCallback(
    (content: string, widgetValue?: unknown) => {
      sendMessage(content, widgetValue);
    },
    [sendMessage]
  );

  return (
    <div className="h-full flex flex-col">
      <AppHeader wsStatus={wsStatus} onNewSession={handleNewSession} />

      {/* Desktop sidebar + main content — flex row */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Desktop sidebar stepper — hidden on mobile, visible on md+ */}
        <WorkflowStepper progress={workflowProgress} />

        {/* Right column: mobile bar + chat */}
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          {/* Mobile compact progress bar — visible only below md breakpoint */}
          <WorkflowProgressBar progress={workflowProgress} />

          {/* Chat area */}
          <main className="flex-1 flex flex-col overflow-hidden max-w-4xl w-full mx-auto">
            <ChatContainer
              messages={messages}
              isTyping={isTyping}
              onSend={handleSend}
              onApprove={sendApproval}
            />

            <ChatInput
              onSend={handleSend}
              disabled={wsStatus !== "open"}
              placeholder={
                wsStatus !== "open"
                  ? "Connecting to MIF Agent..."
                  : 'Type a message or use the widgets above... (type "restart" to start over)'
              }
            />
          </main>
        </div>
      </div>
    </div>
  );
}

