"use client";

import React from "react";

interface SummaryTableProps {
  rows: Array<{ field: string; value: string }>;
}

export function SummaryTable({ rows }: SummaryTableProps) {
  return (
    <div className="w-full max-w-lg rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden mt-2">
      <table className="w-full text-xs">
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className={
                i % 2 === 0
                  ? "bg-gray-50 dark:bg-gray-800/50"
                  : "bg-white dark:bg-gray-900"
              }
            >
              <td className="px-4 py-2.5 font-semibold text-gray-600 dark:text-gray-400 w-48">
                {row.field}
              </td>
              <td className="px-4 py-2.5 text-gray-900 dark:text-gray-200 font-mono">
                {row.value || <span className="text-gray-400 italic">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
