"use client";

import React from "react";
import { Bot, Wifi, WifiOff, RefreshCw } from "lucide-react";
import { WsStatus } from "@/hooks/useWebSocket";
import { cn } from "@/lib/utils";

interface AppHeaderProps {
  wsStatus: WsStatus;
  onNewSession: () => void;
}

const statusConfig = {
  connecting: { label: "Connecting...", color: "text-amber-500" },
  open: { label: "Connected", color: "text-green-500" },
  closed: { label: "Disconnected", color: "text-red-500" },
  error: { label: "Connection Error", color: "text-red-600" },
};

export function AppHeader({ wsStatus, onNewSession }: AppHeaderProps) {
  const { label, color } = statusConfig[wsStatus];

  const statusIcon =
    wsStatus === "connecting" ? <RefreshCw size={12} className="animate-spin" /> :
    wsStatus === "open" ? <Wifi size={12} /> :
    <WifiOff size={12} />;

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-500 to-blue-700 flex items-center justify-center">
          <Bot size={18} className="text-white" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-gray-900 dark:text-white">
            MIF Glue Job Agent
          </h1>
          <p className="text-xs text-gray-500">
            mif-ingest-to-lakehouse-infra-dev
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* WS Status indicator */}
        <div className={cn("flex items-center gap-1.5 text-xs", color)}>
          {statusIcon}
          <span>{label}</span>
        </div>

        {/* New session button */}
        <button
          onClick={onNewSession}
          className="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          + New Job
        </button>
      </div>
    </header>
  );
}
