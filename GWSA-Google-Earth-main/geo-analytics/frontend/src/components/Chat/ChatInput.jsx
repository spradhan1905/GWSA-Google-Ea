/**
 * GWSA GeoAnalytics — ChatInput
 * Input bar with send button.
 */
import React, { useState, useRef } from 'react';
import { Send } from 'lucide-react';

export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('');
  const inputRef = useRef(null);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!text.trim() || disabled) return;
    onSend(text.trim());
    setText('');
    inputRef.current?.focus();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="shrink-0 px-4 py-3 border-t border-gwsa-border">
      <div className="flex items-center gap-2 bg-gwsa-bg-alt rounded-xl border border-gwsa-border focus-within:border-gwsa-accent/50 focus-within:shadow-glow transition-all duration-200">
        <input
          ref={inputRef}
          type="text"
          placeholder="Ask about store performance..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          className="flex-1 bg-transparent border-none text-sm text-gwsa-text placeholder:text-gwsa-text-muted px-4 py-2.5 focus:outline-none focus:ring-0"
          maxLength={2000}
        />
        <button
          onClick={handleSubmit}
          disabled={!text.trim() || disabled}
          className="p-2 mr-1 rounded-lg bg-gwsa-accent hover:bg-gwsa-accent-hover text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200 active:scale-95"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
      <p className="text-[10px] text-gwsa-text-muted mt-1.5 text-center">
        Powered by Gemini AI · Responses may not be 100% accurate
      </p>
    </div>
  );
}
