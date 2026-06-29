# Task 2 Implementation Report: 板块资金数据获取器与调度器

## What was implemented
1. **Config Configuration (`backend/app/config.py`):**
   - Configured `POLL_INTERVAL_SECONDS = 3.0` and the Eastmoney API URL `EASTMONEY_API_URL`.
2. **DataFetcher & Scheduler (`backend/app/scheduler.py`):**
   - Created `DataFetcher` class initialized with a `ConnectionManager`.
   - Implemented `fetch_and_broadcast` to concurrently fetch industry and concept capital flows from Eastmoney API using `httpx.AsyncClient` and `asyncio.gather`.
   - Parsed raw parameters to standard formats (calculating inflow in 100M RMB units, rounded to 2 decimal places).
   - Maintained a minute-granularity history cache `history_cache` storing current cumulative net inflow of the day per sector.
   - Broadcasted payload to WebSocket clients.
   - Implemented `start_loop` to run the task every 3 seconds.
3. **Tests (`backend/tests/test_scheduler.py`):**
   - Wrote unit tests using `pytest` and `pytest-asyncio` mocking out `ConnectionManager` and HTTP API responses.

## Verification & Test Results
- Ran: `PYTHONPATH=backend .venv/bin/pytest backend/tests/ -v`
- Output: 3 passed in 0.18s (including the two preexisting manager tests).

## TDD Evidence

### RED State
- **Command Run:** `PYTHONPATH=backend .venv/bin/pytest backend/tests/test_scheduler.py -v`
- **Failing Output:**
  ```
  ImportError while importing test module '/Users/yanglinzhen.3/AI_Projects/stock/backend/tests/test_scheduler.py'.
  E   ModuleNotFoundError: No module named 'app.scheduler'
  ```
- **Why Failure Was Expected:**
  The test was written to import `DataFetcher` from `app.scheduler` before the `scheduler.py` file was created, ensuring the import would fail due to the missing module.

### GREEN State
- **Command Run:** `PYTHONPATH=backend .venv/bin/pytest backend/tests/ -v`
- **Passing Output:**
  ```
  backend/tests/test_manager.py::test_connection_lifecycle PASSED          [ 33%]
  backend/tests/test_manager.py::test_broadcast_failure_cleanup PASSED     [ 66%]
  backend/tests/test_scheduler.py::test_data_fetch_and_formatting PASSED   [100%]
  ============================== 3 passed in 0.18s ===============================
  ```

## Files Changed
- `backend/app/config.py` (created)
- `backend/app/scheduler.py` (created)
- `backend/tests/test_scheduler.py` (created)

## Self-Review Findings
- The scheduler functions properly under mocks. Real network timeouts are set to 5 seconds to prevent hung queries.
- Formatting calculations divide raw values by `100,000,000` to correctly yield inflow in 100M RMB units (亿元).

## Issues or Concerns
None. All requirements met.

## Task 2 Review Fix Report

### What was fixed
1. **AsyncClient Reuse (`backend/app/scheduler.py`):**
   - Added `self.client = None` inside `DataFetcher.__init__`.
   - Modified `fetch_and_broadcast` to instantiate/reuse a persistent `httpx.AsyncClient` client instance on demand if `self.client is None or self.client.is_closed`. This avoids recreating the client on every 3-second cycle.
2. **Flashing Empty Data on API Failure (`backend/app/scheduler.py`):**
   - Handled exceptions during fetch by returning the existing `self.latest_data` immediately. This prevents overwriting the latest data with empty lists or broadcasting empty datasets to clients, averting dashboard flashing.
3. **Fixed Test Mocking & Added Tests (`backend/tests/test_scheduler.py`):**
   - Fixed `raise_for_status` mocking to avoid coroutine warnings.
   - Added unit test `test_data_fetch_client_reuse` to assert the client instance is correctly reused.
   - Added unit test `test_data_fetch_failure_no_broadcast` to assert exception handling does not overwrite data or trigger broadcast.

### Test Command
```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/
```

### Test Output
```
============================= test session starts ==============================
platform darwin -- Python 3.10.20, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/yanglinzhen.3/AI_Projects/stock
plugins: anyio-4.14.1, asyncio-1.4.0
asyncio: mode=strict, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 5 items

backend/tests/test_manager.py ..                                         [ 40%]
backend/tests/test_scheduler.py ...                                      [100%]

============================== 5 passed in 0.22s ===============================
```

