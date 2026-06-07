"use client";

import React from "react";
import { ExternalLink, GitBranch, FileText, PartyPopper } from "lucide-react";

interface PRSuccessCardProps {
  prUrl: string;
  branchName: string;
  filesModified: string[];
}

export function PRSuccessCard({ prUrl, branchName, filesModified }: PRSuccessCardProps) {
  return (
    <div className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-2 border-green-400 rounded-xl p-5 mt-2 max-w-lg">
      <div className="flex items-center gap-2 mb-4">
        <PartyPopper size={20} className="text-green-600" />
        <h3 className="font-bold text-green-800 dark:text-green-300 text-sm">
          Pull Request Created Successfully!
        </h3>
      </div>

      <div className="space-y-3">
        <a
          href={prUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <ExternalLink size={14} />
          View Pull Request
        </a>

        <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
          <GitBranch size={12} />
          <code className="font-mono bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded">
            {branchName}
          </code>
        </div>

        {filesModified.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-1">
              Files in PR:
            </p>
            {filesModified.map((f, i) => (
              <div key={i} className="flex items-center gap-1 text-xs text-gray-500">
                <FileText size={10} />
                <code className="font-mono">{f}</code>
              </div>
            ))}
          </div>
        )}

        <p className="text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded px-3 py-2">
          ⚠️ This PR will <strong>not</strong> be auto-merged. A team member must review and approve it.
        </p>
      </div>
    </div>
  );
}
