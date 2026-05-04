# GRIDMIND — AI-Driven EV Charging Optimization

> Research prototype for BESCOM EV Infrastructure Challenge

## Problem Statement

Part A: Demand prediction and charging schedule optimization

Part B: Infrastructure location planning for new charging stations

## Configuration

Next.js 14.2 loads `next.config.mjs` (TypeScript `next.config.ts` is supported in newer Next.js releases). Image optimization is disabled for simpler static hosting.

## Quick Start

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
```

## Pages

| Route | Description | Status |
|-------|-------------|--------|
| / | Landing page | ✅ Complete |
| /dashboard | Live grid operations | ✅ Complete |
| /stations | Station map and health | ✅ Complete |
| /forecasting | AI demand forecasting (Part A) | ✅ Complete |
| /planner | Infrastructure location planning (Part B) | ✅ Complete |
| /blockchain | Transaction ledger | 🚧 Mock data |

## Research Basis

1. OCPP-based PPO Scheduling with Safety Projection Layer
2. DR-LB-AI Framework — Singh et al., Scientific Reports / Nature, 2024
3. Solar PV + BMS Integration for EV Charging

## Feature Status

| Feature | Status |
|---------|--------|
| Demand forecasting (15-min) | ✅ Simulated |
| PPO schedule advisor | ✅ Simulated |
| Zone demand scoring | ✅ Mock data |
| K-means location ranking | ✅ Scoring model |
| Blockchain ledger | 🚧 Mock |
| Live OCPP connection | 📋 Planned |
| V2G integration | 📋 Planned |
| Anomaly detection | 📋 Planned |
| Real BESCOM feeder data | 📋 Requires data agreement |

## BESCOM Non-Negotiables Compliance

- No modification to existing distribution systems ✅
- Decision-support layer only ✅
- Synthetic/masked data ✅
- Explainable outputs ✅
- Grid constraint awareness ✅
- No hosted LLM on sensitive data ✅
