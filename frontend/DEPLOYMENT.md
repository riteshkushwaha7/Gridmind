# Deploying GRIDMIND to Vercel

This repo ships `next.config.mjs` (Next.js 14.2). Copy values from `.env.example` into the Vercel project settings.

```bash
npm i -g vercel
vercel --prod
```

Set these env vars in Vercel dashboard:

- NEXT_PUBLIC_APP_NAME
- NEXT_PUBLIC_VERSION
- NEXT_PUBLIC_DATA_MODE (set to "synthetic" for demo)

To swap mock data for real data:

1. Replace exports in lib/mockData.ts with API calls
2. Add server-side data fetching in each page.tsx
3. For OCPP integration: add WebSocket handler in app/api/ocpp/route.ts
