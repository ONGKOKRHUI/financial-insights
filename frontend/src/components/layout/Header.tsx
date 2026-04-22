"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useSearchStore } from "@/stores/searchStore";

const NAV_LINKS = [
  { href: "/companies", label: "Companies" },
  { href: "/api-docs", label: "API Docs" },
];

export default function Header() {
  const router = useRouter();
  const { setQuery } = useSearchStore();
  const [inputValue, setInputValue] = useState("");

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = inputValue.trim().toUpperCase();
    if (!trimmed) return;
    setQuery(trimmed);
    router.push(`/companies/${trimmed}`);
    setInputValue("");
  }

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link
          href="/"
          className="flex items-center gap-2 text-xl font-bold text-slate-900 hover:text-blue-600 transition-colors"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white text-sm font-bold">
            FS
          </span>
          FinSight
        </Link>

        {/* Nav links */}
        <nav className="hidden items-center gap-6 md:flex">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Search ticker… e.g. MAYBANK"
            className="h-9 w-40 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 sm:w-56"
          />
          <button
            type="submit"
            className="h-9 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            Search
          </button>
        </form>
      </div>
    </header>
  );
}
