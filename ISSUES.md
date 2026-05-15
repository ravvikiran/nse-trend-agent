# QuantGridIndia — Known Issues & Technical Debt

Last Updated: 2026-05-15

This document catalogs all known issues, code quality concerns, security vulnerabilities, and architectural improvements needed. Issues are prioritized by severity.

---

## ✅ Resolved Issues

| ID | Issue | Resolution |
|----|-------|------------|
| SEC-001 | Exposed Telegram secrets in `.env` | `.env` is in `.gitignore`. If ever committed, revoke token and purge history. |
| SEC-002 | `.env.railway` not in `.gitignore` | Added `.env.railway` to `.gitignore`. |
| SEC-003 | Unpinned dependency versions | Pinned all dependencies to exact versions in `requirements.txt`. |
| CLEANUP-001 | Dhan broker integration code removed | Deleted `dhan_provider.py` and `dhan_auth.py`. Updated README and `.env.railway`. |
| CLEANUP-002 | Kite provider removed | Deleted `kite_provider.py` and `test_kite_provider.py`. Updated README, spec documents, and ISSUES.md to remove all Kite references. |
| CONFIG-001 | No runtime validation of config file | `ConfigManager` now distinguishes "not found" (warning + defaults) from "invalid JSON" (raises ValueError). |
| CONFIG-002 | Config path relative to CWD | Resolved relative to project root using `Path(__file__).resolve().parent.parent.parent`. |
| CONFIG-003 | Missing cross-field validation | Added validation: EMA periods must be strictly increasing, RS weights and ranking weights must sum to 1.0. |
| LOGIC-001 | Duration check logic reversed | Fixed: `max_scan_duration_seconds` is now the WARNING threshold, `warn_scan_duration_seconds` is the ERROR threshold. |
| PERF-001 | No HTTP connection pooling | Added `requests.Session` with `HTTPAdapter` pooling to `TelegramService` and `YahooFinanceProvider`. |
| DB-001 | Alert cooldown state lost on restart | `Deduplicator` now persists state to SQLite `alert_state` table. Loads on startup, survives restarts. |
| DB-003 | Database writes lack retry on lock | Added `@retry_on_lock()` decorator with exponential backoff for SQLite writes. |
| CODE-001 | Bare `except` clauses | Replaced with `except Exception as e` + `logger.debug(...)` in `stage3_entry_trigger.py`. |
| CODE-002 | Unsafe `.iloc[-1]` on empty DataFrames | Added empty/length guards in `market_breadth_filter.py` and `stage2_relative_strength.py`. |
| CODE-003 | f-strings in logging calls | Replaced all f-string logging with `%s` lazy formatting across all modules. |
| ARCH-001 | Overly complex `_check_compression_breakout` | Extracted `_find_compression_window()` and `_has_tight_candle_window()` helper methods. |
| ARCH-002 | `ScannerConfig` god object | Added sub-config dataclasses (`EMAConfig`, `ATRConfig`, `VolumeConfig`, `RSWeights`, `RankingWeights`) with property accessors. Flat fields retained for backward compatibility. |
| ARCH-003 | Hardcoded NSE holiday list | Moved to `config/nse_holidays.json` (includes 2024-2026). Loaded dynamically at startup. |
| ARCH-004 | Tight coupling AlertFormatter → TelegramService | Introduced `AlertService` ABC interface. `TelegramService` implements it. `AlertFormatter` accepts any `AlertService`. |
| ARCH-005 | Missing broker provider abstraction | Added `--broker` CLI argument with choices `["yahoo", "mock"]`. Factory dispatches based on flag. |
| ARCH-006 | Duplicate IST timezone definitions | Created `src/momentum/utils/timezones.py` with single `IST` constant. All modules import from there. |
| OPS-001 | Railway cron schedule assumes UTC | Added documentation comment in `railway.toml` explaining the UTC assumption. |
| CONFIG-003 (railway) | Railway env file contained Dhan credentials | Cleaned `.env.railway` — removed all Dhan-specific sections. |

---

## 🟡 MEDIUM Priority Issues (Remaining)

### TEST-001: No Integration Tests
**Severity:** HIGH → MEDIUM (downgraded — unit test coverage is comprehensive at 301 tests)  
**Status:** Open

`tests/` contains only unit tests with mocked dependencies. No end-to-end test validates the full pipeline with real market data.

**Impact:** Regressions in data fetching, parsing, or pipeline integration go undetected.

**Files:** `tests/` directory

**Fix:** Add integration test suite:
```python
# tests/integration/test_full_pipeline.py
@pytest.mark.integration
async def test_full_scan_cycle_with_yahoo():
    provider = YahooFinanceProvider(batch_size=10)
    await provider.connect()
    # Run 1 cycle, assert no exceptions, validate output shape
```

Run daily in CI with small universe subset.

### DB-002: No Database Schema Migration Tracking
**Severity:** MEDIUM  
**Status:** Open

Schema changes over time will break old deployments. No versioning or migration logic.

**Files:** `src/momentum/scan_logger.py`, `src/momentum/trade_journal.py`

**Fix:** Add `schema_version` table and incremental migration functions, or use Alembic.

---

## 🔵 LOW Priority Issues (Remaining)

### CODE-004: Long Method `_log_cycle` in ScanLogger
**Severity:** LOW  
**Status:** Open (partially addressed — extracted into `_log_cycle_impl` with retry wrapper)

**Files:** `src/momentum/scan_logger.py`

### CODE-005: Inconsistent Error Handling Between Providers
**Severity:** LOW  
**Status:** Open

YahooFinanceProvider has retry/backoff logic via HTTPAdapter; a shared retry decorator would improve consistency.

**Files:** `src/momentum/providers/yahoo_provider.py`

### CODE-006: Magic Numbers Not Extracted
**Severity:** LOW  
**Status:** Open

Examples:
- `stage3_entry_trigger.py` — `latest_idx < 7` hardcoded
- `yahoo_provider.py` — lookback days magic numbers

### CODE-007: Missing Docstrings for Internal Methods
**Severity:** LOW  
**Status:** Open

Some `_calculate_*` and `_check_*` methods lack docstrings.

### CODE-008: Type Hint Inconsistencies
**Severity:** LOW  
**Status:** Open (partially addressed — added `from __future__ import annotations` to `models.py`)

### CODE-010: No Index Optimization for Date Queries
**Severity:** LOW  
**Status:** Open

`scan_cycles.timestamp` index is B-tree; queries filtering by `date(timestamp)` can't use index efficiently.

### OPS-002: Missing `__all__` Exports
**Severity:** LOW  
**Status:** Open (partially addressed — `__init__.py` now has comprehensive `__all__`)

---

## 📋 Additional Notes

### Potential Race Conditions
While current scan cycles are sequential, future async enhancements should review:
- `Deduplicator._state` mutations — now persisted to SQLite, but add `asyncio.Lock` if parallel scans added
- `TradeJournal` DB connections — use `aiosqlite` for true async

### Security Hardening
- Install `pre-commit` with `gitleaks` to prevent future secret commits
- Consider `bandit` scan for security anti-patterns
- Run `pip-audit` regularly to catch new vulnerabilities in pinned dependencies

---

## 🎯 Recommended Action Order

1. **Next sprint:**
   - Add integration test (TEST-001)
   - Database migration system (DB-002)

2. **Next quarter:**
   - Migrate to `aiosqlite` for true async DB access
   - Full security audit: `bandit -r src/`, `pip-audit`, `safety check`
   - Extract remaining magic numbers to config (CODE-006)

---

*Generated by Kiro — 2026-05-15*
