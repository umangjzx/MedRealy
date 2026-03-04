/**
 * LiveTranscript — displays the rolling real-time transcript during recording.
 * Shows a blinking cursor, word count, and auto-scrolls as text arrives.
 */
/**
 * LiveTranscript — displays the rolling real-time transcript during recording.
 * Shows a blinking cursor, word count, and auto-scrolls as text arrives.
 * Includes AI Copilot side panel for real-time insights.
 */
import { useEffect, useRef, useState } from "react";

const INSIGHT_TRIGGERS = [
  { regex: /bp|blood pressure/i, message: "Monitoring Vitals...", type: "info" },
  { regex: /hypotens|shock/i, message: "⚠ Potential Hemodynamic Instability", type: "warning" },
  { regex: /sepsis|septic/i, message: "⚠ Sepsis Protocol Activation Recommended", type: "critical" },
  { regex: /allergy|allergies|penicillin/i, message: "Checking interaction database...", type: "info" },
  { regex: /temperature|fever/i, message: "Analyzing infection markers...", type: "info" },
  { regex: /pain/i, message: "Assess pain scale (0-10)", type: "action" },
  { regex: /lab|labs|wbc|lactate/i, message: "Cross-referencing normal ranges...", type: "info" }
];

export default function LiveTranscript({ transcript }) {
  const bottomRef = useRef(null);
  const [insights, setInsights] = useState([]);
  const [lastProcessedLength, setLastProcessedLength] = useState(0);

  // Auto-scroll to bottom as new text arrives
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  // Simulate AI Insights based on keywords
  useEffect(() => {
    if (!transcript) return;
    const newText = transcript.slice(lastProcessedLength);
    if (newText.length > 3) {
       INSIGHT_TRIGGERS.forEach(trigger => {
          if (trigger.regex.test(newText)) {
             addInsight(trigger.message, trigger.type);
          }
       });
       setLastProcessedLength(transcript.length);
    }
  }, [transcript]);

  const addInsight = (msg, type) => {
    const id = Date.now() + Math.random();
    setInsights(prev => {
        const similar = prev.find(p => p.msg === msg);
        if (similar) return prev;
        return [...prev.slice(-4), { id, msg, type }];
    });
    
    // Auto remove after 5s
    setTimeout(() => {
       setInsights(prev => prev.filter(i => i.id !== id));
    }, 5000);
  };

  const wordCount = transcript ? transcript.trim().split(/\s+/).filter(Boolean).length : 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 animate-fadeIn">
      {/* Main Transcript Area */}
      <div className="md:col-span-2 glass rounded-xl overflow-hidden flex flex-col h-64 border border-indigo-500/30 shadow-[0_0_15px_rgba(99,102,241,0.1)]">
        <div className="flex items-center justify-between px-4 py-2 border-b border-white/10 bg-black/20">
          <div className="flex items-center gap-2">
            <span className={`relative flex h-3 w-3`}>
               <span className={`animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75 ${transcript ? "block" : "hidden"}`}></span>
               <span className={`relative inline-flex rounded-full h-3 w-3 ${transcript ? "bg-red-500" : "bg-slate-500"}`}></span>
            </span>
            <span className="text-xs font-bold uppercase tracking-widest text-slate-300">Live Transcript</span>
          </div>
          {wordCount > 0 && (
            <span className="text-[10px] font-mono text-slate-400 border border-slate-700 px-2 py-0.5 rounded">{wordCount} wds</span>
          )}
        </div>
        <div className="flex-1 overflow-y-auto p-5 font-mono text-sm leading-relaxed text-slate-200 bg-slate-950/30 relative">
          {transcript ? (
            <p className="whitespace-pre-wrap">
              {transcript}
              <span className="inline-block w-1.5 h-4 bg-cyan-400 ml-1 animate-pulse align-middle shadow-[0_0_8px_cyan]" />
            </p>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-2">
                 <div className="w-12 h-12 rounded-full border-2 border-slate-700 border-t-cyan-500 animate-spin opacity-20"></div>
                 <p className="italic">Listening for clinical speech...</p>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* AI Copilot Side Panel */}
      <div className="glass rounded-xl overflow-hidden flex flex-col h-64 border border-cyan-500/20 bg-slate-900/40 relative">
         <div className="px-4 py-2 border-b border-white/5 bg-cyan-950/10 flex justify-between items-center">
             <span className="text-xs font-bold uppercase tracking-widest text-cyan-400 flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                AI Copilot
             </span>
             <span className="text-[10px] bg-cyan-900/40 text-cyan-300 px-1.5 rounded">ONLINE</span>
         </div>
         
         <div className="flex-1 p-3 space-y-2 overflow-hidden relative">
             <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-5 pointer-events-none"></div>
             
             {insights.length === 0 && (
                 <div className="text-center mt-10 opacity-30">
                     <p className="text-4xl mb-2">🧠</p>
                     <p className="text-xs uppercase tracking-wider">Analyzing context...</p>
                 </div>
             )}

             {insights.map((insight) => (
                 <div key={insight.id} className={`transform transition-all duration-500 animate-slideUp p-3 rounded border-l-2 shadow-lg backdrop-blur-md ${
                     insight.type === 'critical' ? 'bg-red-950/40 border-red-500 text-red-200' :
                     insight.type === 'warning' ? 'bg-orange-950/40 border-orange-500 text-orange-200' :
                     insight.type === 'action' ? 'bg-purple-950/40 border-purple-500 text-purple-200' :
                     'bg-cyan-950/40 border-cyan-500 text-cyan-200'
                 }`}>
                     <div className="flex items-start gap-2">
                         <span className="mt-0.5 text-xs">
                             {insight.type === 'critical' ? '🔴' : insight.type === 'warning' ? '⚠' : insight.type === 'action' ? '⚡' : 'ℹ'}
                         </span>
                         <span className="text-xs font-medium">{insight.msg}</span>
                     </div>
                 </div>
             ))}
         </div>
         
         {/* Fake processing bar */}
         <div className="h-1 bg-slate-800 w-full overflow-hidden">
             <div className="h-full bg-cyan-500/50 w-1/3 animate-progress"></div>
         </div>
      </div>
    </div>
  );
}
