/**
 * LiveTranscript — displays the rolling real-time transcript during recording.
 * Shows a blinking cursor, word count, and auto-scrolls as text arrives.
 */
import { useEffect, useRef } from "react";

export default function LiveTranscript({ transcript }) {
  const bottomRef = useRef(null);

  // Auto-scroll to bottom as new text arrives
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  const wordCount = transcript ? transcript.trim().split(/\s+/).filter(Boolean).length : 0;

  return (
    <div className="glass rounded-xl mt-4 overflow-hidden animate-fadeIn">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700/80">
        <div className="flex items-center">
          <span className={`w-2 h-2 rounded-full mr-2 ${transcript ? "bg-green-400 animate-pulse" : "bg-slate-500"}`} />
          <span className="text-sm font-medium text-slate-300">Live Transcript</span>
        </div>
        {wordCount > 0 && (
          <span className="text-xs text-slate-500">{wordCount} words</span>
        )}
      </div>
      <div className="h-48 overflow-y-auto p-4 font-mono text-sm leading-relaxed text-slate-200 bg-slate-950/30">
        {transcript ? (
          <p className="whitespace-pre-wrap">
            {transcript}
            <span className="inline-block w-0.5 h-4 bg-cyan-400 ml-0.5 animate-pulse align-text-bottom" />
          </p>
        ) : (
          <p className="text-slate-500 italic">Transcript will appear here as you speak…</p>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
