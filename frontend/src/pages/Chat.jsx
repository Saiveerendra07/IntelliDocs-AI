import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Send,
  MessageSquare,
  FileText,
  Sparkles,
  BookOpen,
  HelpCircle,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Plus,
  History,
} from 'lucide-react';
import { documentsApi } from '../api/documents';
import { chatApi } from '../api/chat';
import { Badge } from '../components/common/Badge';

export const Chat = () => {
  const [searchParams] = useSearchParams();
  const initialDocId = searchParams.get('documentId');

  const [documents, setDocuments] = useState([]);
  const [selectedDocIds, setSelectedDocIds] = useState(initialDocId ? [initialDocId] : []);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null); // null = fresh conversation
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState('');
  const [explanationMode, setExplanationMode] = useState('technical'); // beginner, technical, exam, realworld
  const [loading, setLoading] = useState(false);
  const [retrievedPassages, setRetrievedPassages] = useState([]);
  const [showPassages, setShowPassages] = useState(true);

  const messagesEndRef = useRef(null);

  useEffect(() => {
    const init = async () => {
      try {
        const docsRes = await documentsApi.list();
        const docs = docsRes.items || [];
        setDocuments(docs);
        if (docs.length > 0 && selectedDocIds.length === 0) {
          setSelectedDocIds([docs[0].id]);
        }

        const convs = await chatApi.listConversations();
        setConversations(convs || []);
        // Start FRESH by default: do not automatically load old conversation
        setActiveConvId(null);
        setMessages([]);
      } catch (e) {
        console.error('Initialization error:', e);
      }
    };
    init();
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleDocToggle = (docId) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleStartNewChat = () => {
    setActiveConvId(null);
    setMessages([]);
    setRetrievedPassages([]);
    setInputQuery('');
  };

  const handleSelectConversation = async (convId) => {
    try {
      setLoading(true);
      setActiveConvId(convId);
      const msgs = await chatApi.getMessages(convId);
      setMessages(msgs || []);
      setRetrievedPassages([]);
    } catch (e) {
      console.error('Failed to load conversation:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!inputQuery.trim() || loading || selectedDocIds.length === 0) return;

    const query = inputQuery.trim();
    setInputQuery('');

    // Append user message optimistically
    const userMsg = {
      role: 'user',
      content: query,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      let convId = activeConvId;
      if (!convId) {
        const newConv = await chatApi.createConversation({
          title: query.slice(0, 35) + (query.length > 35 ? '...' : ''),
          document_ids: selectedDocIds,
          explanation_mode: explanationMode,
        });
        convId = newConv.id;
        setActiveConvId(convId);
        setConversations((prev) => [newConv, ...prev]);
      }

      const response = await chatApi.askQuestion(convId, {
        query,
        document_ids: selectedDocIds,
        explanation_mode: explanationMode,
      });

      const assistantMsg = {
        role: 'assistant',
        content: response.answer,
        sources: response.sources || [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setRetrievedPassages(response.sources || []);
    } catch (err) {
      console.error('Q&A generation failed:', err);
      const errorMsg = {
        role: 'assistant',
        content: 'Error answering query: ' + (err.response?.data?.error?.message || err.message),
        sources: [],
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-6 overflow-hidden">
      {/* Left Pane: New Chat, Past Conversations, Documents & Retrieved Passages */}
      <div className="hidden md:flex w-80 flex-col gap-4 rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4 shadow-sm overflow-hidden">
        {/* New Chat Button */}
        <button
          onClick={handleStartNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-primary-700 transition-all"
        >
          <Plus className="h-4 w-4" />
          <span>New Chat</span>
        </button>

        {/* Past Conversations List */}
        <div className="border-b border-slate-100 dark:border-surface-darkBorder pb-3">
          <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 dark:text-white mb-2">
            <History className="h-3.5 w-3.5 text-primary-600" />
            <span>Past Conversations</span>
          </div>
          <div className="space-y-1 max-h-32 overflow-y-auto pr-1">
            {conversations.length === 0 ? (
              <p className="text-[11px] text-slate-400 italic">No previous chats yet.</p>
            ) : (
              conversations.map((c) => {
                const isActive = c.id === activeConvId;
                return (
                  <button
                    key={c.id}
                    onClick={() => handleSelectConversation(c.id)}
                    className={`w-full text-left truncate rounded-lg px-2.5 py-1.5 text-xs transition-colors ${
                      isActive
                        ? 'bg-primary-50 dark:bg-primary-950/50 text-primary-900 dark:text-primary-200 font-bold border border-primary-200 dark:border-primary-800'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
                    }`}
                  >
                    {c.title || 'Untitled Conversation'}
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Active Documents Selector */}
        <div>
          <h2 className="text-xs font-bold text-slate-900 dark:text-white mb-1">
            Active Documents
          </h2>
          <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
            {documents.map((doc) => {
              const isChecked = selectedDocIds.includes(doc.id);
              return (
                <label
                  key={doc.id}
                  className={`flex items-center gap-2.5 rounded-lg p-2 text-xs cursor-pointer transition-colors ${
                    isChecked
                      ? 'bg-primary-50 dark:bg-primary-950/40 text-primary-900 dark:text-primary-200 font-medium'
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => handleDocToggle(doc.id)}
                    className="h-3.5 w-3.5 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                  />
                  <FileText className="h-4 w-4 shrink-0 text-slate-400" />
                  <span className="truncate">{doc.original_filename}</span>
                </label>
              );
            })}
          </div>
        </div>

        {/* Expandable Retrieved Passages Panel */}
        <div className="flex-1 flex flex-col border-t border-slate-100 dark:border-surface-darkBorder pt-3 overflow-hidden">
          <div
            onClick={() => setShowPassages(!showPassages)}
            className="flex items-center justify-between cursor-pointer py-1 text-xs font-bold text-slate-900 dark:text-white"
          >
            <span className="flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-primary-600" />
              Retrieved Passages ({retrievedPassages.length})
            </span>
            {showPassages ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </div>

          {showPassages && (
            <div className="mt-2 flex-1 overflow-y-auto space-y-2.5 pr-1">
              {retrievedPassages.length === 0 ? (
                <p className="text-[11px] text-slate-400 italic">
                  Ask a question to view semantic chunk citations and confidence scores.
                </p>
              ) : (
                retrievedPassages.map((src, i) => (
                  <div
                    key={i}
                    className="rounded-lg bg-slate-50 dark:bg-slate-900/50 p-2.5 text-[11px] border border-slate-200/50 dark:border-surface-darkBorder"
                  >
                    <div className="flex items-center justify-between text-primary-600 dark:text-primary-400 font-semibold mb-1">
                      <span>Page {src.page_start || 1}</span>
                      <span className="text-[10px] text-slate-400">
                        Score: {(src.score || 0.85).toFixed(2)}
                      </span>
                    </div>
                    <p className="text-slate-700 dark:text-slate-300 line-clamp-4 leading-relaxed font-mono">
                      {src.snippet || src.text}
                    </p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right Pane: Split-Screen Chat Interface */}
      <div className="flex flex-1 flex-col rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard shadow-sm overflow-hidden">
        {/* Explanation Mode Pill Selector Header */}
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-surface-darkBorder px-5 py-3">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-primary-600" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Grounded Q&A (RAG)
            </span>
            {activeConvId && (
              <span className="text-[11px] text-slate-400 ml-2 hidden sm:inline">
                • Active Session
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 text-xs">
            {[
              { id: 'beginner', label: 'Beginner' },
              { id: 'technical', label: 'Technical' },
              { id: 'exam', label: 'Exam-Oriented' },
              { id: 'realworld', label: 'Real-World Example' },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setExplanationMode(m.id)}
                className={`rounded-lg px-2.5 py-1 font-semibold transition-all ${
                  explanationMode === m.id
                    ? 'bg-primary-600 text-white shadow-xs'
                    : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center p-8">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-50 text-primary-600 dark:bg-primary-950/60 dark:text-primary-400 mb-3">
                <HelpCircle className="h-6 w-6" />
              </div>
              <h3 className="text-base font-bold text-slate-800 dark:text-white">
                Fresh Q&A Session Ready
              </h3>
              <p className="mt-1 text-xs text-slate-400 max-w-sm">
                Ask any technical question or request an overview. Every answer is structured (Direct Answer → Explanation → Document Example → Sources).
              </p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex flex-col ${
                  msg.role === 'user' ? 'items-end' : 'items-start'
                }`}
              >
                <div
                  className={`max-w-2xl rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-xs ${
                    msg.role === 'user'
                      ? 'bg-primary-600 text-white rounded-br-none'
                      : 'bg-slate-100 dark:bg-surface-darkBorder/60 text-slate-800 dark:text-slate-100 rounded-bl-none'
                  }`}
                >
                  <div className="whitespace-pre-wrap">{msg.content}</div>

                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-slate-200/50 dark:border-white/10 text-xs flex flex-wrap items-center gap-2 text-slate-500 dark:text-slate-300">
                      <span className="font-semibold text-primary-600 dark:text-primary-400">
                        Sources:
                      </span>
                      {msg.sources.map((s, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1 rounded bg-white dark:bg-surface-darkCard px-2 py-0.5 font-mono text-[10px] border border-slate-200 dark:border-surface-darkBorder"
                        >
                          {s.citation || `${s.document_title || 'Doc'} (Page ${s.page_start || 1})`}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {loading && (
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
              <span>Retrieving passages & generating structured grounded response...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <form onSubmit={handleSend} className="p-4 border-t border-slate-100 dark:border-surface-darkBorder bg-slate-50/50 dark:bg-surface-darkCard/50">
          <div className="relative flex items-center">
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Ask a question about the document... (e.g. 'what is a view?', 'explain the pdf')"
              className="w-full rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard pl-4 pr-12 py-3 text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:border-primary-600 focus:outline-none"
            />
            <button
              type="submit"
              disabled={loading || !inputQuery.trim() || selectedDocIds.length === 0}
              className="absolute right-2 rounded-lg bg-primary-600 p-2 text-white hover:bg-primary-700 disabled:opacity-40 transition-colors"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
