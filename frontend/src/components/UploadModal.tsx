// src/components/UploadModal.tsx
"use client";

import { useState, useRef, useCallback } from "react";
import { X, Upload, FileText, CheckCircle, AlertCircle } from "lucide-react";
import clsx from "clsx";
import { uploadDocument } from "@/lib/api";

interface Props {
  onClose: () => void;
}

type UploadState = "idle" | "uploading" | "success" | "error";

export function UploadModal({ onClose }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File) => {
    const allowed = [".txt", ".pdf", ".csv", ".md"];
    const ext = "." + f.name.split(".").pop()?.toLowerCase();
    if (!allowed.includes(ext)) {
      setMessage(`File type not supported. Use: ${allowed.join(", ")}`);
      setUploadState("error");
      return;
    }
    setFile(f);
    setUploadState("idle");
    setMessage("");
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const handleUpload = async () => {
    if (!file) return;
    setUploadState("uploading");
    try {
      const res = await uploadDocument(file);
      setMessage(res.message);
      setUploadState("success");
    } catch (e) {
      setMessage((e as Error).message);
      setUploadState("error");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-ink-950/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-md bg-ink-900 border border-ink-700 rounded-2xl p-6 shadow-2xl animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-display font-semibold text-ink-100 text-lg">
              Upload Document
            </h2>
            <p className="text-ink-500 text-xs mt-0.5">
              Add to the RAG knowledge base
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-ink-500 hover:text-ink-300 transition-colors p-1"
          >
            <X size={18} />
          </button>
        </div>

        {/* Drop zone */}
        <div
          className={clsx(
            "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200",
            dragOver
              ? "border-violet-500 bg-violet-500/10"
              : "border-ink-700 hover:border-ink-500 bg-ink-950/40"
          )}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".txt,.pdf,.csv,.md"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
          />

          {file ? (
            <div className="flex flex-col items-center gap-2">
              <FileText size={32} className="text-violet-400" />
              <p className="text-ink-200 text-sm font-medium">{file.name}</p>
              <p className="text-ink-500 text-xs">
                {(file.size / 1024).toFixed(1)} KB
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <Upload size={28} className="text-ink-500" />
              <div>
                <p className="text-ink-300 text-sm">
                  Drop a file or click to browse
                </p>
                <p className="text-ink-600 text-xs mt-1">
                  .txt · .pdf · .csv · .md
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Status message */}
        {message && (
          <div
            className={clsx(
              "mt-3 flex items-center gap-2 text-xs rounded-lg px-3 py-2",
              uploadState === "success"
                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
            )}
          >
            {uploadState === "success" ? (
              <CheckCircle size={14} />
            ) : (
              <AlertCircle size={14} />
            )}
            {message}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 mt-5">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl border border-ink-700 text-ink-400 text-sm hover:border-ink-500 hover:text-ink-200 transition-all"
          >
            {uploadState === "success" ? "Done" : "Cancel"}
          </button>
          {uploadState !== "success" && (
            <button
              onClick={handleUpload}
              disabled={!file || uploadState === "uploading"}
              className="flex-1 py-2.5 rounded-xl bg-violet-600 text-white text-sm font-medium hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              {uploadState === "uploading" ? "Uploading…" : "Upload"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
