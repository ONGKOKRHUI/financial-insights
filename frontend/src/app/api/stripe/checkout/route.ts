/**
 * BFF route: POST /api/stripe/checkout
 *
 * Creates a Stripe Checkout session for the monthly Pro subscription and
 * returns the hosted checkout URL.  The backend reads the user's session
 * cookie to associate the Stripe customer with the correct account.
 *
 * Environment variables required:
 * - ``STRIPE_SECRET_KEY``       — Stripe secret key
 * - ``NEXT_PUBLIC_APP_URL``     — Frontend base URL (for success/cancel redirects)
 * - ``STRIPE_PRO_PRICE_ID``     — Stripe price ID for the MYR 29/mo subscription
 *
 * Note: Stripe is initialised inside the handler (not at module level) so that
 * a missing ``STRIPE_SECRET_KEY`` returns a graceful 503 instead of crashing
 * the Next.js route module at import time.
 */

import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";

const BACKEND =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export async function POST(req: NextRequest) {
  const stripeKey = process.env.STRIPE_SECRET_KEY;
  const proPriceId = process.env.STRIPE_PRO_PRICE_ID ?? "";

  if (!stripeKey || !proPriceId) {
    return NextResponse.json(
      { error: "Stripe is not configured on this server." },
      { status: 503 }
    );
  }

  // Initialise Stripe inside the handler so a missing key returns 503
  // rather than crashing the module at load time.
  const stripe = new Stripe(stripeKey, {
    apiVersion: "2025-01-27.acacia",
  });

  // Identify the logged-in user via the session cookie.
  const cookieHeader = req.headers.get("cookie") ?? "";
  const meRes = await fetch(`${BACKEND}/users/me`, {
    headers: { Cookie: cookieHeader },
    cache: "no-store",
  });

  if (!meRes.ok) {
    return NextResponse.json({ error: "Not authenticated." }, { status: 401 });
  }

  const user = await meRes.json();

  const session = await stripe.checkout.sessions.create({
    mode: "subscription",
    payment_method_types: ["card"],
    customer_email: user.email,
    line_items: [{ price: proPriceId, quantity: 1 }],
    success_url: `${APP_URL}/account?upgraded=true`,
    cancel_url: `${APP_URL}/upgrade?cancelled=true`,
    metadata: { user_email: user.email },
  });

  return NextResponse.json({ checkout_url: session.url });
}
