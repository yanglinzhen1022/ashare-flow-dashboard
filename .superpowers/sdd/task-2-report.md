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

## Task 2 Second Re-Review Fix Report (2026-06-29)

### What was fixed
1. **Stale History Cache Accumulation (`backend/app/scheduler.py`):**
   - Added `self.last_date` initialization in `__init__`.
   - In `_update_history_cache`, compared the current date with `self.last_date`. If they differ (indicating a new trading day), cleared `self.history_cache` and updated `self.last_date`.
2. **Unsafe Dictionary Default Handling (`backend/app/scheduler.py`):**
   - Changed format parsing to use the `(item.get("fXX") or 0.0)` (and `or ""`) pattern in `_format_items` to protect against explicit `null` values returned by the Eastmoney API, preventing potential `TypeError` on division or formatting.
3. **Verification Tests (`backend/tests/test_scheduler.py`):**
   - Added `test_history_cache_cleared_on_new_day` to verify that `history_cache` is cleared when the date changes.
   - Added `test_unsafe_dictionary_default_handling` to verify that `_format_items` correctly handles `None` values by falling back to safe defaults without throwing exceptions.

### Test Command
```bash
python3 -m pytest
```

### Test Output
```
============================== 7 passed in 0.27s ===============================
```

## Task 2 Re-Review Fix Report (Part 4) (2026-06-29)

### What was fixed
1. **Timezone Dependency (UTC+8 pinning) (`backend/app/scheduler.py`):**
   - Replaced host-dependent `time.localtime()` with `datetime` with a fixed timezone offset of UTC+8 (China Standard Time) for all date/time formatting.
   - Pinned timezone for `self.last_date`, `current_date`, `current_time` (timestamp), and `current_min`.
2. **Unsafe Non-Numeric Strings (`backend/app/scheduler.py`):**
   - Implemented `_safe_float` in `DataFetcher` to safely parse floats and fallback to `0.0` on failure, including checking for `NaN` and `None`.
   - Used `_safe_float` for parsing fields in `_format_items` to protect against non-numeric strings like `"-"` or `"NaN"`.
3. **Resources Clean Up (`backend/app/scheduler.py`):**
   - Added an `async def shutdown(self):` method to `DataFetcher` that calls `await self.client.aclose()` if `self.client` is not None.
4. **Verification Tests (`backend/tests/test_scheduler.py`):**
   - Expanded `test_unsafe_dictionary_default_handling` to verify handling of non-numeric strings like `"-"` and `"NaN"`.
   - Added `test_shutdown_closes_client` and `test_shutdown_with_none_client` to verify correct shutdown behavior.

### Test Command
```bash
PYTHONPATH=. ../.venv/bin/pytest
```

### Test Output
```
============================= test session starts ==============================
platform darwin -- Python 3.10.20, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/yanglinzhen.3/AI_Projects/stock/backend
plugins: anyio-4.14.1, asyncio-1.4.0
asyncio: mode=strict, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 9 items

tests/test_manager.py ..                                                 [ 22%]
tests/test_scheduler.py .......                                          [100%]

============================== 9 passed in 0.26s ===============================
```

## Task 2 Mock Date Fix Report (2026-06-29)

### What was fixed
1. **Datetime Mocking Fix (`backend/tests/test_scheduler.py`):**
   - Corrected the mock patching in `test_history_cache_cleared_on_new_day`.
   - Instead of patching `time.strftime` (which was ineffective because `backend/app/scheduler.py` uses `datetime.now(cst_tz).strftime`), patched `app.scheduler.datetime` and set its return values to mock `datetime.now(cst_tz).strftime("%Y-%m-%d")` returning `"2026-06-29"`.
   - This ensures the test success is independent of the actual current date on the host machine.

### Test Command
```bash
PYTHONPATH=. pytest
```

### Test Output
```
============================= test session starts ==============================
platform darwin -- Python 3.10.20, pytest-9.1.0, pluggy-1.6.0
rootdir: /Users/yanglinzhen.3/AI_Projects/stock/backend
plugins: asyncio-1.4.0, anyio-4.13.0
asyncio: mode=strict, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 9 items

tests/test_manager.py ..                                                 [ 22%]
tests/test_scheduler.py .......                                          [100%]

============================== 9 passed in 0.29s ===============================
```
