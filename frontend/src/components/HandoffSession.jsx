/**
 * HandoffSession — Active recording screen
 * Shows a waveform animation, elapsed timer, stage status, and End Handoff button.
 */
import React, { useEffect, useRef, useState, useCallback } from "react";

const STAGE_LABELS = {
  listening:    "Listening — recording in progress",
  transcribing: "Transcribing audio…",
  extracting:   "Extracting SBAR data from transcript…",
  sentinel:     "Running risk checks…",
  bridge:       "Generating handoff report…",
};

// Simple animated sound-wave bar
function WaveBar({ delay }) {
  return (
    <span
      className="inline-block w-1 bg-blue-400 rounded-full mx-0.5"
      style={{
        height: "100%",
        animation: `wave 1.2s ease-in-out ${delay}s infinite alternate`,
      }}
    />
  );
}

/**
 * Pick a supported mimeType for MediaRecorder.
 * Safari doesn't support audio/webm, so fall back to audio/mp4 or default.
 */
function getSupportedMimeType() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
    "",
  ];
  for (const mime of candidates) {
    if (!mime || MediaRecorder.isTypeSupported(mime)) return mime || undefined;
  }
  return undefined;
}

export default function HandoffSession({ onEnd, stage, sendAudio }) {
  const mediaRecorderRef = useRef(null);
  const streamRef        = useRef(null);
  const sendAudioRef     = useRef(sendAudio);
  const [elapsed, setElapsed] = useState(0);
  const [recording, setRecording] = useState(false);
  const [micError, setMicError]   = useState("");
  const timerRef = useRef(null);

  // Keep sendAudio ref current to avoid stale closure in MediaRecorder callback
  useEffect(() => { sendAudioRef.current = sendAudio; }, [sendAudio]);

  const isProcessing = ["transcribing", "extracting", "sentinel", "bridge"].includes(stage);

  // Stop timer when processing starts
  useEffect(() => {
    if (isProcessing && timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, [isProcessing]);

  // ── Start microphone on mount ──────────────────────────────────────────
  useEffect(() => {
    let active = true;

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        if (!active) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;

        const mimeType = getSupportedMimeType();
        const recorderOptions = mimeType ? { mimeType } : {};
        const recorder = new MediaRecorder(stream, recorderOptions);
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            e.data.arrayBuffer().then((buf) => sendAudioRef.current?.(new Uint8Array(buf)));
          }
        };

        recorder.start(2000); // emit chunks every 2 seconds
        setRecording(true);
      })
      .catch((err) => {
        setMicError(`Microphone error: ${err.message}`);
      });

    // Elapsed timer
    timerRef.current = setInterval(() => {
      setElapsed((s) => s + 1);
    }, 1000);

    return () => {
      active = false;
      clearInterval(timerRef.current);
      timerRef.current = null;
      if (mediaRecorderRef.current?.state !== "inactive") {
        mediaRecorderRef.current?.stop();
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const formatTime = (s) => {
    const m = String(Math.floor(s / 60)).padStart(2, "0");
    const sec = String(s % 60).padStart(2, "0");
    return `${m}:${sec}`;
  };

  const handleEnd = useCallback(() => {
    clearInterval(timerRef.current);
    timerRef.current = null;
    if (mediaRecorderRef.current?.state !== "inactive") {
      mediaRecorderRef.current?.stop();
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    setRecording(false);
    onEnd?.();
  }, [onEnd]);

  return (
    <div className="glass rounded-2xl p-6 sm:p-7 animate-slideUp">
      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold">Active Handoff</h2>
          <p className="text-xs text-slate-400 mt-0.5">Recording and processing in real-time</p>
        </div>
        <div className="text-2xl font-mono text-cyan-300">{formatTime(elapsed)}</div>
      </div>

      {/* Waveform or processing spinner */}
      <div className="flex items-center justify-center h-16 mb-6">
        {isProcessing ? (
          <div className="flex items-center gap-3 text-slate-300 glass rounded-xl px-4 py-2">
            <svg className="animate-spin w-5 h-5 text-cyan-400" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <span className="text-sm">{STAGE_LABELS[stage] || stage}</span>
          </div>
        ) : (
          <div className="flex items-end gap-0.5 h-12 animate-pulse-glow rounded-lg px-3" aria-label="Recording waveform">
            {[0,.1,.2,.35,.45,.15,.3,.05,.25,.4].map((d, i) => (
              <WaveBar key={i} delay={d} />
            ))}
          </div>
        )}
      </div>

      {/* Status text */}
      {!isProcessing && (
        <p className="text-center text-sm text-slate-400 mb-6">
          {micError || (recording ? "🎙 Recording — speak normally" : "Starting microphone…")}
        </p>
      )}

      {/* End Button (only when actually recording) */}
      {!isProcessing && (
        <button
          onClick={handleEnd}
          disabled={!recording}
          className="w-full p-4 btn-danger disabled:opacity-50 rounded-xl text-lg font-semibold"
        >
          End Handoff
        </button>
      )}
    </div>
  );
}
