// src/app/settings/page.tsx
"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle, XCircle, ExternalLink } from "lucide-react";
import Link from "next/link";
import clsx from "clsx";
import { fetchHealth } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

const PROVIDERS = [
  {
    id: "groq",
    name: "Groq",
    tag: "Recommended",
    tagColor: "text-violet-400 bg-violet-500/10 border-violet-500/20",
    description: "Cloud API, fastest inference, generous free tier",
    model: "llama-3.3-70b-versatile",
    setup: [
      "Sign up at console.groq.com",
      "Create an API key",
      'Set LLM_PROVIDER=groq in .env',
      "Set GROQ_API_KEY=your_key",
    ],
    url: "https://console.groq.com",
    color: "border-violet-500/30 bg-violet-500/5",
  },
  {
    id: "gemini",
    name: "Google Gemini",
    tag: "1500 req/day free",
    tagColor: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    description: "Google AI Studio, 1500 free requests per day",
    model: "gemini-1.5-flash",
    setup: [
      "Visit aistudio.google.com",
      "Click Get API Key",
      'Set LLM_PROVIDER=gemini in .env',
      "Set GOOGLE_API_KEY=your_key",
    ],
    url: "https://aistudio.google.com",
    color: "border-blue-500/20 bg-blue-500/5",
  },
  {
    id: "ollama",
    name: "Ollama",
    tag: "100% Local",
    tagColor: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    description: "Run models locally, no internet required, unlimited",
    model: "llama3.2 / mistral / qwen2.5",
    setup: [
      "Install from ollama.com",
      "Run: ollama pull llama3.2",
      'Set LLM_PROVIDER=ollama in .env',
      "Start Ollama service",
    ],
    url: "https://ollama.com",
    color: "border-emerald-500/20 bg-emerald-500/5",
  },
];

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [apiStatus, setApiStatus] = useState<"loading" | "ok" | "error">("loading");
  const [token, setToken] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);

  const checkHealth = () => {
    setApiStatus("loading");
    fetchHealth()
      .then((h) => { setHealth(h); setApiStatus("ok"); })
      .catch(() => { setHealth(null); setApiStatus("error"); });
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      setToken(localStorage.getItem("api_token") || "");
    }
    checkHealth();
  }, []);

  const handleSaveToken = (e: React.FormEvent) => {
    e.preventDefault();
    if (typeof window !== "undefined") {
      if (token.trim()) {
        localStorage.setItem("api_token", token.trim());
      } else {
        localStorage.removeItem("api_token");
      }
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
      checkHealth();
    }
  };

  return (
    <div className="min-h-screen bg-grid">
      {/* Header */}
      <header className="border-b border-ink-800/60 bg-ink-950/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-screen-xl mx-auto px-5 py-3 flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-1.5 text-ink-500 hover:text-ink-200 text-xs font-mono transition-colors"
          >
            <ArrowLeft size={13} />
            Back
          </Link>
          <span className="text-ink-700">|</span>
          <h1 className="font-display font-semibold text-sm text-ink-200">
            Configuration
          </h1>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-5 py-8">
        <div className="max-w-3xl mx-auto space-y-8">

          {/* API Status */}
          <section>
            <h2 className="font-display font-semibold text-ink-200 mb-4">
              Backend Status
            </h2>
            <div className="bg-ink-900/60 border border-ink-800 rounded-2xl p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {apiStatus === "ok" ? (
                    <CheckCircle size={18} className="text-emerald-400" />
                  ) : apiStatus === "error" ? (
                    <XCircle size={18} className="text-rose-400" />
                  ) : (
                    <div className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                  )}
                  <div>
                    <p className={clsx("text-sm font-medium", {
                      "text-emerald-400": apiStatus === "ok",
                      "text-rose-400": apiStatus === "error",
                      "text-ink-400": apiStatus === "loading",
                    })}>
                      {apiStatus === "ok" ? "Connected" : apiStatus === "error" ? "Disconnected" : "Checking…"}
                    </p>
                    <p className="text-ink-600 text-xs font-mono mt-0.5">
                      {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
                    </p>
                  </div>
                </div>

                {health && (
                  <div className="text-right">
                    <p className="text-ink-200 text-sm font-mono font-medium">
                      {health.llm_provider.toUpperCase()} · {health.llm_model}
                    </p>
                    <p className="text-ink-600 text-xs font-mono mt-0.5">
                      {health.llm_type} · v{health.version}
                    </p>
                  </div>
                )}
              </div>

              {apiStatus === "error" && (
                <div className="mt-4 bg-ink-950/60 border border-ink-800 rounded-xl p-3">
                  <p className="text-ink-400 text-xs font-mono">
                    Start the backend with:
                  </p>
                  <pre className="text-emerald-400 text-xs font-mono mt-1.5 bg-black/30 rounded-lg p-2.5">
                    uvicorn api.main:app --reload --port 8000
                  </pre>
                </div>
              )}
            </div>
          </section>

          {/* Authentication Settings */}
          <section>
            <h2 className="font-display font-semibold text-ink-200 mb-4">
              Authentication Settings
            </h2>
            <div className="bg-ink-900/60 border border-ink-800 rounded-2xl p-5">
              <p className="text-ink-300 text-sm mb-4">
                Enter your configured <strong className="text-ink-100">API Key</strong> or <strong className="text-ink-100">JWT Token</strong> below to authorize the frontend application with the backend services.
              </p>
              <form onSubmit={handleSaveToken} className="space-y-4">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="api-token" className="text-ink-500 text-[10px] font-mono uppercase tracking-wider">
                    Bearer Token / API Key
                  </label>
                  <div className="flex gap-2">
                    <input
                      id="api-token"
                      type="password"
                      placeholder="Paste your token or API Key..."
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      className="bg-ink-950/80 border border-ink-800 rounded-xl px-3 py-2 text-ink-100 text-xs font-mono placeholder-ink-600 focus:outline-none focus:border-violet-500/50 flex-grow"
                    />
                    <button
                      type="submit"
                      className="bg-violet-600 hover:bg-violet-500 active:bg-violet-700 text-ink-100 rounded-xl px-4 py-2 text-xs font-mono font-semibold transition-colors flex-shrink-0"
                    >
                      Save Key
                    </button>
                  </div>
                </div>
                {saveSuccess && (
                  <p className="text-emerald-400 text-xs font-mono flex items-center gap-1.5 animate-fade-in">
                    <CheckCircle size={12} /> Key saved successfully! Re-checking status...
                  </p>
                )}
              </form>
            </div>
          </section>

          {/* Provider cards */}
          <section>
            <h2 className="font-display font-semibold text-ink-200 mb-4">
              LLM Providers
            </h2>
            <div className="space-y-4">
              {PROVIDERS.map((p) => {
                const isActive = health?.llm_provider === p.id;
                return (
                  <div
                    key={p.id}
                    className={clsx(
                      "border rounded-2xl p-5 transition-all",
                      isActive
                        ? p.color + " border-opacity-60"
                        : "border-ink-800 bg-ink-900/40"
                    )}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-display font-semibold text-ink-100 text-base">
                              {p.name}
                            </h3>
                            <span className={clsx("text-[10px] font-mono px-2 py-0.5 rounded-full border", p.tagColor)}>
                              {p.tag}
                            </span>
                            {isActive && (
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                                ● Active
                              </span>
                            )}
                          </div>
                          <p className="text-ink-500 text-xs mt-1">{p.description}</p>
                        </div>
                      </div>
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-ink-500 hover:text-violet-400 text-xs font-mono transition-colors flex-shrink-0"
                      >
                        Sign up
                        <ExternalLink size={11} />
                      </a>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Model */}
                      <div>
                        <p className="text-ink-600 text-[10px] font-mono uppercase tracking-wider mb-1.5">
                          Default Model
                        </p>
                        <code className="text-violet-300 text-xs font-mono bg-ink-950/60 border border-ink-800 rounded-lg px-2.5 py-1.5 block">
                          {p.model}
                        </code>
                      </div>

                      {/* Setup steps */}
                      <div>
                        <p className="text-ink-600 text-[10px] font-mono uppercase tracking-wider mb-1.5">
                          Setup
                        </p>
                        <ol className="space-y-1">
                          {p.setup.map((step, i) => (
                            <li key={i} className="flex items-start gap-2 text-xs font-mono text-ink-400">
                              <span className="text-ink-700 flex-shrink-0 tabular-nums w-3">
                                {i + 1}.
                              </span>
                              <code className={clsx({
                                "text-emerald-400": step.includes("Set ") || step.includes("Run:"),
                                "text-ink-400": !step.includes("Set ") && !step.includes("Run:"),
                              })}>
                                {step}
                              </code>
                            </li>
                          ))}
                        </ol>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Embeddings info */}
          <section>
            <h2 className="font-display font-semibold text-ink-200 mb-4">
              Embeddings (RAG)
            </h2>
            <div className="bg-ink-900/60 border border-ink-800 rounded-2xl p-5">
              <div className="flex items-center gap-3 mb-3">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                  Free · No API Key
                </span>
              </div>
              <p className="text-ink-300 text-sm mb-3">
                Uses <strong className="text-ink-100">HuggingFace sentence-transformers</strong> locally — no API key required.
                Model downloads automatically on first run (~90MB).
              </p>
              <code className="text-violet-300 text-xs font-mono bg-ink-950/60 border border-ink-800 rounded-lg px-3 py-2 block">
                sentence-transformers/all-MiniLM-L6-v2
              </code>
            </div>
          </section>

          {/* .env template */}
          <section>
            <h2 className="font-display font-semibold text-ink-200 mb-4">
              Environment Template
            </h2>
            <div className="bg-ink-900/60 border border-ink-800 rounded-2xl p-5">
              <p className="text-ink-500 text-xs font-mono mb-3">
                Copy to <code className="text-violet-300">.env</code> in your backend root
              </p>
              <pre className="text-xs font-mono text-ink-300 leading-relaxed bg-ink-950/80 border border-ink-800 rounded-xl p-4 overflow-x-auto">
{`# Pick ONE provider
LLM_PROVIDER=groq

# Groq (recommended)
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# OR Google Gemini
# LLM_PROVIDER=gemini
# GOOGLE_API_KEY=your_key_here

# OR Ollama (local)
# LLM_PROVIDER=ollama
# OLLAMA_MODEL=llama3.2

# Vector store (local by default)
VECTOR_STORE=faiss
FAISS_INDEX_PATH=./data/faiss_index

# Redis (optional, for session memory)
REDIS_URL=redis://localhost:6379

# LangSmith (optional, free tier)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=your_key_here`}
              </pre>
            </div>
          </section>

        </div>
      </main>
    </div>
  );
}
