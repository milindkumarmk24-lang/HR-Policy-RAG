"use client";

import { useEffect, useRef, useState } from "react";
import { MicIcon, SendIcon, StopIcon } from "./Icons";

// Minimal typing for the Web Speech API (Chrome, Edge, Safari).
type Recognition = {
  lang: string; interimResults: boolean; continuous: boolean;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null; onerror: (() => void) | null;
  start: () => void; stop: () => void;
};

export default function Composer({ busy, disabled, onSend, onStop }: {
  busy: boolean; disabled: boolean; onSend: (q: string) => void; onStop: () => void;
}) {
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [speechOk, setSpeechOk] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);
  const rec = useRef<Recognition | null>(null);

  useEffect(() => {
    const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
    setSpeechOk(Boolean(w.SpeechRecognition || w.webkitSpeechRecognition));
  }, []);

  useEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  function submit() {
    const q = text.trim();
    if (!q || busy || disabled) return;
    onSend(q);
    setText("");
  }

  function toggleMic() {
    if (listening) {
      rec.current?.stop();
      return;
    }
    const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) return;
    const r = new Ctor();
    r.lang = navigator.language || "en-IN";
    r.interimResults = true;
    r.continuous = false;
    const before = text ? text.trimEnd() + " " : "";
    r.onresult = (e) => {
      const said = Array.from(e.results).map((res) => res[0].transcript).join("");
      setText(before + said);
    };
    r.onend = () => { setListening(false); area.current?.focus(); };
    r.onerror = () => setListening(false);
    rec.current = r;
    setListening(true);
    r.start();
  }

  return (
    <div className="composer-wrap">
      <form className="composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <label htmlFor="question" className="sr-only">Ask about your handbook</label>
        <textarea
          id="question"
          ref={area}
          rows={1}
          value={text}
          placeholder={disabled ? "Add a handbook to start asking" : listening ? "Listening…" : "Ask a policy question"}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
        />
        {speechOk && (
          <button type="button" className="icon-btn" aria-pressed={listening} disabled={disabled}
                  aria-label={listening ? "Stop dictation" : "Ask by voice"} title={listening ? "Stop dictation" : "Ask by voice"}
                  onClick={toggleMic}>
            <MicIcon />
          </button>
        )}
        {busy ? (
          <button type="button" className="btn" onClick={onStop} aria-label="Stop answering"><StopIcon size={16} /> Stop</button>
        ) : (
          <button type="submit" className="btn btn-primary" disabled={!text.trim() || disabled}>
            <SendIcon size={16} /> Ask
          </button>
        )}
      </form>
      <p className="composer-hint">Answers come only from the uploaded handbook and cite the section they used. Check anything important with HR.</p>
    </div>
  );
}
