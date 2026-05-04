# GRIDMIND — Frontend ⇆ Backend Connection Guide

The data layer (`lib/api.ts`, `hooks/`, `store/gridmind.ts`) is wired and ready.
UI components still consume the **legacy mock data** in `lib/mockData.ts` — this
guide shows how to swap them, page by page, to hit the live gateway.

## Page → hook → endpoint

| Page                                       | Hook                                       | Backend endpoint                  |
| ------------------------------------------ | ------------------------------------------ | --------------------------------- |
| `/dashboard`                               | `useDashboardOverview()`                   | `GET /dashboard/overview`         |
| `/dashboard` (alerts strip / banner)       | `useAlerts()`                              | `GET /dashboard/alerts`           |
| `/dashboard` (drill into one zone)         | `useZoneDetail(zoneId)`                    | `GET /dashboard/zone/{zone_id}`   |
| `/forecasting` (one-zone chart)            | `useZoneForecast(zoneId, hours)`           | `GET /forecast/{zone_id}?hours=H` |
| `/forecasting` (overview across zones)     | `useAllForecast(hours)`                    | `GET /forecast/all?hours=H`       |
| `/stations` (current PPO setpoints)        | `useCurrentSchedule()`                     | `GET /schedule/current`           |
| `/stations` (operator override button)     | `useOverrideSchedule().mutate(...)`        | `POST /schedule/override`         |
| `/planner` (zone ranking + recommendations)| `useZoneRanking()`                         | `GET /zones/ranking`              |
| `/planner` ("Recompute" button)            | `useReplan().mutate()`                     | `POST /clustering/replan`         |
| any service-status badge                   | `getSystemHealth()` (call directly)        | `GET /health`                     |

## How to swap one component from mock → live

The pattern is the same on every page: drop the import that pulls from
`lib/mockData.ts` and replace it with a hook call.

### Dashboard — `components/dashboard/DashboardClient.tsx`

```tsx
// before
import { networkSnapshot, energyTimeseries24h } from "@/lib/mockData";
const grid = networkSnapshot;

// after
import { useDashboardOverview } from "@/hooks/useDashboard";
const { data: overview, isLoading } = useDashboardOverview();
const grid = overview?.grid_total;
```

### Forecasting — `components/forecasting/ForecastingPageClient.tsx`

```tsx
import { useZoneForecast } from "@/hooks/useForecast";
const { data: forecast } = useZoneForecast(zoneId, 4);
// forecast.forecast: ForecastPoint[]   ← drop into Recharts
```

### Stations — `components/stations/StationsPageClient.tsx`

```tsx
import { useCurrentSchedule, useOverrideSchedule } from "@/hooks/useSchedule";
const { data: schedule } = useCurrentSchedule();
const override = useOverrideSchedule();
// later, in an onClick:
override.mutate({ zoneId: "Z01", powerKw: 22 });
```

### Planner — `components/planner/PlannerPageClient.tsx`

```tsx
import { useZoneRanking, useReplan } from "@/hooks/useZones";
const { data: ranking } = useZoneRanking();
const replan = useReplan();
// "Recompute" button: <button onClick={() => replan.mutate()}>
```

### Selecting a zone (Zustand)

```tsx
import { useGridmindStore } from "@/store/gridmind";
const selected = useGridmindStore((s) => s.selectedZoneId);
const setSelected = useGridmindStore((s) => s.setSelectedZoneId);
```

## Environment setup (3 commands)

```bash
cd frontend
cp .env.example .env.local           # then edit NEXT_PUBLIC_API_URL if needed
npm install                          # installs @tanstack/react-query + zustand
npm run dev                          # http://localhost:3000
```

The backend gateway must be reachable at the URL in `NEXT_PUBLIC_API_URL`.
For the Docker Compose stack: `docker compose up -d` from the repo root, then
the default `http://localhost:8000` is correct.

## Verifying the connection

In the browser dev tools:

1. **Network tab** — every refresh of `/dashboard` should fire
   `GET http://localhost:8000/dashboard/overview` (200 OK, JSON body).
   If you see no requests, `NEXT_PUBLIC_API_URL` is unset → mock fallback.
2. **Console tab** — look for `[GRIDMIND API]` warnings. Each one means a call
   fell back to mock data, with the underlying error logged inline.
3. **Response headers** — every gateway response includes
   `X-Correlation-ID: <hex>`; useful for grepping the gateway JSON logs
   (`docker compose logs backend-gateway | grep <id>`).
4. **TanStack Devtools (optional)** — install
   `@tanstack/react-query-devtools` and mount `<ReactQueryDevtools />` inside
   `Providers` to inspect cache state, stale times, and refetch cadences.

## Behaviour when backend is down

Every function in `lib/api.ts` is **non-throwing**: if the gateway is
unreachable or returns non-2xx, it logs `[GRIDMIND API]` and returns the
matching payload from `lib/mock-fallback.ts`. The UI never breaks — it just
silently degrades to fallback shapes.
