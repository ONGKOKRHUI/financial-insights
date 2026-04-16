"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";

export default function JarvisButton() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const router = useRouter();

  const publicApiUrl =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      chunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (e: BlobEvent) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorderRef.current.onstop = async () => {
        setIsProcessing(true);
        const audioBlob = new Blob(chunksRef.current, { type: "audio/webm" });
        await sendAudioToBackend(audioBlob);
        
        // Stop all audio tracks to release the microphone
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Error accessing microphone:", err);
      alert("Please allow microphone access to use Jarvis.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const sendAudioToBackend = async (audioBlob: Blob) => {
    const formData = new FormData();
    formData.append("file", audioBlob, "recording.webm");

    try {
      // Assuming your FastAPI backend handles this endpoint
      const response = await fetch(`${publicApiUrl}/api/jarvis/voice`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Failed to process voice command");

      const data = await response.json();
      
      // Execute the navigation command received from the backend
      if (data.action === "navigate" && data.target) {
        router.push(data.target);
      }
    } catch (error) {
      console.error("Error communicating with Jarvis:", error);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <button
      onMouseDown={startRecording}
      onMouseUp={stopRecording}
      onTouchStart={startRecording}
      onTouchEnd={stopRecording}
      disabled={isProcessing}
      className={`fixed bottom-6 right-6 p-4 rounded-full shadow-lg transition-all z-50 flex items-center justify-center
        ${isRecording ? "bg-red-500 animate-pulse" : "bg-blue-600 hover:bg-blue-700"}
        ${isProcessing ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
      `}
      title="Hold to talk to Jarvis"
    >
      {isProcessing ? (
        <span className="text-white text-sm font-semibold">...</span>
      ) : (
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6 text-white">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
        </svg>
      )}
    </button>
  );
}