"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Run = {
  run_id: string;
  status: "running" | "awaiting_user_submit" | "completed" | "failed";
  error: string | null;
  current_row: number | null;
  user_submitted: boolean;
  live_view_url: string | null;
  live_view_debug_url: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [ocrFile, setOcrFile] = useState<File | null>(null);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [isOcrUploading, setIsOcrUploading] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [showLiveView, setShowLiveView] = useState(true);
  const esRef = useRef<EventSource | null>(null);

  const progressText = useMemo(() => {
    if (!run) return null;
    if (run.status === "running") return "Agent en cours...";
    if (run.status === "awaiting_user_submit") {
      const n = (run.current_row ?? 0) + 1;
      return `Prêt pour la ligne ${n} : clique sur Envoyer dans la Live View.`;
    }
    if (run.status === "completed") return "Terminé.";
    if (run.status === "failed") return "Erreur.";
    return null;
  }, [run]);

  async function runOcr() {
    if (!ocrFile) return;
    setOcrError(null);
    setIsOcrUploading(true);
    try {
      const form = new FormData();
      form.append("file", ocrFile);
      const res = await fetch(`${API_BASE}/run/image`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail ?? `Erreur HTTP ${res.status}`);
      }
      const data = (await res.json()) as {
        run_id: string;
        live_view_url: string;
      };
      setRunId(data.run_id);
      setRun({
        run_id: data.run_id,
        status: "running",
        error: null,
        current_row: null,
        user_submitted: false,
        live_view_url: data.live_view_url,
        live_view_debug_url: null,
      });
      setShowLiveView(true);
    } catch (e) {
      setOcrError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsOcrUploading(false);
    }
  }

  async function startJob() {
    if (!file) return;
    setError(null);
    setIsUploading(true);
    setRun(null);
    setRunId(null);
    setShowLiveView(true);

    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/run`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail ?? `Erreur HTTP ${res.status}`);
      }

      const data = (await res.json()) as {
        run_id: string;
        live_view_url: string;
      };
      setRunId(data.run_id);
      setRun({
        run_id: data.run_id,
        status: "running",
        error: null,
        current_row: null,
        user_submitted: false,
        live_view_url: data.live_view_url,
        live_view_debug_url: null,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsUploading(false);
    }
  }

  useEffect(() => {
    if (!runId) return;

    esRef.current?.close();
    const es = new EventSource(`${API_BASE}/run/${runId}/events`);
    esRef.current = es;

    es.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as
          | { type: "awaiting_user_submit"; row_index: number }
          | { type: "running"; row_index: number }
          | { type: "completed" }
          | { type: "failed"; error: string };

        if (msg.type === "awaiting_user_submit") {
          setRun((prev) =>
            prev
              ? {
                  ...prev,
                  status: "awaiting_user_submit",
                  current_row: msg.row_index,
                }
              : null,
          );
          setShowLiveView(true);
        } else if (msg.type === "running") {
          setRun((prev) =>
            prev
              ? { ...prev, status: "running", current_row: msg.row_index }
              : null,
          );
          setShowLiveView(true);
        } else if (msg.type === "completed") {
          setRun((prev) => (prev ? { ...prev, status: "completed" } : null));
          setShowLiveView(false);
          es.close();
        } else if (msg.type === "failed") {
          setRun((prev) =>
            prev ? { ...prev, status: "failed", error: msg.error } : null,
          );
          setShowLiveView(false);
          es.close();
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    };

    es.onerror = () => {
      setError("Connexion Live View (SSE) interrompue");
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [runId]);

  async function markDone() {
    if (!runId) return;
    setError(null);
    const res = await fetch(`${API_BASE}/run/${runId}/submit`, {
      method: "POST",
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setError(data?.detail ?? `Erreur HTTP ${res.status}`);
      return;
    }
    setShowLiveView(false);
  }

  return (
    <div className="min-h-screen bg-zinc-50 px-6 py-10 text-zinc-950 dark:bg-black dark:text-zinc-50">
      <div className="mx-auto w-full max-w-4xl">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight">
            Remplissage automatique de formulaire
          </h1>
          <p className="mt-2 text-zinc-600 dark:text-zinc-400">
            Upload un CSV/Excel ou une image. Tu verras l'agent remplir le
            formulaire en live. À la fin, c'est toi qui cliques sur Envoyer.
          </p>
        </header>

        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <div className="flex flex-col gap-4">
                <div className="flex-1">
                  <label className="text-sm font-medium">
                    Fichier CSV / Excel (.xlsx)
                  </label>
                  <div className="mt-2 flex items-center gap-3">
                    <input
                      type="file"
                      accept=".csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                      className="block w-full text-sm file:mr-4 file:rounded-full file:border-0 file:bg-zinc-900 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-zinc-700 dark:file:bg-zinc-100 dark:file:text-black"
                    />
                  </div>
                </div>

                <button
                  onClick={startJob}
                  disabled={!file || isUploading}
                  className="inline-flex h-11 items-center justify-center rounded-full bg-zinc-900 px-5 text-sm font-medium text-white shadow-sm transition disabled:cursor-not-allowed disabled:opacity-50 hover:bg-zinc-700 dark:bg-zinc-100 dark:text-black dark:hover:bg-white"
                >
                  {isUploading ? "Envoi..." : "Lancer"}
                </button>
              </div>
            </div>

            <div>
              <div className="flex flex-col gap-4">
                <div className="flex-1">
                  <label className="text-sm font-medium">Image</label>
                  <div className="mt-2 flex items-center gap-3">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => setOcrFile(e.target.files?.[0] ?? null)}
                      className="block w-full text-sm file:mr-4 file:rounded-full file:border-0 file:bg-zinc-900 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-zinc-700 dark:file:bg-zinc-100 dark:file:text-black"
                    />
                  </div>
                </div>

                <button
                  onClick={runOcr}
                  disabled={!ocrFile || isOcrUploading}
                  className="inline-flex h-11 items-center justify-center rounded-full bg-indigo-600 px-5 text-sm font-medium text-white shadow-sm transition disabled:cursor-not-allowed disabled:opacity-50 hover:bg-indigo-500"
                >
                  {isOcrUploading ? "Analyse..." : "Extraire"}
                </button>

                {ocrError ? (
                  <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-200">
                    {ocrError}
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          {error ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-200">
              {error}
            </div>
          ) : null}

          {runId ? (
            <div className="mt-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm text-zinc-600 dark:text-zinc-400">
                    Run
                  </div>
                  <div className="font-mono text-sm">{runId}</div>
                </div>
                <div className="text-sm text-zinc-600 dark:text-zinc-400">
                  {progressText}
                </div>
              </div>

              {run?.live_view_url && showLiveView ? (
                <div className="mt-6">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <a
                      href={run.live_view_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium text-zinc-900 underline underline-offset-4 hover:text-zinc-700 dark:text-zinc-100 dark:hover:text-white"
                    >
                      Ouvrir la Live View en plein écran
                    </a>
                    <button
                      onClick={markDone}
                      disabled={
                        run.status === "failed" || run.status === "completed"
                      }
                      className="inline-flex h-10 items-center justify-center rounded-full bg-emerald-600 px-5 text-sm font-medium text-white shadow-sm transition disabled:cursor-not-allowed disabled:opacity-50 hover:bg-emerald-500"
                    >
                      J'ai soumis
                    </button>
                  </div>

                  <div className="mt-4 overflow-hidden rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
                    <iframe
                      src={run.live_view_url}
                      className="h-[70vh] w-full"
                      sandbox="allow-same-origin allow-scripts"
                      allow="clipboard-read; clipboard-write"
                    />
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
