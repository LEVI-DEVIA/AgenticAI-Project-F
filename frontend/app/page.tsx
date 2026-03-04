"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type JobRow = {
  index: number;
  status: "pending" | "success" | "failed";
  error: string | null;
};

type Job = {
  job_id: string;
  status:
    | "running"
    | "completed"
    | "completed_with_errors"
    | "failed";
  total: number;
  submitted: number;
  failed: number;
  rows: JobRow[];
  errors: { row_index: number | null; error: string | null }[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

function StatusPill({ status }: { status: JobRow["status"] }) {
  const cls =
    status === "success"
      ? "bg-emerald-100 text-emerald-800 border-emerald-200"
      : status === "failed"
        ? "bg-red-100 text-red-800 border-red-200"
        : "bg-zinc-100 text-zinc-700 border-zinc-200";
  const label =
    status === "success"
      ? "Validé"
      : status === "failed"
        ? "Échec"
        : "En attente";
  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const pollTimer = useRef<number | null>(null);

  const progressText = useMemo(() => {
    if (!job) return null;
    return `${job.submitted}/${job.total} validés · ${job.failed} échecs`;
  }, [job]);

  async function startJob() {
    if (!file) return;
    setError(null);
    setIsUploading(true);
    setJob(null);
    setJobId(null);

    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/jobs`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail ?? `Erreur HTTP ${res.status}`);
      }

      const data = (await res.json()) as { job_id: string };
      setJobId(data.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsUploading(false);
    }
  }

  async function fetchJob(id: string) {
    const res = await fetch(`${API_BASE}/jobs/${id}`, { cache: "no-store" });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data?.detail ?? `Erreur HTTP ${res.status}`);
    }
    const data = (await res.json()) as Job;
    setJob(data);
    if (
      data.status === "completed" ||
      data.status === "completed_with_errors" ||
      data.status === "failed"
    ) {
      if (pollTimer.current) {
        window.clearInterval(pollTimer.current);
        pollTimer.current = null;
      }
    }
  }

  useEffect(() => {
    if (!jobId) return;
    fetchJob(jobId).catch((e) => setError(e.message));
    if (pollTimer.current) window.clearInterval(pollTimer.current);
    pollTimer.current = window.setInterval(() => {
      fetchJob(jobId).catch((e) => setError(e.message));
    }, 1200);
    return () => {
      if (pollTimer.current) {
        window.clearInterval(pollTimer.current);
        pollTimer.current = null;
      }
    };
  }, [jobId]);

  return (
    <div className="min-h-screen bg-zinc-50 px-6 py-10 text-zinc-950 dark:bg-black dark:text-zinc-50">
      <div className="mx-auto w-full max-w-4xl">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight">
            Remplissage automatique de formulaire
          </h1>
          <p className="mt-2 text-zinc-600 dark:text-zinc-400">
            Upload un fichier CSV, puis suis la validation utilisateur par utilisateur.
          </p>
        </header>

        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex-1">
              <label className="text-sm font-medium">Fichier CSV</label>
              <div className="mt-2 flex items-center gap-3">
                <input
                  type="file"
                  accept=".csv,text/csv"
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

          {error ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-200">
              {error}
            </div>
          ) : null}

          {jobId ? (
            <div className="mt-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm text-zinc-600 dark:text-zinc-400">
                    Job
                  </div>
                  <div className="font-mono text-sm">{jobId}</div>
                </div>
                <div className="text-sm text-zinc-600 dark:text-zinc-400">
                  {progressText}
                </div>
              </div>

              <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-900">
                <div
                  className="h-full rounded-full bg-emerald-500 transition-all"
                  style={{
                    width: job ? `${Math.round(((job.submitted + job.failed) / job.total) * 100)}%` : "0%",
                  }}
                />
              </div>

              <div className="mt-6 grid gap-3">
                {(job?.rows ?? []).map((r) => (
                  <div
                    key={r.index}
                    className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`h-2.5 w-2.5 rounded-full ${
                          r.status === "success"
                            ? "bg-emerald-500"
                            : r.status === "failed"
                              ? "bg-red-500"
                              : "bg-zinc-400"
                        } ${r.status === "success" ? "animate-pulse" : ""}`}
                      />
                      <div className="text-sm font-medium">Utilisateur {r.index + 1}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      {r.error ? (
                        <div className="hidden max-w-xl truncate text-xs text-zinc-500 dark:text-zinc-400 sm:block">
                          {r.error}
                        </div>
                      ) : null}
                      <StatusPill status={r.status} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
