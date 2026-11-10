# A-Share Capital Flow Dashboard - Developer Notes & Progress Log

This file acts as a persistent memory and rule file for the Antigravity CLI to retrieve project context immediately when starting a new session in this workspace.

---

## 📅 Current Progress Status: 100% COMPLETE & VERIFIED

All planned features and code-review fixes for the A-Share Capital Flow Dashboard are fully completed, tested, and running.

### Key Milestones Achieved:
1. **HTTP Connection Pool Reuse (Task 1 & Review Fix):**
   - Utilizes persistent `httpx.AsyncClient` natively without thread-blocking custom transport layers.
   - Global `socket.getaddrinfo` IPv4 resolution patch for `eastmoney.com` permanently bypasses empty replies/CDN drops from IPv6 CDN nodes.
2. **Interactive TreeMap (Task 2):**
   - Roam and zoom features enabled.
   - Double-click anywhere on the TreeMap to trigger a smooth reset.
3. **Multi-Period Switcher & Trend Lines (Task 3 & Today Trend Fix):**
   - Period options: Today (今日分时), 3-day, 5-day, 10-day.
   - Intraday `1d` period uses the backend memory cache (`fetcher.history_cache`) to avoid fetching empty 1-minute arrays from Eastmoney.
   - Multi-day periods pull 30-day historical K-lines (`klt=101`) to render cumulative trend curves.
4. **Reverse Stock Linkage (Task 4):**
   - API endpoint `/api/stocks/search` handles stock lookup with safe fallback parsing.
   - UI switches page tab and highlights corresponding sectors on stock input.
   - The concept blacklist is DRY-refactored into `isConceptActive` helper.
5. **Robust Test Suite:**
   - 26/26 tests pass with 0 warnings. Tests mock network calls and restore state (`fetcher.latest_data`) cleanly.
6. **Core Stocks Ranking Expanded to Top 50:**
   - `/api/sectors/{code}/stocks` supports configurable `limit` parameter, defaulting to `50` (up from `10`).
   - Caching layer dynamically adjusts to requested limit, keeping 30s TTL.
   - Frontend UI layout dynamically shows `(Top N)` badge with seamless scroll support and aligned rank numbers.

---

## 🛠️ How to Run & Verify
- **Start Dashboard Server:** `bash run.sh` (runs at http://localhost:8080)
- **Run Pytest Suite:** `PYTHONPATH=backend .venv/bin/pytest backend/tests/ -v`
- **Build Frontend:** `npm run build` (inside `frontend/`)

---

## 🔮 Future Optimization Roadmap

When resuming development in this workspace, prioritize the following optimization opportunities:

1. **Frontend Assets & Chunking (Important):**
   - Vite build output warns of chunks >500kB. Optimize Rollup configuration (`manualChunks` in `vite.config.js`) to split vendor dependencies (like ECharts).
2. **Enhanced Multi-Period Caching:**
   - Currently, when switching between 3d/5d/10d, the frontend fetches daily K-line histories on sector clicks. Consider caching daily K-line histories on the frontend to speed up switching.
3. **Scale & Pub/Sub Backend Architecture:**
   - If scaling up for many concurrent users, replace the local in-memory `ConnectionManager` broadcast with a Redis-based Pub/Sub adapter to support multi-process/multi-instance deployments.
4. **Extended Financial Analytics:**
   - Integrate market index correlations (e.g. SSE Composite index overlay on the trend chart) to analyze capital flow impacts against index movements.
