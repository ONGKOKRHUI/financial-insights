import type { Metadata } from "next"; // Type definition for Next.js metadata
import type { ReactNode } from "react";
import "./globals.css"; // Import global CSS for the entire app
import Header from "@/components/layout/Header"; // Header component for top navigation
import Footer from "@/components/layout/Footer"; // Footer component for bottom section
import { Providers } from "@/lib/providers"; // React context providers for global state (e.g., theme, auth, API clients)
import { Inter } from "next/font/google";
import JarvisButton from "@/components/ui/JarvisButton"; // 1. Import the new component

const inter = Inter({ subsets: ["latin"] });

/**
 * Metadata for SEO and social sharing
 */
export const metadata: Metadata = {
  title: {
    default: "FinSight — Malaysian Financial Data API", // Default title for pages
    template: "%s | FinSight", // Template for dynamic page titles, e.g., "Dashboard | FinSight"
  },
  description:
    "Financial data API and analytics platform for Malaysian Blue-Chip companies. Access structured income statements, KPIs, and trend analysis for KLSE-listed companies.", // SEO description
  keywords: ["Malaysian stocks", "KLSE", "financial data", "API", "Maybank", "CIMB", "TNB"], // Optional SEO keywords
  openGraph: {
    type: "website", // Type of OpenGraph object
    siteName: "FinSight", // Name used in social sharing
  },
};

/**
 * RootLayout component
 * Wraps all pages in the app with common layout, global providers, and metadata
 */
export default function RootLayout({
  children, // The page content to render inside this layout
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en"> {/* Root HTML element with language set to English */}
      <body className={`${inter.className} min-h-screen flex flex-col bg-slate-50`}>
        {/* 
          Providers wrap the app to give all children access to global contexts
          (e.g., theme, state, API clients)
        */}
        <Providers>
          <Header /> {/* Top navigation bar */}
          <main className="flex-1">{children}</main> {/* Page content grows to fill remaining space */}
          <Footer /> {/* Bottom section */}
          <JarvisButton /> {/* Global floating voice control */}
        </Providers>
      </body>
    </html>
  );
}