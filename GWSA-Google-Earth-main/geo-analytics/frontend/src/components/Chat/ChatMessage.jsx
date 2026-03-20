/**
 * GWSA GeoAnalytics — ChatMessage
 * Individual message bubble with markdown-like rendering.
 */
import React, { useState } from 'react';
import { Bot, User, Code, ChevronDown, ChevronRight } from 'lucide-react';
import { sanitizeHtml } from '../../utils/sanitize';

function renderMarkdown(text) {
  // Simple markdown: **bold**, bullet points, newlines
  let html = text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/^• /gm, '• ')
    .replace(/\n/g, '<br/>');
  return sanitizeHtml(html);
}

export default function ChatMessage({ message }) {
  const isAI = message.role === 'assistant';
  const [showSQL, setShowSQL] = useState(false);

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
          ? 'bg-gwsa-bg-alt border border-gwsa-border text-gwsa-text'
          : 'bg-gwsa-accent text-white'
      }`}>
        {isAI ? (
          <div className="chat-ai-content text-sm leading-relaxed"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }} />
        ) : (
          <p className="text-sm leading-relaxed">{message.content}</p>
        )}

        {/* SQL Query Toggle */}
        {message.sqlUsed && (
          <div className="mt-2 pt-2 border-t border-gwsa-border">
            <button onClick={() => setShowSQL(!showSQL)}
              className="flex items-center gap-1 text-[10px] text-gwsa-text-muted hover:text-gwsa-text-secondary transition-colors">
              <Code className="w-3 h-3" />
              SQL Query
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
