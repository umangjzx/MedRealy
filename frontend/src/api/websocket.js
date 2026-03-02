/**
 * MedRelay WebSocket hook
 * Connects to ws://localhost:8000/ws/handoff and manages message flow.
 */
import { useState, useRef, useCallback, useEffect } from "react";

const WS_BASE = `ws://${window.location.hostname}:8000/ws/handoff`;

const INITIAL_STATE = {
  stage: "listening",
  transcript: "",
  sbar: null,
  alerts: [],
  report: null,
  message: "",
};

/**
 * @param {Object} callbacks
 * @param {Function} callbacks.onComplete  - called with final FinalReport data
 * @param {Function} callbacks.onError     - called with error message string
 */
export function useWebSocket({ onComplete, onError } = {}) {
  const [sessionState, setSessionState] = useState({ ...INITIAL_STATE });

  const ws = useRef(null);
  // Use refs for callbacks to avoid stale closures
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);

  useEffect(() => { onCompleteRef.current = onComplete; }, [onComplete]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (ws.current) {
        ws.current.close();
        ws.current = null;
      }
    };
  }, []);

  const handleMessage = useCallback((data) => {
    switch (data.stage) {
      case "listening":
        setSessionState((prev) => ({
          ...prev,
          stage: "listening",
          message: data.message || "",
        }));
        break;

      case "transcribing":
        setSessionState((prev) => ({
          ...prev,
          stage: "transcribing",
          message: data.message || "",
        }));
        break;

      case "extracting":
        setSessionState((prev) => ({
          ...prev,
          stage: "extracting",
          message: data.message || "",
        }));
        break;

      // Transcript update (partial during recording, or final after end)
      case "transcript":
        if (data.final) {
          // Replace entire transcript with the authoritative final version
          setSessionState((prev) => ({ ...prev, transcript: data.data }));
        } else {
          // Append partial segment
          setSessionState((prev) => ({
            ...prev,
            transcript: prev.transcript
              ? prev.transcript + " " + data.data
              : data.data,
          }));
        }
        break;

      case "extract":
        setSessionState((prev) => ({
          ...prev,
          stage: "sentinel",
          sbar: data.data,
        }));
        break;

      case "sentinel":
        setSessionState((prev) => ({
          ...prev,
          stage: "bridge",
          alerts: data.data,
        }));
        break;

      case "bridge":
        setSessionState((prev) => ({
          ...prev,
          stage: "bridge",
          report: data.data?.rendered,
        }));
        break;

      case "complete":
        setSessionState((prev) => ({
          ...prev,
          stage: "bridge",
          final: data.data,
        }));
        onCompleteRef.current?.(data.data);
        break;

      case "error":
        onErrorRef.current?.(data.message || "Unknown pipeline error");
        break;

      default:
        break;
    }
  }, []);

  /** Open connection and send the start message */
  const connect = useCallback(
    (outgoing, incoming, token) => {
      // Close any existing connection
      if (ws.current) {
        ws.current.close();
        ws.current = null;
      }

      // Reset state for new session
      setSessionState({ ...INITIAL_STATE });

      // Append JWT token as query param if provided
      const url = token ? `${WS_BASE}?token=${encodeURIComponent(token)}` : WS_BASE;
      const socket = new WebSocket(url);
      ws.current = socket;

      socket.onopen = () => {
        socket.send(JSON.stringify({ type: "start", outgoing, incoming }));
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleMessage(data);
        } catch {
          // ignore malformed frames
        }
      };

      socket.onerror = (e) => {
        console.error("WebSocket error", e);
        onErrorRef.current?.("WebSocket connection error. Is the backend running?");
      };

      socket.onclose = () => {
        console.log("WebSocket closed");
      };
    },
    [handleMessage]
  );

  /** Send a JSON control message (e.g. {"type": "end"}) */
  const sendMessage = useCallback((obj) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(obj));
    } else {
      console.warn("WebSocket not open, cannot send message:", obj);
    }
  }, []);

  /** Send a binary audio chunk */
  const sendAudio = useCallback((chunk) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(chunk);
    }
  }, []);

  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }
  }, []);

  return { connect, disconnect, sendMessage, sendAudio, sessionState };
}
