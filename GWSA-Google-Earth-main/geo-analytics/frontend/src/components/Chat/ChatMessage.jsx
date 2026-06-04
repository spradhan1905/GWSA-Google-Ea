/**
 * GWSA GeoAnalytics — ChatMessage
 * Individual message bubble with markdown-like rendering.
 */
import React, { useState } from 'react';
import { Bot, User, Code, ChevronDown, ChevronRight } from 'lucide-react';
import { sanitizeHtml } from '../../utils/sanitize';
import ChatCompareChart from './ChatCompareChart';

function renderMarkdown(text) {
  // Simple markdown: **bold**, bullet points, newlines
  let html = text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^• /gm, '• ')
    .replace(/\n/g, '<br/>');
  return sanitizeHtml(html);
}

export default function ChatMessage({ message, onFollowupClick }) {
  const isAI = message.role === 'assistant';
  const [showSQL, setShowSQL] = useState(false);
  const followups = Array.isArray(message.followups) ? message.followups : [];

  return (
    <div className={`flex gap-2.5 ${isAI ? '' : 'flex-row-reverse'}`}>
      {/* Avatar */}
      <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
        isAI ? 'bg-gradient-to-br from-gwsa-accent to-blue-400' : 'bg-gwsa-surface-hover border border-gwsa-border'
      }`}>
        {isAI ? <Bot className="w-3.5 h-3.5 text-white" /> : <User className="w-3.5 h-3.5 text-gwsa-text-muted" />}
      </div>

      {/* Bubble */}
      <div className={`max-w-[85%] rounded-xl px-3.5 py-2.5 ${
        isAI
          ? message.isError
            ? 'bg-amber-50/90 dark:bg-amber-950/30 border border-amber-200/80 dark:border-amber-800/60 text-gwsa-text'
            : 'bg-gwsa-bg-alt border border-gwsa-border text-gwsa-text'
          : 'bg-gwsa-accent text-white'
      }`}>
        {isAI ? (
          <div className="chat-ai-content text-sm leading-relaxed"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }} />
        ) : (
          <p className="text-sm leading-relaxed">{message.content}</p>
        )}

        {isAI && message.chart && (
          <ChatCompareChart chart={message.chart} />
        )}

        {isAI && followups.length > 0 && onFollowupClick && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {followups.slice(0, 5).map((q, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => onFollowupClick(q)}
                className="text-[10px] px-2 py-1 rounded-full border border-gwsa-border bg-gwsa-bg hover:bg-gwsa-surface-hover text-gwsa-text-secondary text-left max-w-full"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Data action toggle */}
        {message.sqlUsed && (
          <div className="mt-2 pt-2 border-t border-gwsa-border">
            <button onClick={() => setShowSQL(!showSQL)}
              className="flex items-center gap-1 text-[10px] text-gwsa-text-muted hover:text-gwsa-text-secondary transition-colors">
              <Code className="w-3 h-3" />
              Data Action
              {showSQL ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            </button>
            {showSQL && (
              <pre className="mt-1 text-[10px] text-gwsa-text-muted bg-gwsa-bg rounded-md p-2 overflow-x-auto whitespace-pre-wrap break-words">
                {message.sqlUsed}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
