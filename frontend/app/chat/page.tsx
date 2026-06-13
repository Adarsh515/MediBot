"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

const API = "http://localhost:8000";

interface Source {
  source_document: string;
  section_title: string;
  collection: string;
}

interface Message {
  id: number;
  role: "user" | "bot";
  text: string;
  sources?: Source[];
  retrieval_type?: string;
  isBlocked?: boolean;
}

const ROLE_STYLES: Record<string, { bg: string; text: string; icon: string; label: string }> = {
  doctor:            { bg: "bg-emerald-100", text: "text-emerald-800", icon: "🩺", label: "Doctor" },
  nurse:             { bg: "bg-purple-100",  text: "text-purple-800",  icon: "💉", label: "Nurse" },
  billing_executive: { bg: "bg-orange-100",  text: "text-orange-800",  icon: "🧾", label: "Billing Executive" },
  technician:        { bg: "bg-yellow-100",  text: "text-yellow-800",  icon: "🔧", label: "Technician" },
  admin:             { bg: "bg-red-100",     text: "text-red-800",     icon: "🛡️", label: "Admin" },
};

const COLLECTION_ICONS: Record<string, string> = {
  general: "📋", clinical: "🧬", nursing: "💊", billing: "💰", equipment: "⚙️",
};

export default function ChatPage() {
  const [messages,    setMessages]    = useState<Message[]>([]);
  const [input,       setInput]       = useState("");
  const [loading,     setLoading]     = useState(false);
  const [role,        setRole]        = useState("");
  const [username,    setUsername]    = useState("");
  const [collections, setCollections] = useState<string[]>([]);
  const [sqlAccess,   setSqlAccess]   = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const msgId     = useRef(0);
  const router    = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("token");
    const r     = localStorage.getItem("role") || "";
    const u     = localStorage.getItem("username") || "";
    const c     = localStorage.getItem("collections");
    if (!token) { router.push("/"); return; }
    setRole(r);
    setUsername(u);
    if (c) setCollections(JSON.parse(c));

    fetch(`${API}/collections/${r}`)
      .then(res => res.json())
      .then(d => { setCollections(d.collections); setSqlAccess(d.sql_rag_access); });

    const style = ROLE_STYLES[r] || {};
    setMessages([{
      id: msgId.current++, role: "bot",
      text: `Hello! I'm MediBot ${style.icon || ""}. You're logged in as ${u} (${style.label || r}). Ask me anything from your accessible collections.`,
    }]);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text?: string) => {
    const question = (text || input).trim();
    if (!question || loading) return;
    setInput("");
    setMessages(prev => [...prev, { id: msgId.current++, role: "user", text: question }]);
    setLoading(true);

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          role,
          token: localStorage.getItem("token"),
        }),
      });

      if (res.status === 401) { localStorage.clear(); router.push("/"); return; }

      if (!res.ok) {
        const errText = await res.text();
        setMessages(prev => [...prev, {
          id: msgId.current++, role: "bot",
          text: `⚠️ Server error ${res.status}: ${errText}`,
        }]);
        setLoading(false);
        return;
      }

      const data = await res.json();

      setMessages(prev => [...prev, {
        id: msgId.current++,
        role: "bot",
        text: data.answer,
        sources: data.sources,
        retrieval_type: data.retrieval_type,
        isBlocked: data.retrieval_type === "rbac_blocked",
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: msgId.current++, role: "bot",
        text: `⚠️ Error: ${String(err)}`,
      }]);
    }finally {
      setLoading(false);
    }
  };

  const style = ROLE_STYLES[role] || {};

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-100 flex flex-col">
        <div className="p-5 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🏥</span>
            <div>
              <h1 className="font-bold text-gray-900">MediBot</h1>
              <p className="text-xs text-gray-400">MediAssist Health Network</p>
            </div>
          </div>
        </div>

        <div className="p-4 border-b border-gray-100">
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${style.bg} ${style.text}`}>
            <span>{style.icon}</span>
            <div>
              <div className="font-semibold text-sm">{username}</div>
              <div className="text-xs opacity-75">{style.label}</div>
            </div>
          </div>
        </div>

        <div className="p-4 border-b border-gray-100">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Accessible Collections
          </p>
          <div className="space-y-1">
            {collections.map(c => (
              <div key={c} className="flex items-center gap-2 text-xs text-gray-600 py-1">
                <span>{COLLECTION_ICONS[c] || "📁"}</span>
                <span className="capitalize font-medium">{c}</span>
              </div>
            ))}
          </div>
          {sqlAccess && (
            <div className="mt-3 text-xs bg-amber-50 text-amber-700 rounded-lg px-3 py-2 border border-amber-200">
              🗄️ SQL Analytics enabled
            </div>
          )}
        </div>

        <div className="mt-auto p-4 border-t border-gray-100">
          <button
            onClick={() => { localStorage.clear(); router.push("/"); }}
            className="w-full text-xs text-gray-400 hover:text-red-500 py-2 transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Chat */}
      <main className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {messages.map(m => (
            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              {m.role === "bot" && (
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm mr-3 mt-0.5 flex-shrink-0">
                  🤖
                </div>
              )}
              <div className={`max-w-2xl rounded-2xl px-5 py-4 text-sm shadow-sm
                ${m.role === "user"
                  ? "bg-blue-600 text-white rounded-br-sm"
                  : m.isBlocked
                    ? "bg-red-50 border border-red-200 text-red-900 rounded-bl-sm"
                    : "bg-white border border-gray-100 text-gray-800 rounded-bl-sm"}`}>

                {m.isBlocked && (
                  <div className="flex items-center gap-2 mb-2 pb-2 border-b border-red-200">
                    <span>🔒</span>
                    <span className="font-semibold text-xs uppercase tracking-wide text-red-700">Access Restricted</span>
                  </div>
                )}

                <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>

                {m.retrieval_type && m.retrieval_type !== "rbac_blocked" && (
                  <span className={`mt-2 inline-block text-xs px-2 py-0.5 rounded-full font-mono
                    ${m.retrieval_type === "sql_rag"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-green-100 text-green-700"}`}>
                    {m.retrieval_type === "sql_rag" ? "🗄️ sql_rag" : "🔍 hybrid_rag"}
                  </span>
                )}

                {m.sources && m.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-100 space-y-1.5">
                    <p className="text-xs font-semibold text-gray-400">Sources</p>
                    {m.sources.map((s, j) => (
                      <div key={j} className="text-xs bg-gray-50 rounded-lg px-3 py-2">
                        <span className="font-semibold text-gray-700">{s.source_document}</span>
                        {s.section_title && (
                          <span className="text-gray-500"> · {s.section_title}</span>
                        )}
                        <span className={`ml-2 px-1.5 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text}`}>
                          {s.collection}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm mr-3 flex-shrink-0">🤖</div>
              <div className="bg-white border border-gray-100 rounded-2xl rounded-bl-sm px-5 py-4 shadow-sm">
                <div className="flex gap-1 items-center">
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{animationDelay:"0ms"}} />
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{animationDelay:"150ms"}} />
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{animationDelay:"300ms"}} />
                  <span className="text-xs text-gray-400 ml-2">MediBot is thinking…</span>
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-gray-100 bg-white px-6 py-4">
          <div className="flex gap-3">
            <input
              className="flex-1 bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              placeholder={`Ask MediBot… (${style.label || role} access)`}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && sendMessage()}
              disabled={loading}
            />
            <button
              onClick={() => sendMessage()}
              disabled={loading || !input.trim()}
              className="bg-blue-600 text-white px-5 py-3 rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}