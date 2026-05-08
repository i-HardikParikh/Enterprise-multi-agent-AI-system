# 🖥️ Enterprise Agent — Next.js Frontend

Production-grade Next.js 14 frontend for the Enterprise Multi-Agent AI System.

## Pages

| Route | Description |
|---|---|
| `/` | Main dashboard — run agents, view pipeline, stream output |
| `/history` | Look up past jobs by ID |
| `/settings` | Provider configuration guide + API status |

## Features

- **Real-time SSE streaming** — see each agent step as it runs
- **Live pipeline visualization** — animated nodes (idle → active → done)
- **Execution log** — timestamped entries with severity levels
- **Output panel** — markdown rendered + JSON formatted + copy/download
- **LLM-as-Judge eval** — run detailed evaluation on any output
- **Document upload** — upload .txt/.pdf/.csv to the RAG knowledge base
- **Provider status bar** — shows active LLM provider + model in header
- **History lookup** — fetch any past job by ID
- **Settings page** — setup guide for all 3 free providers

## Quick Start

```bash
cd agent-frontend
npm install
npm run dev
# Open http://localhost:3000
```

Make sure the Python backend is running at `http://localhost:8000`.

## Environment

```bash
# .env.local (already created)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Change `NEXT_PUBLIC_API_URL` to point to your deployed backend.

## Project Structure

```
src/
├── app/
│   ├── layout.tsx          ← Root layout (fonts, global styles)
│   ├── globals.css         ← Tailwind + custom styles
│   ├── page.tsx            ← Main dashboard
│   ├── history/page.tsx    ← Job history lookup
│   └── settings/page.tsx   ← Provider config guide
├── components/
│   ├── PipelineNode.tsx    ← Animated agent pipeline node
│   ├── LogPanel.tsx        ← Real-time execution log
│   ├── OutputPanel.tsx     ← Output with markdown + tabs
│   ├── ScoreBadge.tsx      ← Quality score with circular progress
│   ├── MetricCard.tsx      ← Metric display card
│   ├── EvalPanel.tsx       ← LLM-as-judge evaluation UI
│   ├── UploadModal.tsx     ← Drag-and-drop file upload
│   └── ProviderBar.tsx     ← API status + provider info
├── hooks/
│   └── useAgentStream.ts  ← SSE streaming hook + state management
└── lib/
    ├── api.ts             ← All API calls (typed)
    └── types.ts           ← TypeScript types
```

## Tech Stack

`Next.js 14` · `TypeScript` · `Tailwind CSS` · `Lucide React` · `DM Sans` · `Syne` · `JetBrains Mono`
