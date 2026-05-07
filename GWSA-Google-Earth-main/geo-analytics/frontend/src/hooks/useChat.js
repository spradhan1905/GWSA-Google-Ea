/**
 * GWSA GeoAnalytics — useChat hook (Azure OpenAI via backend)
 * Manages chat state, optional V2 session_state, and backend AI interactions.
 */
import { useState, useCallback } from 'react';
import { sendChatMessage } from '../services/api';

export default function useChat(storeContext) {
  const [messages, setMessages] = useState([]);
  const [sessionState, setSessionState] = useState(null);
  const [loading, setLoading] = useState(false);

  const send = useCallback(async (text) => {
    if (!text.trim() || loading) return;
    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    try {
      const history = messages.slice(-10).map(m => ({ role: m.role, content: m.content }));
      const res = await sendChatMessage(text, storeContext, history, sessionState);
      if (res.data.session_state) {
        setSessionState(res.data.session_state);
      }
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.reply || 'No response generated.',
        sqlUsed: res.data.sql_used,
        queryData: res.data.data,
        followups: res.data.followups,
      }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, an error occurred.' }]);
    } finally {
      setLoading(false);
    }
  }, [loading, messages, storeContext, sessionState]);

  const clear = useCallback(() => {
    setMessages([]);
    setSessionState(null);
  }, []);

  return { messages, loading, send, clear, sessionState };
}
