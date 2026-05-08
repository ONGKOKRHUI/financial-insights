"use client";

/**
 * LiveSearchBox — debounced, keyboard-navigable Elasticsearch search dropdown.
 *
 * Behaviour
 * ---------
 * - Debounces input by 200 ms before firing a request.
 * - Cancels any in-flight request when the user types again (AbortController).
 * - Shows a spinner while loading, an inline error note on failure, and an
 *   empty-state message when no results are found for a non-trivial query.
 * - Supports full keyboard interaction:
 *     ↑ / ↓  — move active highlight through results
 *     Enter   — navigate to the active (or first) result
 *     Escape  — close the dropdown
 * - Clicking outside the component closes the dropdown.
 * - Navigates to `source_uri` when present, otherwise falls back to `/companies/{ticker}`
 *   for company-domain hits, or shows a non-navigable display for other content.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { LiveSearchResult } from "@/types";

const DEBOUNCE_MS = 200;
const MIN_QUERY_LEN = 2;

// ── Helpers ────────────────────────────────────────────────────────────────

function resolveHref(hit: LiveSearchResult): string | null {
  // file:// URIs are local filesystem paths from ingestion — not browser-navigable
  const uri = hit.source_uri && !hit.source_uri.startsWith("file://") ? hit.source_uri : null;
  if (uri) return uri;
  if (hit.domain === "company" && hit.ticker) {
    return `/companies/${hit.ticker}`;
  }
  if (hit.domain === "api" || hit.doc_type === "api_doc") {
    return "/api-docs";
  }
  return null;
}

function DomainBadge({ domain, ticker }: { domain: string; ticker: string | null }) {
  const label = ticker ?? domain;
  const colours: Record<string, string> = {
    platform: "bg-indigo-900/60 text-indigo-300",
    api: "bg-cyan-900/60 text-cyan-300",
    pipeline: "bg-purple-900/60 text-purple-300",
    company: "bg-emerald-900/60 text-emerald-300",
  };
  const cls = colours[domain] ?? "bg-slate-700 text-slate-300";
  return (
    <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${cls}`}>
      {label.toUpperCase()}
    </span>
  );
}

// ── Component ──────────────────────────────────────────────────────────────

export default function LiveSearchBox() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<LiveSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [open, setOpen] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // ── Close on outside click ───────────────────────────────────────────────
  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  // ── Debounced search ─────────────────────────────────────────────────────
  useEffect(() => {
    const trimmed = query.trim();

    if (trimmed.length < MIN_QUERY_LEN) {
      setResults([]);
      setOpen(false);
      setError(null);
      return;
    }

    const timer = setTimeout(async () => {
      // Cancel any previous in-flight request
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      setLoading(true);
      setError(null);
      setActiveIndex(-1);

      try {
        const res = await api.search.live(trimmed, abortRef.current.signal);
        setResults(res.hits);
        setOpen(true);
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") return;
        setError("Search unavailable");
        setResults([]);
        setOpen(true);
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [query]);

  // ── Navigation helper ────────────────────────────────────────────────────
  const navigateTo = useCallback(
    (hit: LiveSearchResult) => {
      const href = resolveHref(hit);
      if (!href) return;
      setOpen(false);
      setQuery("");
      if (href.startsWith("http")) {
        window.open(href, "_blank", "noopener noreferrer");
      } else {
        router.push(href);
      }
    },
    [router]
  );

  // ── Keyboard handler ─────────────────────────────────────────────────────
  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const target = results[activeIndex] ?? results[0];
      if (target) navigateTo(target);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const showDropdown = open && query.trim().length >= MIN_QUERY_LEN;

  return (
    <div ref={containerRef} className="relative hidden sm:block">
      {/* Input */}
      <div className="relative flex items-center">
        <svg
          className="pointer-events-none absolute left-3 h-4 w-4 text-slate-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-4.35-4.35m0 0A7.5 7.5 0 1 0 6.5 6.5a7.5 7.5 0 0 0 10.6 10.6z"
          />
        </svg>

        {loading && (
          <svg
            className="absolute right-3 h-4 w-4 animate-spin text-indigo-400"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v8H4z"
            />
          </svg>
        )}

        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (results.length > 0) setOpen(true);
          }}
          placeholder="Search docs…"
          role="combobox"
          aria-label="Search documentation"
          aria-autocomplete="list"
          aria-expanded={showDropdown}
          aria-haspopup="listbox"
          aria-controls="live-search-listbox"
          className="h-9 w-48 rounded-lg border border-slate-700 bg-slate-800 pl-9 pr-8 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 lg:w-64"
        />
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div
          id="live-search-listbox"
          role="listbox"
          aria-label="Search suggestions"
          className="absolute left-0 top-full z-50 mt-1.5 w-[420px] max-w-[calc(100vw-2rem)] rounded-xl border border-slate-700 bg-slate-900 shadow-2xl"
        >
          {error && (
            <p className="px-4 py-3 text-sm text-rose-400">{error}</p>
          )}

          {!error && results.length === 0 && (
            <p className="px-4 py-3 text-sm text-slate-500">
              No results for &ldquo;{query.trim()}&rdquo;
            </p>
          )}

          {!error && results.length > 0 && (
            <ul>
              {results.map((hit, idx) => {
                const href = resolveHref(hit);
                const isActive = idx === activeIndex;

                return (
                  <li key={`${hit.source_path}-${hit.rank}`} role="option" aria-selected={isActive}>
                    <button
                      type="button"
                      disabled={!href}
                      onMouseEnter={() => setActiveIndex(idx)}
                      onClick={() => navigateTo(hit)}
                      className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors ${
                        isActive
                          ? "bg-indigo-900/40"
                          : "hover:bg-slate-800"
                      } ${!href ? "cursor-default opacity-60" : "cursor-pointer"} ${
                        idx === 0 ? "rounded-t-xl" : ""
                      } ${idx === results.length - 1 ? "rounded-b-xl" : "border-b border-slate-800"}`}
                    >
                      {/* Rank indicator */}
                      <span className="mt-0.5 shrink-0 text-xs font-mono text-slate-600 w-4">
                        {hit.rank}
                      </span>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium text-white">
                            {hit.title}
                          </span>
                          <DomainBadge domain={hit.domain} ticker={hit.ticker} />
                        </div>
                        <p className="mt-0.5 line-clamp-2 text-xs text-slate-400">
                          {hit.snippet}
                        </p>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="border-t border-slate-800 px-4 py-2 text-[10px] text-slate-600">
            ↑↓ navigate · Enter open · Esc close
          </div>
        </div>
      )}
    </div>
  );
}
