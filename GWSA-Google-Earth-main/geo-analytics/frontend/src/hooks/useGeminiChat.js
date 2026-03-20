/**
 * GWSA GeoAnalytics — useGeminiChat hook
 * Manages chat state and Gemini API interactions.
 */
import { useState, useCallback } from 'react';
import { sendChatMessage } from '../services/api';

export default function useGeminiChat(storeContext) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const send = useCallback(async (text) => {
    if (!text.trim() || loading) return;
    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    try {
      const history = messages.slice(-10).map(m => ({ role: m.role, content: m.content }));
      const res = await sendChatMessage(text, storeContext, history);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: res.data.reply || 'No response generated.',
        sqlUsed: res.data.sql_used,
        queryData: res.data.data,
      }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, an error occurred.' }]);
    } finally {
      setLoading(false);
    }
  }, [loading, messages, storeContext]);

  const clear = useCallback(() => setMessages([]), []);

  return { messages, loading, send, clear };
}
