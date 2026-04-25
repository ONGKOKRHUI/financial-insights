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
 */

import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY ?? "", {
  apiVersion: "2026-04-22.dahlia",
});

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
const PRO_PRICE_ID = process.env.STRIPE_PRO_PRICE_ID ?? "";

export async function POST(req: NextRequest) {
  if (!PRO_PRICE_ID) {
    return NextResponse.json(
      { error: "Stripe is not configured on this server." },
      { status: 503 }
    );
  }

  // Identify the logged-in user via the BFF auth/me endpoint
  const cookieHeader = req.headers.get("cookie") ?? "";
  const meRes = await fetch(
    `${process.env.INTERNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/users/me`,
    { headers: { Cookie: cookieHeader }, cache: "no-store" }
  );
  if (!meRes.ok) {
    return NextResponse.json({ error: "Not authenticated." }, { status: 401 });
  }
  const user = await meRes.json();

  const session = await stripe.checkout.sessions.create({
    mode: "subscription",
    payment_method_types: ["card"],
    customer_email: user.email,
    line_items: [{ price: PRO_PRICE_ID, quantity: 1 }],
    success_url: `${APP_URL}/account?upgraded=true`,
    cancel_url: `${APP_URL}/upgrade?cancelled=true`,
    metadata: { user_email: user.email },
  });

  return NextResponse.json({ checkout_url: session.url });
}
