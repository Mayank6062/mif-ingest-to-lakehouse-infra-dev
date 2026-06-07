"use client";

import React, { useEffect, useRef } from "react";
import { ChatMessage } from "@/types";
import { ChatMessageBubble } from "./ChatMessage";
import { TypingIndicator } from "./TypingIndicator";

interface ChatContainerProps {
  messages: ChatMessage[];
  isTyping: boolean;
  onSend: (content: string, widgetValue?: unknown) => void;
  onApprove: (approved: boolean) => void;
}

export function ChatContainer({ messages, isTyping, onSend, onApprove }: ChatContainerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  return (
    <div className="flex-1 overflow-y-auto chat-scroll py-4">
      {messages.map((msg) => (
        <ChatMessageBubble
          key={msg.id}
          message={msg}
          onSend={onSend}
          onApprove={onApprove}
        />
      ))}
      {isTyping && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}
