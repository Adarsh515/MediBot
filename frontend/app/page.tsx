"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

const API = "http://localhost:8000";  // Change this to your backend API URL if different

const DEMO_ACCOUNTS = [
  { username: "dr.mehta",     password: "doctor",            role: "Doctor",            color: "bg-emerald-50 border-emerald-300 text-emerald-800" },
  { username: "nurse.priya",  password: "nurse",             role: "Nurse",             color: "bg-purple-50 border-purple-300 text-purple-800" },
  { username: "billing.ravi", password: "billing_executive", role: "Billing Executive", color: "bg-orange-50 border-orange-300 text-orange-800" },
  { username: "tech.anand",   password: "technician",        role: "Technician",        color: "bg-yellow-50 border-yellow-300 text-yellow-800" },
  { username: "admin.sys",    password: "admin",             role: "Admin",             color: "bg-red-50 border-red-300 text-red-800" },
];

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const router = useRouter();

  const handleLogin = async (u = username, p = password) => {
    if (!u || !p) { setError("Enter username and password."); return; }
    setLoading(true);
    setError("");
    try {
      const res  = await fetch(`${API}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p }),
      });
      if (!res.ok) { setError("Invalid credentials."); setLoading(false); return; }
      const data = await res.json();
      localStorage.setItem("token",       data.token);
      localStorage.setItem("role",        data.role);
      localStorage.setItem("username",    data.username);
      localStorage.setItem("collections", JSON.stringify(data.accessible_collections));
      router.push("/chat");
    } catch {
      setError("Cannot reach MediBot server.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🏥</div>
          <h1 className="text-2xl font-bold text-gray-900">MediBot</h1>
          <p className="text-sm text-gray-500 mt-1">MediAssist Health Network · Internal Assistant</p>
        </div>

        <div className="space-y-3 mb-6">
          <input
            className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleLogin()}
          />
          <input
            className="w-full border border-gray-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleLogin()}
          />
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <button
            onClick={() => handleLogin()}
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </div>

        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1 h-px bg-gray-100" />
          <span className="text-xs text-gray-400 font-medium uppercase tracking-wider">Demo Accounts</span>
          <div className="flex-1 h-px bg-gray-100" />
        </div>

        <div className="space-y-2">
          {DEMO_ACCOUNTS.map(a => (
            <button
              key={a.username}
              onClick={() => handleLogin(a.username, a.password)}
              disabled={loading}
              className={`w-full flex items-center justify-between px-4 py-2.5 rounded-lg border text-sm font-medium transition-colors ${a.color} disabled:opacity-50`}
            >
              <span className="font-mono text-xs">{a.username}</span>
              <span className="text-xs opacity-70">{a.role}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}