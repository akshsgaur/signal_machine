"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  brief: string;
  loading: boolean;
}

function Skeleton() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-6 bg-zinc-800 rounded w-1/2" />
      <div className="h-4 bg-zinc-800 rounded w-full" />
      <div className="h-4 bg-zinc-800 rounded w-5/6" />
      <div className="h-4 bg-zinc-800 rounded w-4/6" />
      <div className="h-4 bg-zinc-800 rounded w-full mt-4" />
      <div className="h-4 bg-zinc-800 rounded w-3/4" />
    </div>
  );
}

export function DecisionBrief({ brief, loading }: Props) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 w-full h-full overflow-auto">
      <h3 className="text-white font-semibold mb-4">Decision Brief</h3>
      {loading || !brief ? (
        <Skeleton />
      ) : (
        <div className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{brief}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
