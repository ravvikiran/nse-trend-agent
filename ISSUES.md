# QuantGridIndia — Known Issues & Technical Debt

Last Updated: 2026-05-15

This document catalogs all known issues, code quality concerns, security vulnerabilities, and architectural improvements needed. Issues are prioritized by severity.

---

## ✅ Resolved Issues

| ID | Issue | Resolution |
|----|-------|------------|
| SEC-001 | Exposed Telegram secrets in `.env` | `.env` is in `.gitignore`. If ever committed, revoke token and purge history. |
| SEC-002 | `.env.railway` not in `.gitignore` | Added `.env.railway` to `.gitignore`. |
| CLEANUP-001 | Dhan broker integration code removed | Deleted `dhan_provider.py` and `dhan_auth.py`. Updated README and `.env.railway`. |
| CLEANUP-002 | Kite provider removed | Deleted `kite_provider.py` and `test_kite_provider.py`. Updated README, spec documents, and ISSUES.md to remove all Kite references. |
| CONFIG-003 | Railway env file contained Dhan credentials | Cleaned `.env.railway` — removed all Dhan-specific sections. |

---

## ⚠️ Deferred Issues (User Marked for Later Review)

| ID | Issue | Location | Notes |
|----|-------|----------|-------|
| LOGIC-001 | Duration check logic reversed (error/warning thresholds swapped) | `src/momentum/scanner.py:784-804` | User aware; will address later. |

---

## 🔴 CRITICAL Issues

### SEC-003: Unpinned Dependency Versions (Potential Supply Chain Attack)
**Severity:** CRITICAL  
**Status:** Open

`requirements.txt` uses open-ended version specifiers (`>=`). This risks:
- Automatic installation of future breaking versions
- Known vulnerabilities in older versions that satisfy the range

**Affected dependencies:**
- `pandas>=2.0.0` — vulnerable to CVE-2023-47239 if <2.2.0
- `numpy>=1.24.0` — multiple CVEs if <1.26.4

**Files:** `requirements.txt:7-8`

**Fix:**
```txt
pandas==2.2.2
numpy==1.26.4
requests==2.31.0
ta==0.11.0
yfinance==0.2.36
python-dotenv==1.0.1
pytz==2024.1
```

Also run `pip-audit` regularly to catch new vulnerabilities.

---

## 🟠 HIGH Priority Issues

### TEST-001: No Integration Tests
**Severity:** HIGH  
**Status:** Open

`tests/` contains only unit tests with mocked dependencies. No end-to-end test validates the full pipeline with real market data.

**Impact:** regressions in data fetching, parsing, or pipeline integration go undetected.

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

### PERF-001: No HTTP Connection Pooling
**Severity:** HIGH  
**Status:** Open

All data providers (`dhan_provider` removed, but `yahoo_provider.py`, `telegram_service.py`) use `requests.get/post` without session reuse. Each request creates a new TCP connection → high latency and resource exhaustion under load.

**Files:** 
- `src/momentum/providers/yahoo_provider.py`
- `src/momentum/telegram_service.py`

**Fix:**
```python
import requests

class YahooFinanceProvider:
    def __init__(self, ...):
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10, pool_maxsize=20, max_retries=3
        )
        self._session.mount("https://", adapter)
```
Use `self._session` for all requests. Apply same to `TelegramService`.

### DB-001: Alert Cooldown State Lost on Restart
**Severity:** HIGH  
**Status:** Open

`Deduplicator` stores cooldown state in memory only. If process restarts (e.g., Railway dyno recycle), all cooldowns reset → risk of duplicate alerts within 30 minutes.

**Files:** `src/momentum/deduplicator.py:34`

**Fix:** Persist state to SQLite. Add table:
```sql
CREATE TABLE IF NOT EXISTS alert_state (
    symbol TEXT PRIMARY KEY,
    last_alert_time TEXT,
    last_setup_type TEXT,
    last_rank_score REAL,
    alert_count_today INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
Load on startup, update on each alert, clear daily via scheduled job.

---

## 🟡 MEDIUM Priority Issues

### CODE-001: Bare `except` Clauses Swallow Exceptions
**Severity:** MEDIUM  
**Status:** Open

Silent failures make debugging impossible.

**Files:**
- `src/momentum/stage3_entry_trigger.py:496`
- `src/momentum/stage3_entry_trigger.py:531`

**Fix:**
```python
except Exception as e:
    logger.debug("Failed to calculate RSI: %s", e)
    return None
```

### CODE-002: Unsafe `.iloc[-1]` on Potentially Empty DataFrames
**Severity:** MEDIUM  
**Status:** Open

Accessing `.iloc[-1]` without checking DataFrame length can raise `IndexError` if data fetch returns empty.

**Files:**
- `src/momentum/stage2_relative_strength.py:154`
- `src/momentum/market_breadth_filter.py:127-128`
- `src/momentum/scanner.py:389, 444, 531, 541` (some already guarded)

**Fix:**
```python
if len(close) == 0 or close.empty:
    return None
current_price = close.iloc[-1]
```

### CODE-003: f-strings in Logging Calls (Performance Anti-pattern)
**Severity:** MEDIUM  
**Status:** Open

f-strings evaluate eagerly even if log level disabled → wasted CPU.

**Files:** Multiple (`scanner.py`, `stage*`, providers)

**Fix:**
```python
# Bad
logger.error(f"Scan cycle failed: {e}")
# Good
logger.error("Scan cycle failed: %s", e)
```

### ARCH-001: Overly Complex Method `_check_compression_breakout`
**Severity:** MEDIUM  
**Status:** Open

112 lines, nested loops, cyclomatic complexity ~12. Hard to test/maintain.

**Files:** `src/momentum/stage3_entry_trigger.py:211-323`

**Fix:** Extract inner loop:
```python
def _has_tight_candle_window(self, df, atr_series, start_idx, end_idx):
    for i in range(start_idx, end_idx):
        candle = df.iloc[i]
        atr_val = atr_series.iloc[i]
        if pd.isna(atr_val) or atr_val == 0:
            return False
        if (candle["high"] - candle["low"]) >= 0.7 * atr_val:
            return False
    return True
```

### ARCH-002: `ScannerConfig` God Object
**Severity:** MEDIUM  
**Status:** Open

54 lines, 25+ fields mixing EMA params, ATR, volume, ranking weights, timing, filters.

**Files:** `src/momentum/models.py:40-93`

**Fix:** Split into sub-configs:
```python
@dataclass
class EMAConfig: ...
@dataclass
class VolumeConfig: ...
@dataclass
class RankingWeights: ...
@dataclass
class ScannerConfig:
    ema: EMAConfig = field(default_factory=EMAConfig)
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    ...
```

### ARCH-003: Hardcoded NSE Holiday List
**Severity:** MEDIUM  
**Status:** Open

`scan_scheduler.py` hardcodes holidays through 2025. Will break in 2026.

**Files:** `src/momentum/scan_scheduler.py:25-63`

**Fix:** Move holidays to `config/nse_holidays.json` or use `pandas_market_calendars`.

### ARCH-004: Tight Coupling — `AlertFormatter` → `TelegramService`
**Severity:** MEDIUM  
**Status:** Open

`AlertFormatter` depends on concrete `TelegramService`. Hard to test/extend.

**Files:** `src/momentum/alert_formatter.py:32-39`

**Fix:** Introduce `AlertService` interface:
```python
class AlertService(ABC):
    @abstractmethod
    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool: ...
```
`TelegramService` implements it. Allows future Slack/email integrations.

### ARCH-005: Missing Broker Provider Abstraction
**Severity:** MEDIUM  
**Status:** Open

Provider selection hardcoded in `main.py:127-151`. Currently only YahooFinance and Mock are available; adding a new provider requires code changes.

**Files:** 
- `src/momentum/main.py`
- `src/momentum/providers/__init__.py`

**Fix:**
- Export all providers from `providers/__init__.py`
- Add `--broker` CLI argument with choices derived from available providers (e.g., `["yahoo", "mock"]`)
- Factory dispatches based on flag.

### ARCH-006: Duplicate IST Timezone Definitions
**Severity:** MEDIUM  
**Status:** Open

`timezone(timedelta(hours=5, minutes=30))` defined in 6+ files.

**Files:** `main.py`, `scanner.py`, `scan_scheduler.py`, `alert_formatter.py`, `trade_journal.py`, `market_breadth_filter.py`

**Fix:** Create `src/momentum/utils/timezones.py`:
```python
from datetime import timezone, timedelta
IST = timezone(timedelta(hours=5, minutes=30))
```
Import from there.

### DB-002: No Database Schema Migration Tracking
**Severity:** MEDIUM  
**Status:** Open

Schema changes over time will break old deployments. No versioning or migration logic.

**Files:** `src/momentum/scan_logger.py:53-129`, `src/momentum/trade_journal.py:93-128`

**Fix:** Add `schema_version` table and incremental migration functions, or use Alembic.

### DB-003: Database Writes Lack Retry on Lock
**Severity:** MEDIUM  
**Status:** Open

SQLite can fail with `database is locked` under concurrent access (unlikely now, but risky if async tasks grow).

**Files:** `scan_logger.py`, `trade_journal.py`

**Fix:** Wrap writes in retry with exponential backoff catching `sqlite3.OperationalError`.

### CONFIG-001: No Runtime Validation of Config File
**Severity:** MEDIUM  
**Status:** Open

`ConfigManager.load()` silently falls back to defaults if file missing or invalid. User unaware their settings were ignored.

**Files:** `src/momentum/config_manager.py:53-72`

**Fix:** Distinguish "not found" (warning + defaults) from "invalid JSON" (error + exit). Log clearly which path taken.

### CONFIG-002: Config Path Relative to CWD
**Severity:** MEDIUM  
**Status:** Open

`DEFAULT_CONFIG_PATH = "config/momentum_scanner.json"` is relative. Fails if user runs from wrong directory.

**Files:** `src/momentum/config_manager.py:48, 80`

**Fix:** Resolve relative to project root:
```python
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config" / "momentum_scanner.json"
```

### CONFIG-003: Missing Cross-Field Validation
**Severity:** MEDIUM  
**Status:** Open

No validation that EMA periods are ordered (`ema_fast < ema_medium < ema_slow`), or that ranking weights sum to 1.0.

**Files:** `src/momentum/config_manager.py:105-139`

**Fix:** Add cross-field checks:
```python
if not (fast < medium < slow):
    raise ValueError("EMA periods must be strictly increasing")
if abs(sum(ranking_weights.values()) - 1.0) > 0.01:
    raise ValueError("Ranking weights must sum to 1.0")
```

---

## 🔵 LOW Priority Issues

### CODE-004: Long Method `_log_cycle` in ScanLogger
**Severity:** LOW  
**Status:** Open

95 lines; mixes signal insertion, rejected setups insertion, summary logging.

**Files:** `src/momentum/scan_logger.py:131-226`

**Fix:** Extract `_insert_signals()` and `_insert_rejected_setups()`.

### CODE-005: Inconsistent Error Handling Between Providers
**Severity:** LOW  
**Status:** Open

YahooFinanceProvider has retry/backoff logic; a shared retry decorator would improve consistency and maintainability.

**Files:** `src/momentum/providers/yahoo_provider.py`

**Fix:** Create `@retry_async` decorator with exponential backoff.

### CODE-006: Magic Numbers Not Extracted
**Severity:** LOW  
**Status:** Open

Examples:
- `stage3_entry_trigger.py:241` — `latest_idx < 7` hardcoded
- `yahoo_provider.py:38-40` — lookback days magic numbers

**Fix:** Class-level constants or config fields.

### CODE-007: Missing Docstrings for Internal Methods
**Severity:** LOW  
**Status:** Open

Many `_calculate_*` and `_check_*` methods lack docstrings.

**Files:** `stage3_entry_trigger.py`, `stage2_relative_strength.py`, etc.

**Fix:** Add Google/NumPy style docstrings with Args, Returns, and brief algorithm description.

### CODE-008: Type Hint Inconsistencies
**Severity:** LOW  
**Status:** Open

Mixed `list` vs `List`, `dict` vs `Dict`. Use `from __future__ import annotations` for forward compatibility.

**Files:** Multiple, e.g., `data_provider.py:44`

### CODE-009: Optional Dependencies Imported Inside Functions
**Severity:** LOW  
**Status:** Open

`dhan_auth.py` and `dhan_provider.py` had lazy imports — now removed. Check if any other modules do this.

**Files:** None remaining (post-Dhan removal). Verify with grep.

### CODE-010: No Index Optimization for Date Queries
**Severity:** LOW  
**Status:** Open

`scan_cycles.timestamp` index is B-tree; queries filtering by `date(timestamp)` can't use index efficiently.

**Files:** `src/momentum/scan_logger.py` schema

**Fix:** Add generated column:
```sql
ALTER TABLE scan_cycles ADD COLUMN date_only DATE GENERATED ALWAYS AS (date(timestamp)) STORED;
CREATE INDEX idx_scan_cycles_date ON scan_cycles(date_only);
```

### CODE-011: `data/` Directory Contains User Data
**Severity:** LOW  
**Status:** Open

`data/watchlist.json` may be user-edited. Document format or add to `.gitignore`.

**Files:** `data/watchlist.json`

### OPS-001: Railway Cron Schedule Assumes UTC
**Severity:** LOW  
**Status:** Open

`railway.toml:3` uses `"30 3 * * 1-5"` (03:30 UTC = 09:00 IST). Works while NSE doesn't observe DST. Document assumption.

**Files:** `railway.toml`

### OPS-002: Missing `__all__` Exports
**Severity:** LOW  
**Status:** Open

Several modules lack explicit `__all__`, risking accidental exports.

**Files:** `src/momentum/__init__.py` and submodules

---

## 📋 Additional Notes

### Potential Race Conditions
While current scan cycles are sequential, future async enhancements should review:
- `Deduplicator._state` mutations — add `asyncio.Lock` if parallel scans added
- `TradeJournal` DB connections — use `aiosqlite` for true async

### Unused / Dead Code
- Any remaining `import dhanhq` references? Grep verified none after removal.

### Security Hardening
- Install `pre-commit` with `gitleaks` to prevent future secret commits
- Consider `bandit` scan for security anti-patterns
- Enable `pandas` option `mode.chained_assignment = None` to catch SettingWithCopy warnings

---

## 🎯 Recommended Action Order

1. **This week:**
   - Pin all dependencies (SEC-003)
   - Add `.env.railway` to `.gitignore` (already done; commit)
   - Fix duration check logic reversed (LOGIC-001) — optional defer
   - Add connection pooling to `yahoo_provider` and `telegram_service` (PERF-001)

2. **This sprint:**
   - Persist deduplicator state to SQLite (DB-001)
   - Split `ScannerConfig` into sub-configs (ARCH-002)
   - Consolidate IST timezone constant (ARCH-006)
   - Add config cross-validation (CONFIG-003)
   - Add integration test (TEST-001)
   - Replace bare `except` with logging (CODE-001)

3. **Next quarter:**
   - Database migration system (DB-002)
   - Abstract `AlertService` interface (ARCH-004)
   - Externalize holiday list (ARCH-003)
   - Migrate to `aiosqlite` (DB-003)
   - Full security audit: `bandit -r src/`, `pip-audit`, `safety check`

---

*Generated by Kilo — 2026-05-15*
