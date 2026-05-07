# Tests for core/rate_limiter.py — Adaptive rate limiter with persistence.
#
# Covers:
# - RateLimiter.__init__(): defaults, custom params, persistence loading
# - RateLimiter.should_wait(): threshold logic, max_delay cap, base_delay
# - RateLimiter.record_error(): timestamp recording, persistence trigger
# - RateLimiter.record_success(): placeholder (no-op for now)
# - RateLimiter._persist_errors() / _load_persisted_errors(): JSON persistence
# - RateLimiter._cleanup_old_errors(): expiry of old timestamps
# - get_rate_limiter(): singleton, lazy init

import json
import time
from pathlib import Path

import pytest

# ─── RateLimiter.__init__ ─────────────────────────────────────────


class TestRateLimiterInit:
    """Tests for RateLimiter initialization."""

    def test_default_initialization(self):
        """RateLimiter initializes with sensible defaults."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter()
        assert rl.base_delay == 0.2
        assert rl.max_delay == 10.0
        assert rl.memory_minutes == 30
        assert rl.error_threshold == 1
        assert rl.persist_path is None
        assert rl._error_timestamps == []

    def test_custom_initialization(self, temp_dir):
        """RateLimiter accepts custom parameters."""
        from core.rate_limiter import RateLimiter

        path = str(temp_dir / "state.json")
        rl = RateLimiter(
            base_delay=0.5,
            max_delay=30.0,
            memory_minutes=60,
            error_threshold=3,
            persist_path=path,
        )
        assert rl.base_delay == 0.5
        assert rl.max_delay == 30.0
        assert rl.memory_minutes == 60
        assert rl.error_threshold == 3
        assert rl.persist_path == Path(path)

    def test_creates_empty_error_timestamps(self):
        """RateLimiter starts with no error timestamps."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter()
        assert isinstance(rl._error_timestamps, list)
        assert len(rl._error_timestamps) == 0

    def test_accepts_string_persist_path(self, temp_dir):
        """persist_path as a string is converted to Path."""
        from core.rate_limiter import RateLimiter

        path_str = str(temp_dir / "state.json")
        rl = RateLimiter(persist_path=path_str)
        assert isinstance(rl.persist_path, Path)
        assert str(rl.persist_path) == path_str

    def test_accepts_path_object_persist_path(self, temp_dir):
        """persist_path as a Path object is accepted."""
        from core.rate_limiter import RateLimiter

        path_obj = temp_dir / "state.json"
        rl = RateLimiter(persist_path=str(path_obj))
        assert rl.persist_path == path_obj

    def test_none_persist_path_means_no_persistence(self):
        """When persist_path is None, no persistence file is used."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(persist_path=None)
        assert rl.persist_path is None

    def test_loads_persisted_errors_on_init(self, temp_dir):
        """RateLimiter loads error timestamps from an existing persist file."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        now = time.time()
        timestamps = [now - 10, now - 5, now]
        state_file.write_text(
            json.dumps({"error_timestamps": timestamps}), encoding="utf-8"
        )

        rl = RateLimiter(persist_path=str(state_file))
        # Loaded timestamps should be present (within memory window)
        assert len(rl._error_timestamps) == 3

    def test_handles_missing_persisted_file_gracefully(self, temp_dir):
        """Missing persist file results in empty error timestamps."""
        from core.rate_limiter import RateLimiter

        path = str(temp_dir / "nonexistent.json")
        rl = RateLimiter(persist_path=path)
        assert rl._error_timestamps == []

    def test_handles_corrupt_persisted_file_gracefully(self, temp_dir):
        """Corrupt JSON in persist file results in empty error timestamps."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        state_file.write_text("NOT VALID JSON{{{{", encoding="utf-8")

        rl = RateLimiter(persist_path=str(state_file))
        assert rl._error_timestamps == []

    def test_handles_missing_timestamps_key_gracefully(self, temp_dir):
        """Persist file with missing 'error_timestamps' key defaults to empty."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        state_file.write_text(json.dumps({"other_key": 123}), encoding="utf-8")

        rl = RateLimiter(persist_path=str(state_file))
        assert rl._error_timestamps == []

    def test_cleans_up_old_errors_on_load(self, temp_dir):
        """Expired timestamps from persist file are removed on load."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        now = time.time()
        # One timestamp that's 31 minutes old (outside default 30-min window)
        # and one that's recent
        timestamps = [now - 31 * 60, now - 5]
        state_file.write_text(
            json.dumps({"error_timestamps": timestamps}), encoding="utf-8"
        )

        rl = RateLimiter(persist_path=str(state_file), memory_minutes=30)
        # Only the recent timestamp should survive
        assert len(rl._error_timestamps) == 1


# ─── RateLimiter.should_wait ──────────────────────────────────────


class TestRateLimiterShouldWait:
    """Tests for RateLimiter.should_wait() threshold and delay logic."""

    def test_no_errors_returns_false_and_base_delay(self):
        """With no errors, should_wait returns (False, base_delay)."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(base_delay=0.2, error_threshold=1)
        should_wait, delay = rl.should_wait()
        assert should_wait is False
        assert delay == pytest.approx(0.2)

    def test_below_threshold_returns_false_and_base_delay(self):
        """Below the error threshold, should_wait returns (False, base_delay)."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(base_delay=0.2, error_threshold=3)
        rl._error_timestamps = [time.time()]  # 1 error, threshold is 3
        should_wait, delay = rl.should_wait()
        assert should_wait is False
        assert delay == pytest.approx(0.2)

    def test_at_threshold_returns_true(self):
        """At the error threshold, should_wait returns True."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(base_delay=0.2, error_threshold=1)
        rl._error_timestamps = [time.time()]
        should_wait, delay = rl.should_wait()
        assert should_wait is True

    def test_threshold_1_first_error_triggers_wait(self):
        """With threshold=1 (reactive), a single error triggers waiting."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(base_delay=0.2, error_threshold=1)
        rl._error_timestamps = [time.time()]
        should_wait, delay = rl.should_wait()
        assert should_wait is True
        # multiplier = 2^(1-1) = 1, delay = 0.2 * 1 = 0.2
        assert delay == pytest.approx(0.2)

    def test_errors_beyond_threshold_increase_delay_exponentially(self):
        """Delay increases exponentially with errors beyond the threshold."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(base_delay=0.2, error_threshold=1)
        # 3 errors → multiplier = 2^(3-1) = 4, delay = 0.2 * 4 = 0.8
        now = time.time()
        rl._error_timestamps = [now - 2, now - 1, now]
        should_wait, delay = rl.should_wait()
        assert should_wait is True
        assert delay == pytest.approx(0.8)

    def test_many_errors_hit_max_delay(self):
        """Delay is capped at max_delay even with many errors."""
        from core.rate_limiter import RateLimiter

        # Use base_delay=1.0 so that multiplier 16 yields 16.0, capped at 10.0
        rl = RateLimiter(base_delay=1.0, max_delay=10.0, error_threshold=1)
        # 10 errors → multiplier = min(2^9, 16) = 16, delay = 1.0 * 16 = 16.0 → capped at 10.0
        now = time.time()
        rl._error_timestamps = [now - i for i in range(10)]
        should_wait, delay = rl.should_wait()
        assert should_wait is True
        assert delay == pytest.approx(10.0)

    def test_max_delay_is_respected(self):
        """Calculated delay never exceeds max_delay."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(base_delay=0.2, max_delay=2.0, error_threshold=1)
        now = time.time()
        # 5 errors → multiplier = 2^4 = 16, delay = 3.2 → capped at 2.0
        rl._error_timestamps = [now - i for i in range(5)]
        should_wait, delay = rl.should_wait()
        assert should_wait is True
        assert delay == pytest.approx(2.0)

    def test_old_errors_cleaned_up_before_check(self):
        """Errors older than memory_minutes are removed before checking threshold."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(base_delay=0.2, memory_minutes=5, error_threshold=1)
        # Add an error that's 10 minutes old (outside 5-minute window)
        rl._error_timestamps = [time.time() - 10 * 60]
        should_wait, delay = rl.should_wait()
        # Old error cleaned up → below threshold → no wait
        assert should_wait is False
        assert delay == pytest.approx(0.2)

    def test_mixed_old_and_recent_errors(self):
        """Only recent errors count toward the threshold."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(base_delay=0.2, memory_minutes=5, error_threshold=1)
        now = time.time()
        # One old error (outside window) and one recent
        rl._error_timestamps = [now - 10 * 60, now - 1]
        should_wait, delay = rl.should_wait()
        # Only the recent error counts → at threshold with threshold=1
        assert should_wait is True
        # multiplier = 2^(1-1) = 1, delay = 0.2
        assert delay == pytest.approx(0.2)

    def test_error_threshold_3_requires_three_errors(self):
        """With threshold=3, two errors don't trigger waiting but three do."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(base_delay=0.2, error_threshold=3)
        now = time.time()

        # Two errors: below threshold
        rl._error_timestamps = [now - 2, now - 1]
        should_wait, delay = rl.should_wait()
        assert should_wait is False
        assert delay == pytest.approx(0.2)

        # Three errors: at threshold
        rl._error_timestamps = [now - 2, now - 1, now]
        should_wait, delay = rl.should_wait()
        assert should_wait is True
        # multiplier = 2^(3-3) = 1, delay = 0.2
        assert delay == pytest.approx(0.2)

    def test_multiplier_capped_at_16(self):
        """The exponential multiplier is capped at 16."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(base_delay=0.2, max_delay=100.0, error_threshold=1)
        now = time.time()
        # 20 errors → multiplier would be 2^19 = 524288, but capped at 16
        # delay = 0.2 * 16 = 3.2
        rl._error_timestamps = [now - i for i in range(20)]
        should_wait, delay = rl.should_wait()
        assert should_wait is True
        assert delay == pytest.approx(3.2)


# ─── RateLimiter.record_error ─────────────────────────────────────


class TestRateLimiterRecordError:
    """Tests for RateLimiter.record_error()."""

    def test_records_error_timestamp(self):
        """record_error adds a timestamp to _error_timestamps."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter()
        assert len(rl._error_timestamps) == 0
        rl.record_error()
        assert len(rl._error_timestamps) == 1
        assert isinstance(rl._error_timestamps[0], float)

    def test_records_multiple_errors(self):
        """Multiple calls to record_error add multiple timestamps."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter()
        rl.record_error()
        rl.record_error()
        rl.record_error()
        assert len(rl._error_timestamps) == 3

    def test_timestamps_are_close_to_current_time(self):
        """Recorded timestamps are approximately the current time."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter()
        before = time.time()
        rl.record_error()
        after = time.time()
        assert before <= rl._error_timestamps[0] <= after

    def test_persists_on_record_when_path_set(self, temp_dir):
        """record_error persists state when persist_path is configured."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        rl = RateLimiter(persist_path=str(state_file))
        rl.record_error()

        # File should exist and contain the timestamp
        assert state_file.exists()
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert "error_timestamps" in data
        assert len(data["error_timestamps"]) == 1

    def test_does_not_persist_when_no_path(self):
        """record_error does not attempt file I/O when persist_path is None."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(persist_path=None)
        # Should not raise an error
        rl.record_error()
        assert len(rl._error_timestamps) == 1

    def test_record_error_affects_should_wait(self):
        """After recording an error, should_wait reflects the new state."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(base_delay=0.2, error_threshold=1)
        should_wait, _ = rl.should_wait()
        assert should_wait is False

        rl.record_error()
        should_wait, delay = rl.should_wait()
        assert should_wait is True
        assert delay == pytest.approx(0.2)


# ─── RateLimiter.record_success ────────────────────────────────────


class TestRateLimiterRecordSuccess:
    """Tests for RateLimiter.record_success() — currently a no-op placeholder."""

    def test_record_success_does_not_raise(self):
        """record_success is callable and does not raise."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter()
        rl.record_success()  # Should not raise

    def test_record_success_does_not_modify_timestamps(self):
        """record_success does not change error timestamps."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter()
        rl.record_error()
        count_before = len(rl._error_timestamps)
        rl.record_success()
        assert len(rl._error_timestamps) == count_before


# ─── RateLimiter._persist_errors ──────────────────────────────────


class TestRateLimiterPersistErrors:
    """Tests for RateLimiter._persist_errors()."""

    def test_creates_file_on_persist(self, temp_dir):
        """_persist_errors creates a JSON file."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        rl = RateLimiter(persist_path=str(state_file))
        rl.record_error()
        assert state_file.exists()

    def test_writes_valid_json(self, temp_dir):
        """Persisted file contains valid JSON with error_timestamps key."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        rl = RateLimiter(persist_path=str(state_file))
        rl.record_error()
        rl.record_error()

        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert "error_timestamps" in data
        assert len(data["error_timestamps"]) == 2

    def test_noop_when_no_persist_path(self):
        """_persist_errors does nothing when persist_path is None."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(persist_path=None)
        rl.record_error()
        # Should not raise, no file written (nothing to assert on filesystem)

    def test_creates_parent_directories(self, temp_dir):
        """_persist_errors creates parent directories if they don't exist."""
        from core.rate_limiter import RateLimiter

        nested_path = temp_dir / "subdir" / "deep" / "state.json"
        rl = RateLimiter(persist_path=str(nested_path))
        rl.record_error()
        assert nested_path.exists()

    def test_overwrites_existing_file(self, temp_dir):
        """_persist_errors overwrites the file with current state."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        rl = RateLimiter(persist_path=str(state_file))

        # First persist
        rl.record_error()
        data1 = json.loads(state_file.read_text(encoding="utf-8"))
        assert len(data1["error_timestamps"]) == 1

        # Second persist adds another error
        rl.record_error()
        data2 = json.loads(state_file.read_text(encoding="utf-8"))
        assert len(data2["error_timestamps"]) == 2

    def test_handles_write_error_gracefully(self, temp_dir):
        """_persist_errors logs a warning on write failure but does not raise."""
        from core.rate_limiter import RateLimiter

        # Use a path where the parent directory cannot be created
        # (e.g., root-level path that requires permissions)
        rl = RateLimiter(persist_path="/nonexistent_root_dir/state.json")
        # Should not raise, just log a warning
        rl.record_error()


# ─── RateLimiter._load_persisted_errors ───────────────────────────


class TestRateLimiterLoadPersistedErrors:
    """Tests for RateLimiter._load_persisted_errors()."""

    def test_loads_timestamps_from_valid_file(self, temp_dir):
        """Loads error timestamps from a valid JSON file."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        now = time.time()
        timestamps = [now - 60, now - 30, now]
        state_file.write_text(
            json.dumps({"error_timestamps": timestamps}), encoding="utf-8"
        )

        rl = RateLimiter(persist_path=str(state_file))
        assert len(rl._error_timestamps) == 3
        assert rl._error_timestamps == timestamps

    def test_handles_missing_file_gracefully(self, temp_dir):
        """Missing persist file results in empty timestamps."""
        from core.rate_limiter import RateLimiter

        path = str(temp_dir / "nonexistent.json")
        rl = RateLimiter(persist_path=path)
        assert rl._error_timestamps == []

    def test_handles_invalid_json_gracefully(self, temp_dir):
        """Invalid JSON in persist file results in empty timestamps."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        state_file.write_text("}invalid json{", encoding="utf-8")

        rl = RateLimiter(persist_path=str(state_file))
        assert rl._error_timestamps == []

    def test_cleans_up_old_errors_on_load(self, temp_dir):
        """Expired timestamps are removed during load."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        now = time.time()
        # 2 old timestamps (60 min ago) and 1 recent (1 min ago)
        timestamps = [now - 60 * 60, now - 60 * 60, now - 60]
        state_file.write_text(
            json.dumps({"error_timestamps": timestamps}), encoding="utf-8"
        )

        rl = RateLimiter(persist_path=str(state_file), memory_minutes=30)
        # Only the recent timestamp should survive
        assert len(rl._error_timestamps) == 1

    def test_noop_when_no_persist_path(self):
        """_load_persisted_errors does nothing when persist_path is None."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(persist_path=None)
        assert rl._error_timestamps == []

    def test_preserves_recent_errors_on_load(self, temp_dir):
        """Recent timestamps are preserved during load."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        now = time.time()
        timestamps = [now - 60, now - 30, now - 5]
        state_file.write_text(
            json.dumps({"error_timestamps": timestamps}), encoding="utf-8"
        )

        rl = RateLimiter(persist_path=str(state_file), memory_minutes=30)
        assert len(rl._error_timestamps) == 3


# ─── RateLimiter._cleanup_old_errors ──────────────────────────────


class TestRateLimiterCleanupOldErrors:
    """Tests for RateLimiter._cleanup_old_errors()."""

    def test_removes_old_errors(self):
        """Timestamps older than memory_minutes are removed."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(memory_minutes=5)
        now = time.time()
        rl._error_timestamps = [now - 10 * 60, now - 6 * 60, now - 60]
        rl._cleanup_old_errors()
        assert len(rl._error_timestamps) == 1
        assert rl._error_timestamps[0] == pytest.approx(now - 60, abs=1)

    def test_keeps_recent_errors(self):
        """Timestamps within memory_minutes are preserved."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(memory_minutes=10)
        now = time.time()
        rl._error_timestamps = [now - 5 * 60, now - 60, now]
        rl._cleanup_old_errors()
        assert len(rl._error_timestamps) == 3

    def test_empty_list_stays_empty(self):
        """_cleanup_old_errors on empty list is a no-op."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter()
        rl._cleanup_old_errors()
        assert rl._error_timestamps == []

    def test_all_errors_expired_results_in_empty_list(self):
        """When all errors are expired, the list becomes empty."""
        from core.rate_limiter import RateLimiter

        rl = RateLimiter(memory_minutes=1)
        now = time.time()
        rl._error_timestamps = [now - 120, now - 90]
        rl._cleanup_old_errors()
        assert rl._error_timestamps == []


# ─── get_rate_limiter ──────────────────────────────────────────────


class TestGetRateLimiter:
    """Tests for get_rate_limiter() singleton behavior."""

    def test_returns_rate_limiter_instance(self):
        """get_rate_limiter() returns a RateLimiter instance."""
        from core.rate_limiter import RateLimiter, get_rate_limiter

        rl = get_rate_limiter()
        assert isinstance(rl, RateLimiter)

    def test_singleton_returns_same_instance(self):
        """Repeated calls to get_rate_limiter() return the same instance."""
        from core.rate_limiter import get_rate_limiter

        rl1 = get_rate_limiter()
        rl2 = get_rate_limiter()
        assert rl1 is rl2

    def test_uses_custom_path_when_provided(self, temp_dir):
        """get_rate_limiter() uses the provided path on first call."""
        import core.rate_limiter as rl_module
        from core.rate_limiter import get_rate_limiter

        # Reset singleton
        rl_module._global_rate_limiter = None

        custom_path = str(temp_dir / "custom_state.json")
        rl = get_rate_limiter(persist_path=custom_path)
        assert str(rl.persist_path) == custom_path

        # Clean up
        rl_module._global_rate_limiter = None

    def test_ignores_path_on_subsequent_calls(self, temp_dir):
        """get_rate_limiter() ignores persist_path on subsequent calls."""
        import core.rate_limiter as rl_module
        from core.rate_limiter import get_rate_limiter

        # Reset singleton
        rl_module._global_rate_limiter = None

        rl1 = get_rate_limiter(persist_path=str(temp_dir / "first.json"))
        rl2 = get_rate_limiter(persist_path=str(temp_dir / "second.json"))
        assert rl1 is rl2
        # Path should still be the first one
        assert "first.json" in str(rl2.persist_path)

        # Clean up
        rl_module._global_rate_limiter = None

    def test_default_path_from_config(self, temp_dir):
        """get_rate_limiter() with no args uses path from config."""
        import core.rate_limiter as rl_module
        from core.rate_limiter import get_rate_limiter

        rl_module._global_rate_limiter = None

        rl = get_rate_limiter()
        # Default path should come from config.RATE_LIMITER_STATE_PATH
        assert rl.persist_path is not None
        assert "rate_limiter_state.json" in str(rl.persist_path)

        # Clean up
        rl_module._global_rate_limiter = None


# ─── Persistence round-trip ────────────────────────────────────────


class TestRateLimiterPersistenceRoundTrip:
    """Integration tests for persist → load cycle."""

    def test_persist_and_reload_preserves_state(self, temp_dir):
        """State persists across RateLimiter instances (simulating restart)."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"

        # First instance: record errors and persist
        rl1 = RateLimiter(persist_path=str(state_file))
        rl1.record_error()
        rl1.record_error()
        assert len(rl1._error_timestamps) == 2

        # Second instance: should load persisted state
        rl2 = RateLimiter(persist_path=str(state_file))
        assert len(rl2._error_timestamps) == 2
        assert rl2._error_timestamps == rl1._error_timestamps

    def test_should_wait_uses_loaded_state(self, temp_dir):
        """should_wait() correctly uses errors loaded from persist file."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        now = time.time()

        # Create a persist file with 2 recent errors
        state_file.write_text(
            json.dumps({"error_timestamps": [now - 10, now - 5]}),
            encoding="utf-8",
        )

        # New instance loads persisted errors
        rl = RateLimiter(
            base_delay=0.2,
            max_delay=10.0,
            error_threshold=1,
            persist_path=str(state_file),
        )

        should_wait, delay = rl.should_wait()
        assert should_wait is True
        # 2 errors → multiplier = 2^(2-1) = 2, delay = 0.2 * 2 = 0.4
        assert delay == pytest.approx(0.4)

    def test_cleanup_then_persist_removes_old_errors(self, temp_dir):
        """After cleanup removes old errors, persist saves the cleaned state."""
        from core.rate_limiter import RateLimiter

        state_file = temp_dir / "state.json"
        now = time.time()

        # Create a persist file with 1 old and 1 recent error
        state_file.write_text(
            json.dumps({"error_timestamps": [now - 60 * 60, now - 5]}),
            encoding="utf-8",
        )

        # Load with short memory — old error should be cleaned up
        rl = RateLimiter(
            persist_path=str(state_file),
            memory_minutes=5,
        )
        assert len(rl._error_timestamps) == 1

        # Record another error to trigger persist
        rl.record_error()
        # Now there should be 2 timestamps (1 recent from file + 1 new)
        assert len(rl._error_timestamps) == 2

        # Reload from file — should have 2 recent timestamps
        rl2 = RateLimiter(persist_path=str(state_file), memory_minutes=5)
        assert len(rl2._error_timestamps) == 2
