/**
 * GWSA GeoAnalytics — ChatDrawer
 * Slide-up AI chat panel.
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { X, Sparkles, Minimize2, Maximize2 } from 'lucide-react';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import { sendChatMessage } from '../../services/api';

const WELCOME_MESSAGE = {
  role: 'assistant',
  content: `Welcome to **GWSA GeoAnalytics AI**.\n\nI can help you analyze store performance, compare locations, and explore financial trends across all Goodwill of San Antonio locations.\n\nTry asking:\n• "Which store has the highest revenue this year?"\n• "Compare door counts for Fredericksburg vs Culebra"\n• "What's the expense ratio trend for our outlets?"`,
};

export default function ChatDrawer({ open, onClose, storeContext }) {
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [sessionState, setSessionState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleSend = useCallback(async (text) => {
    if (!text.trim() || loading) return;

    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const history = messages.slice(-10).map(m => ({
        role: m.role,
        content: m.content,
      }));
      const res = await sendChatMessage(text, storeContext, history, sessionState);
      const data = res.data;
      if (data.session_state) {
        setSessionState(data.session_state);
      }
      const aiMsg = {
        role: 'assistant',
        content: data.reply || 'I couldn\'t generate a response. Please try again.',
        sqlUsed: data.sql_used,
        queryData: data.data,
        followups: data.followups,
        responseType: data.response_type,
        chart: data.chart,
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (err) {
      let errorMsg = 'Sorry, I encountered an error. Please try again.';
      if (err.code === 'ECONNABORTED') {
        errorMsg =
          'That took longer than expected, so the request was stopped. '
          + 'Try again with a narrower date range or a single focused question. '
          + 'If this keeps happening often, your team can raise the chat timeout in deployment settings.';
        if (import.meta.env.DEV) {
          errorMsg +=
            ' Dev note: `VITE_CHAT_TIMEOUT_MS` (frontend) and `AI_COMPLETION_TIMEOUT_SEC` (backend).';
        }
      } else if (typeof err.response?.data?.reply === 'string' && err.response.data.reply.trim()) {
        errorMsg = err.response.data.reply;
      } else if (err.response?.status === 429) {
        errorMsg = err.response?.data?.error || 'AI quota or rate limit reached. Please wait and try again later.';
      } else if (typeof err.response?.data?.error === 'string' && err.response.data.error.trim()) {
        errorMsg = err.response.data.error;
      }
      console.error('[Chat] Request failed', err.response?.data || err.message || err);
      setMessages(prev => [...prev, { role: 'assistant', content: errorMsg, isError: true }]);
    } finally {
      setLoading(false);
    }
  }, [loading, messages, storeContext, sessionState]);

  if (!open) return null;

  return (
    <div className={`absolute bottom-0 right-0 z-50 transition-all duration-350 ease-[cubic-bezier(0.16,1,0.3,1)] animate-slide-up ${
      expanded ? 'left-0 top-0' : 'w-full sm:w-[420px] h-[480px] sm:right-4 sm:bottom-4 sm:rounded-2xl overflow-hidden'
    }`}>
      <div className={`h-full bg-gwsa-surface/95 backdrop-blur-xl border border-gwsa-border shadow-panel flex flex-col ${
        expanded ? '' : 'sm:rounded-2xl'
      }`}>

        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-gwsa-border">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-gwsa-accent to-blue-400 flex items-center justify-center">
              <Sparkles className="w-3.5 h-3.5 text-white" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gwsa-text">GWSA AI Assistant</h3>
              <p className="text-[10px] text-gwsa-text-muted">
                {storeContext ? `Viewing: ${storeContext}` : 'Ask about any location'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => setExpanded(!expanded)}
              className="p-1.5 rounded-lg hover:bg-gwsa-surface-hover transition-colors hidden sm:block">
              {expanded ? <Minimize2 className="w-4 h-4 text-gwsa-text-muted" /> : <Maximize2 className="w-4 h-4 text-gwsa-text-muted" />}
            </button>
            <button onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-gwsa-surface-hover transition-colors">
              <X className="w-4 h-4 text-gwsa-text-muted" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {messages.map((msg, i) => (
            <ChatMessage key={i} message={msg} onFollowupClick={handleSend} />
          ))}
          {loading && (
            <div className="flex items-center gap-2 px-3 py-2">
              <div className="flex gap-1">
                <div className="w-1.5 h-1.5 bg-gwsa-accent rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-1.5 h-1.5 bg-gwsa-accent rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-1.5 h-1.5 bg-gwsa-accent rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
              <span className="text-xs text-gwsa-text-muted">Thinking...</span>
            </div>
          )}
        </div>

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={loading} />
      </div>
    </div>
  );
}
