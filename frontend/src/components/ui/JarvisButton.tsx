"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

// ── Types ──────────────────────────────────────────────────────────────────────
type RecordingState = "idle" | "listening" | "processing";

interface Toast {
  id: number;
  type: "success" | "error" | "info";
  message: string;
}

interface JarvisResponse {
  action: "navigate" | "respond" | "unknown" | "error";
  target?: string;
  label?: string;
  transcript?: string;
  message?: string;
  voice?: string;
}

// ── Web Speech API type augmentation ─────────────────────────────────────────
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}
interface SpeechRecognitionResultList {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}
interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
}
interface SpeechRecognitionAlternative {
  readonly transcript: string;
  readonly confidence: number;
}
interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onstart: ((e: Event) => void) | null;
  onend: ((e: Event) => void) | null;
  onerror: ((e: Event & { error: string }) => void) | null;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onspeechend: ((e: Event) => void) | null;
}

declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognitionInstance;
    webkitSpeechRecognition: new () => SpeechRecognitionInstance;
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
let toastCounter = 0;
const nextToastId = () => ++toastCounter;

// ── Component ──────────────────────────────────────────────────────────────────
export default function JarvisButton() {
  const [state, setState] = useState<RecordingState>("idle");
  const [interimText, setInterimText] = useState("");   // live partial words
  const [finalText, setFinalText] = useState("");        // committed words
  const [responseText, setResponseText] = useState("");
  const [statusLabel, setStatusLabel] = useState("Jarvis");
  const [statusColor, setStatusColor] = useState("#10b981");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isVisible, setIsVisible] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const [hasWebSpeech, setHasWebSpeech] = useState(false);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const accumulatedFinalRef = useRef<string>("");       // collects final segments
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const router = useRouter();

  const publicApiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  // ── Detect Web Speech API support ────────────────────────────────────────────
  useEffect(() => {
    const supported =
      typeof window !== "undefined" &&
      (!!window.SpeechRecognition || !!window.webkitSpeechRecognition);
    setHasWebSpeech(supported);
    if (!supported) {
      console.warn("[Jarvis] Web Speech API not available in this browser.");
    }
  }, []);

  // ── Mount animation ───────────────────────────────────────────────────────────
  useEffect(() => {
    const t = setTimeout(() => setIsVisible(true), 600);
    return () => clearTimeout(t);
  }, []);

  // ── Audio element for TTS ─────────────────────────────────────────────────────
  useEffect(() => {
    audioRef.current = new Audio();
    return () => { audioRef.current?.pause(); };
  }, []);

  // ── Toast management ──────────────────────────────────────────────────────────
  const addToast = useCallback((type: Toast["type"], message: string, duration = 4500) => {
    const id = nextToastId();
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), duration);
  }, []);

  const dismissToast = (id: number) =>
    setToasts((prev) => prev.filter((t) => t.id !== id));

  // ── Set status helper ─────────────────────────────────────────────────────────
  const setStatus = (label: string, color: string) => {
    setStatusLabel(label);
    setStatusColor(color);
  };

  // ── Intent API call (text → SSE response) ────────────────────────────────────
  // Sends ONLY the transcript text — no audio upload, no ASR wait.
  // This is called after the browser's Web Speech API gives us the final text.
  const sendTextForIntent = useCallback(async (transcript: string) => {
    if (!transcript.trim()) {
      setState("idle");
      setStatus("Jarvis", "#10b981");
      return;
    }

    setState("processing");
    setStatus("Thinking…", "#f59e0b");

    try {
      const formData = new FormData();
      formData.append("text", transcript);

      const response = await fetch(`${publicApiUrl}/api/jarvis/intent/stream`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok || !response.body) {
        addToast("error", "Jarvis could not process your request.");
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        let currentEvent = "";
        let currentData = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            currentData = line.slice(6).trim();
          } else if (line === "" && currentEvent && currentData) {
            await handleSSEEvent(currentEvent, currentData);
            currentEvent = "";
            currentData = "";
          }
        }
      }
    } catch {
      addToast("error", "Could not reach Jarvis. Is the backend running?");
    } finally {
      setState("idle");
      setStatus("Jarvis", "#10b981");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [publicApiUrl]);

  // ── SSE event handler ─────────────────────────────────────────────────────────
  const handleSSEEvent = async (event: string, rawData: string) => {
    let data: Record<string, unknown>;
    try { data = JSON.parse(rawData) as Record<string, unknown>; }
    catch { return; }

    switch (event) {
      case "response": {
        const resp = data as unknown as JarvisResponse;
        setStatus("Responding…", "#3b82f6");

        if (resp.action === "navigate" && resp.target) {
          addToast("success", `Navigating to ${resp.label ?? resp.target}…`);
          if (resp.voice) void playTTS(resp.voice);
          setTimeout(() => {
            setShowPanel(false);
            setInterimText("");
            setFinalText("");
            setResponseText("");
            accumulatedFinalRef.current = "";
            router.push(resp.target!);
          }, 900);
        } else if (resp.action === "respond" && resp.message) {
          setResponseText(resp.message);
          if (resp.voice) void playTTS(resp.voice);
        } else if (resp.action === "unknown") {
          addToast("info", resp.message ?? "I didn't catch that. Try saying a company name.");
        } else if (resp.action === "error") {
          addToast("error", resp.message ?? "Something went wrong.");
        }
        break;
      }
      case "error": {
        addToast("error", (data.message as string) ?? "Jarvis error.");
        break;
      }
      case "done": {
        setStatus("Jarvis", "#10b981");
        break;
      }
    }
  };

  // ── TTS playback ──────────────────────────────────────────────────────────────
  const playTTS = async (text: string) => {
    try {
      const fd = new FormData();
      fd.append("text", text);
      const res = await fetch(`${publicApiUrl}/api/jarvis/speak`, { method: "POST", body: fd });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.src = url;
        void audioRef.current.play();
        audioRef.current.onended = () => URL.revokeObjectURL(url);
      }
    } catch { /* non-fatal */ }
  };

  // ── Web Speech Recognition ────────────────────────────────────────────────────
  const startListening = useCallback(() => {
    if (state !== "idle" || !hasWebSpeech) return;

    const SpeechRecognition =
      window.SpeechRecognition ?? window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.continuous = true;      // keep mic open across pauses
    recognition.interimResults = true;  // show words as they come
    recognition.lang = "en-US";
    recognition.maxAlternatives = 1;

    accumulatedFinalRef.current = "";
    setInterimText("");
    setFinalText("");
    setResponseText("");
    setShowPanel(true);
    setState("listening");
    setStatus("Listening…", "#ef4444");

    recognition.onresult = (e: SpeechRecognitionEvent) => {
      // Reset silence timer every time speech is detected
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);

      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i];
        if (result.isFinal) {
          accumulatedFinalRef.current += result[0].transcript + " ";
        } else {
          interim += result[0].transcript;
        }
      }

      setFinalText(accumulatedFinalRef.current);
      setInterimText(interim);

      // Auto-submit after 2s of silence (user stopped speaking mid-continuous session)
      silenceTimerRef.current = setTimeout(() => {
        recognition.stop();
      }, 2000);
    };

    recognition.onspeechend = () => {
      // Speech ended — give a 400ms grace period then stop
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = setTimeout(() => recognition.stop(), 400);
    };

    recognition.onend = () => {
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      const fullTranscript = (accumulatedFinalRef.current + interimText).trim();
      setInterimText("");
      setFinalText(fullTranscript);
      if (fullTranscript) {
        void sendTextForIntent(fullTranscript);
      } else {
        setState("idle");
        setStatus("Jarvis", "#10b981");
      }
    };

    recognition.onerror = (e: Event & { error: string }) => {
      if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
      const errorCode = e.error;
      if (errorCode === "not-allowed") {
        addToast("error", "Microphone access denied. Please allow mic permissions.");
      } else if (errorCode !== "no-speech" && errorCode !== "aborted") {
        addToast("error", `Speech error: ${errorCode}`);
      }
      setState("idle");
      setStatus("Jarvis", "#10b981");
    };

    recognitionRef.current = recognition;
    recognition.start();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, hasWebSpeech, sendTextForIntent]);

  const stopListening = useCallback(() => {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    recognitionRef.current?.stop();
  }, []);

  // ── Keyboard shortcut: J ──────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "j" || e.key === "J") {
        if (state === "idle") startListening();
        else if (state === "listening") stopListening();
      }
      if (e.key === "Escape" && state === "listening") stopListening();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [state, startListening, stopListening]);

  // ── Derived ───────────────────────────────────────────────────────────────────
  const isListening = state === "listening";
  const isProcessing = state === "processing";
  const displayText = finalText + interimText;
  const buttonLabel =
    isListening ? "Stop listening" :
    isProcessing ? "Processing…" :
    hasWebSpeech ? "Press J or click to speak" : "Web Speech API not supported";

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`
        @keyframes jarvis-ring-pulse {
          0%, 100% { transform: scale(1); opacity: 0.6; }
          50%       { transform: scale(1.6); opacity: 0; }
        }
        @keyframes jarvis-glow-idle {
          0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0.5), 0 8px 32px rgba(59,130,246,0.3); }
          50%       { box-shadow: 0 0 0 8px rgba(59,130,246,0), 0 8px 32px rgba(59,130,246,0.45); }
        }
        @keyframes jarvis-toast-in {
          from { opacity: 0; transform: translateX(60px); }
          to   { opacity: 1; transform: translateX(0); }
        }
        @keyframes jarvis-panel-in {
          from { opacity: 0; transform: translateY(12px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes jarvis-btn-in {
          from { opacity: 0; transform: translateY(20px) scale(0.8); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes jarvis-dot {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40%           { transform: scale(1); opacity: 1; }
        }
        @keyframes jarvis-cursor-blink {
          0%, 100% { opacity: 1; }
          50%      { opacity: 0; }
        }
        .jarvis-ring {
          position: absolute; inset: -10px; border-radius: 9999px;
          border: 2px solid rgba(239,68,68,0.7);
          animation: jarvis-ring-pulse 1.4s ease-out infinite;
        }
        .jarvis-ring-2 { animation-delay: 0.7s; }
        .jarvis-btn-enter { animation: jarvis-btn-in 0.5s cubic-bezier(0.34,1.56,0.64,1) forwards; }
        .jarvis-toast-enter { animation: jarvis-toast-in 0.3s cubic-bezier(0.34,1.56,0.64,1); }
        .jarvis-panel-enter { animation: jarvis-panel-in 0.25s ease-out; }
        .jarvis-idle-glow { animation: jarvis-glow-idle 3s ease-in-out infinite; }
        .jarvis-dot-1 { animation: jarvis-dot 1.2s ease-in-out infinite; }
        .jarvis-dot-2 { animation: jarvis-dot 1.2s ease-in-out infinite 0.2s; }
        .jarvis-dot-3 { animation: jarvis-dot 1.2s ease-in-out infinite 0.4s; }
        .jarvis-cursor {
          display: inline-block; width: 2px; height: 0.9em;
          background: #ef4444; margin-left: 2px; vertical-align: text-bottom;
          animation: jarvis-cursor-blink 0.7s steps(1) infinite;
        }
      `}</style>

      {/* ── Status panel ─────────────────────────────────────────────────────── */}
      {showPanel && (
        <div
          className="jarvis-panel-enter fixed bottom-24 right-6 z-50 w-80 rounded-2xl border border-white/10 bg-slate-900/95 p-4 shadow-2xl backdrop-blur-md"
          style={{ boxShadow: "0 8px 40px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.05)" }}
        >
          {/* Header */}
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div
                className="h-2 w-2 rounded-full transition-all duration-500"
                style={{ background: statusColor, boxShadow: `0 0 7px ${statusColor}` }}
              />
              <span className="text-xs font-semibold uppercase tracking-widest text-slate-300">
                {statusLabel}
              </span>
            </div>
            <button
              onClick={() => {
                setShowPanel(false);
                if (state === "listening") stopListening();
              }}
              className="rounded-full p-1 text-slate-500 transition-colors hover:text-slate-300"
              aria-label="Close Jarvis panel"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>

          {/* Live transcript box — shown while listening AND after */}
          {(displayText || isListening) && (
            <div className="rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-2.5 min-h-[2.5rem]">
              <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-1">You said</p>
              <p className="text-xs leading-relaxed">
                {/* Committed (final) words — bright white */}
                {finalText && (
                  <span className="text-slate-100">{finalText}</span>
                )}
                {/* Interim (partial) words — dimmed */}
                {interimText && (
                  <span className="text-slate-400 italic">{interimText}</span>
                )}
                {/* Blinking cursor while listening */}
                {isListening && <span className="jarvis-cursor" />}
              </p>
            </div>
          )}

          {/* Thinking state */}
          {isProcessing && (
            <div className="mt-2 flex items-center gap-2 text-amber-400/80">
              <span className="flex gap-1">
                <span className="jarvis-dot-1 h-1.5 w-1.5 rounded-full bg-amber-400 inline-block" />
                <span className="jarvis-dot-2 h-1.5 w-1.5 rounded-full bg-amber-400 inline-block" />
                <span className="jarvis-dot-3 h-1.5 w-1.5 rounded-full bg-amber-400 inline-block" />
              </span>
              <span className="text-xs">Jarvis is thinking…</span>
            </div>
          )}

          {/* Response */}
          {responseText && !isProcessing && (
            <div className="mt-2 rounded-lg border border-blue-900/40 bg-blue-950/30 px-3 py-2">
              <p className="text-[10px] uppercase tracking-widest text-blue-400/60 mb-1">Jarvis</p>
              <p className="text-xs text-slate-200 leading-relaxed">{responseText}</p>
            </div>
          )}

          {/* Footer hint */}
          {state === "idle" && !responseText && (
            <p className="mt-3 text-[10px] text-slate-600">
              Press{" "}
              <kbd className="rounded border border-slate-700 px-1 py-0.5 font-mono text-[10px] text-slate-500">
                J
              </kbd>{" "}
              or click the mic to speak
            </p>
          )}
        </div>
      )}

      {/* ── Toast notifications ───────────────────────────────────────────────── */}
      <div
        className="fixed right-6 z-[60] flex flex-col gap-2 items-end pointer-events-none"
        style={{ bottom: showPanel ? "calc(1.5rem + 6rem + 0.75rem + 10rem)" : "6rem" }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="jarvis-toast-enter pointer-events-auto flex items-start gap-2.5 rounded-xl px-4 py-3 shadow-xl max-w-xs"
            style={{
              background:
                toast.type === "success" ? "linear-gradient(135deg,#065f46,#047857)"
                : toast.type === "error" ? "linear-gradient(135deg,#7f1d1d,#b91c1c)"
                : "linear-gradient(135deg,#1e3a5f,#1d4ed8)",
              border:
                toast.type === "success" ? "1px solid rgba(52,211,153,0.3)"
                : toast.type === "error" ? "1px solid rgba(248,113,113,0.3)"
                : "1px solid rgba(147,197,253,0.3)",
            }}
          >
            <span className="mt-0.5 text-base">
              {toast.type === "success" ? "✓" : toast.type === "error" ? "✕" : "ℹ"}
            </span>
            <p className="text-xs text-white leading-relaxed flex-1">{toast.message}</p>
            <button
              onClick={() => dismissToast(toast.id)}
              className="ml-1 text-white/50 hover:text-white transition-colors text-xs"
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {/* ── Floating mic button ───────────────────────────────────────────────── */}
      <div
        className={`fixed bottom-6 right-6 z-50 ${isVisible ? "jarvis-btn-enter" : "opacity-0"}`}
        style={{ opacity: isVisible ? 1 : 0 }}
      >
        {/* Tooltip */}
        <div
          className="pointer-events-none absolute -top-9 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-white/10 bg-slate-900/90 px-2.5 py-1 text-[10px] text-slate-300 backdrop-blur"
          style={{ opacity: state === "idle" ? 0.85 : 0, transition: "opacity 0.3s" }}
        >
          {buttonLabel}
        </div>

        {/* Pulse rings while listening */}
        {isListening && (
          <>
            <div className="jarvis-ring" />
            <div className="jarvis-ring jarvis-ring-2" />
          </>
        )}

        {/* Main button */}
        <button
          id="jarvis-voice-button"
          onClick={() => {
            if (state === "idle") startListening();
            else if (state === "listening") stopListening();
          }}
          disabled={isProcessing || !hasWebSpeech}
          aria-label={buttonLabel}
          aria-pressed={isListening}
          className={`relative flex h-14 w-14 items-center justify-center rounded-full transition-all duration-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${!isListening && !isProcessing ? "jarvis-idle-glow" : ""}`}
          style={{
            background:
              isListening ? "linear-gradient(135deg,#dc2626,#b91c1c)"
              : isProcessing ? "linear-gradient(135deg,#d97706,#b45309)"
              : "linear-gradient(135deg,#2563eb,#1d4ed8)",
            boxShadow: isListening
              ? "0 0 0 0 transparent, 0 8px 24px rgba(220,38,38,0.5)"
              : isProcessing ? "0 8px 24px rgba(217,119,6,0.4)"
              : undefined,
          }}
        >
          {isProcessing ? (
            <span className="flex gap-1">
              <span className="jarvis-dot-1 h-1.5 w-1.5 rounded-full bg-white inline-block" />
              <span className="jarvis-dot-2 h-1.5 w-1.5 rounded-full bg-white inline-block" />
              <span className="jarvis-dot-3 h-1.5 w-1.5 rounded-full bg-white inline-block" />
            </span>
          ) : isListening ? (
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-white" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-6 w-6 text-white">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
            </svg>
          )}
        </button>

        {/* J badge */}
        {state === "idle" && (
          <span
            className="absolute -bottom-1 -left-1 flex h-4 w-4 items-center justify-center rounded-full border border-slate-600 bg-slate-800 text-[9px] font-bold text-slate-400"
            aria-hidden="true"
          >
            J
          </span>
        )}
      </div>
    </>
  );
}