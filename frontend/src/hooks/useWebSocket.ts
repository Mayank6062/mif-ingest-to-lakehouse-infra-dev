"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { WS_BASE } from "@/lib/constants";

export type WsStatus = "connecting" | "open" | "closed" | "error";

interface UseWebSocketOptions {
  sessionId: string;
  sessionToken: string;
  onMessage: (data: unknown) => void;
  onStatusChange?: (status: WsStatus) => void;
}

export function useWebSocket({ sessionId, sessionToken, onMessage, onStatusChange }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<WsStatus>("connecting");
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);
  const MAX_RECONNECT = 5;

  const updateStatus = useCallback((s: WsStatus) => {
    setStatus(s);
    onStatusChange?.(s);
  }, [onStatusChange]);

  const connect = useCallback(() => {
    // Do not attempt to connect until the server has issued both credentials
    if (!sessionId || !sessionToken) return;

    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    // Token is appended as a query parameter (browser WebSocket API does not
    // support custom headers; query param is the standard alternative)
    const url = `${WS_BASE}/ws/${sessionId}?token=${encodeURIComponent(sessionToken)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    updateStatus("connecting");

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      updateStatus("open");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      updateStatus("closed");
      // Auto-reconnect with exponential backoff
      if (reconnectAttempts.current < MAX_RECONNECT) {
        const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30000);
        reconnectAttempts.current++;
        reconnectTimer.current = setTimeout(connect, delay);
      } else {
        updateStatus("error");
      }
    };

    ws.onerror = () => {
      updateStatus("error");
    };
  }, [sessionId, sessionToken, onMessage, updateStatus]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { send, status };
}
