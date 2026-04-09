import { useState, useRef, useCallback } from 'react';

export function useVoiceInput({ onResult, onError }) {
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef(null);

  const isSupported = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;

  const startRecording = useCallback(() => {
    if (!isSupported) {
      onError?.('Voice input not supported in this browser. Use Chrome.');
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.lang = 'en-IN'; // Indian English
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => setIsRecording(true);

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      onResult?.(transcript);
      setIsRecording(false);
    };

    recognition.onerror = (event) => {
      onError?.(`Voice error: ${event.error}`);
      setIsRecording(false);
    };

    recognition.onend = () => setIsRecording(false);

    recognitionRef.current = recognition;
    recognition.start();
  }, [isSupported, onResult, onError]);

  const stopRecording = useCallback(() => {
    recognitionRef.current?.stop();
    setIsRecording(false);
  }, []);

  return { isRecording, isSupported, startRecording, stopRecording };
}
