# Jarvis Voice Assistant

Jarvis is the hands-free AI assistant built into FinSight. It lets you navigate the platform, ask financial questions, and retrieve company information entirely by voice.

---

## Overview

```
You speak → Browser captures audio → FastAPI transcribes → Dify classifies intent → FinSight responds
```

Jarvis supports **6 intent types**:

| # | Intent | Example | Action |
|---|--------|---------|--------|
| 1 | **Navigation** | "Go to Maybank" | Routes to company page |
| 2 | **Financial Info** | "What is Petronas's P/E ratio?" | Queries financial database |
| 3 | **Company Info** | "Tell me about CIMB" | Searches company PDFs |
| 4 | **Documentation** | "How do I export data?" | Searches platform docs |
| 5 | **Small Talk** | "Hello Jarvis" | Conversational response |
| 6 | **Sensitive Topic** | (anything harmful) | Polite refusal |

---

## Quick Start

### Activate Jarvis
- **Click** the blue mic button (bottom-right of any page)
- **Press** the `J` keyboard shortcut

### Speak your command
The panel shows your live transcript as soon as you stop speaking.

### Jarvis responds
- Navigation commands → auto-routes you to the page
- Questions → answer shown in the panel and spoken aloud

---

## See Also

- [Architecture & Pipeline](./architecture.md) — full technical pipeline diagram
- [API Reference](./api-reference.md) — backend endpoints
- [Intent Classifier Prompt](./intent-classifier.md) — the system prompt used for routing
- [Deployment Guide](./deployment.md) — local Docker + production setup
- [Phase Roadmap](./roadmap.md) — what's coming next
