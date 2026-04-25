### Phase 4: Full-Stack Dashboard, Auth & RBAC (Weeks 12-16) (Monash W12-Sem break W2) + Payment gateway system

**Focus:** Frontend visualizations, enterprise security, and monetization.

- **What to Build:** Connect the Next.js frontend to the FastAPI backend. Build out the interactive data visualization dashboards (graphs and charts) for financial analysis. Implement industry-level authentication, session management, and Role-Based Access Control (RBAC). This RBAC system will enforce the monetization logic, ensuring only paid users can view the detailed dashboards and visual analytics.
- **What to Learn & Tools to Use:** Learn state management using **Zustand** and **TanStack Query**. Master enterprise authentication flows using **OAuth2**, **JWT** (with HttpOnly cookies), and platforms like **Keycloak** or **Auth0**. Use libraries like **Recharts** or **Chart.js** for the visualizations.
- **Milestone:** A complete, secure web application with restricted routes and a functioning freemium model.
- IMPORTANT: now the Restful API is built, the visualisation is done calling this API. build the visualizations for paid users. build the RBAC systems with strict and production-grade security. builds the **user application that consumes that API**.

This is exactly the transition point where a side project becomes a production-grade SaaS product. Your scattered thoughts represent a complete standard architecture for modern web applications. 

To answer your specific question on monetization: a **tiered monthly subscription (SaaS model)** using Stripe makes much more business sense than registering a bank account for an API key. It reduces friction, aligns with standard developer tools (like Alpha Vantage), and is easier to implement securely using Stripe Checkout and webhooks.

Here is your brain-dump synthesized into a clear, professional Product Requirements Document (PRD) for Phase 4.

---

## Phase 4 Specification: "FinSight" Security, RBAC & Monetization

### 1. Authentication & Security Architecture
* **JWT & Session Management:** FastAPI will generate short-lived JWT Access Tokens and long-lived Refresh Tokens. Crucially for production, these will be sent to the Next.js frontend as **HttpOnly, Secure cookies**, preventing Cross-Site Scripting (XSS) attacks from stealing the tokens.
* **Registration Flow:** When a user registers via email, the system automatically generates a cryptographically secure password, displays it exactly once via the UI for the user to copy, and hashes it using `bcrypt` before storing it in PostgreSQL.
* **State Management:** The Next.js frontend will use **Zustand** to manage the global `user` state (logged in, role, tier) and **TanStack Query** to cache and invalidate API calls to the FastAPI backend based on that state.

### 2. Role-Based Access Control (RBAC) Matrix

| Feature / View | Unauthenticated | Free User (Logged In) | Paid User (Pro Tier) | Admin |
| :--- | :---: | :---: | :---: | :---: |
| **Landing Page & API Docs** | ✅ | ✅ | ✅ | ✅ |
| **Basic Visualizations** | ✅ | ✅ | ✅ | ✅ |
| **Account Settings** | ❌ | ✅ | ✅ | ✅ |
| **Developer API Key** | ❌ | ❌ | ✅ (1 Key) | ✅ (Multiple) |
| **Advanced Visualizations** | ❌ | ❌ | ✅ | ✅ |
| **Admin Dashboard** | ❌ | ❌ | ❌ | ✅ |

### 3. The Admin User Management Dashboard
* A hidden route (`/admin/dashboard`) accessible only to accounts with the `admin` role in the database.
* **Capabilities:** A data table displaying all registered users, their creation date, their Stripe subscription status (Free/Paid), and their RBAC role.
* **Actions:** Admins can manually revoke API keys, upgrade/downgrade user tiers, or delete accounts entirely.

### 4. Monetization & Stripe Integration
* **The Gateway:** Integrate **Stripe Checkout**. When a Free User clicks "Upgrade", they are redirected to a Stripe-hosted payment page for a monthly subscription.
* **The Webhook:** Set up a FastAPI endpoint to listen for Stripe webhooks (e.g., `invoice.payment_succeeded`). When triggered, the backend automatically updates the user's status to "Paid" in the database and generates their API key.

### 5. Visualization Strategy (Free vs. Paid)
To drive conversions, the Free tier must show value, but the Paid tier must provide the actual analytical edge for the target blue-chip companies (Maybank, CIMB, TNB, etc.).

* **Free Tier Visuals (The Teaser):**
    * *Historical Performance:* Simple line charts of quarterly revenue and net income over the last 3 years using Recharts.
    * *High-Level Metrics:* KPI cards showing the latest EPS (Earnings Per Share) and P/E ratio.
* **Paid Tier Visuals (The Value Prop):**
    * *LLM Sentiment Overlay:* A composite chart showing stock price overlaid with an AI-generated "sentiment score" derived from the tone of the earnings reports.
    * *Peer Comparison Radar:* A Recharts Radar chart comparing a selected company (e.g., Maybank) against its peers (CIMB) across 5 axes: Liquidity, Debt-to-Equity, Profit Margin, Asset Turnover, and Return on Equity.
    * *The Waterfall Chart:* A breakdown of how gross revenue flows down to net income, isolating exact operating expenses and taxes parsed directly from the PDFs.

---

<Elicitations message="Which technical flow should we lock down next?">
  <Elicitation label="Design the HttpOnly JWT Auth Flow" query="Break down the exact sequence and code structure for implementing JWT HttpOnly cookies between FastAPI and Next.js." />
  <Elicitation label="Map out the Stripe Webhook Integration" query="Explain how to set up the Stripe subscription flow and the FastAPI webhook to automatically generate API keys upon payment." />
  <Elicitation label="Design the Admin User Management DB Schema" query="Help me design the PostgreSQL database schema needed to handle these specific RBAC roles, Stripe IDs, and API keys." />
</Elicitations>