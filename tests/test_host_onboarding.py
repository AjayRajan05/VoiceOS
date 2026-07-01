"""Tests for host control plane onboarding (Phase B)."""

from core.doctor.degradation import DegradationTier
from core.host.onboarding import (
    ensure_host_environment,
    preflight_hybrid,
    run_first_time_setup,
)


class TestEnsureHostEnvironment:
    def test_creates_workspace_dirs(self, tmp_path):
        summary = ensure_host_environment(tmp_path)
        assert (tmp_path / "workspace").is_dir()
        assert (tmp_path / "logs").is_dir()
        assert "project_root" in summary

    def test_creates_env_from_example(self, tmp_path):
        (tmp_path / ".env.example").write_text("EXECUTION_MODE=auto\n", encoding="utf-8")
        summary = ensure_host_environment(tmp_path)
        assert summary["env_created"] is True
        assert (tmp_path / ".env").exists()


class TestPreflightHybrid:
    def test_preflight_returns_report(self, monkeypatch):
        monkeypatch.setenv("EXECUTION_MODE", "local")
        ok, report = preflight_hybrid()
        assert isinstance(report, dict)
        assert "tier" in report
        assert isinstance(ok, bool)

    def test_require_full_hybrid_strict(self, monkeypatch):
        monkeypatch.setenv("EXECUTION_MODE", "local")
        ok, report = preflight_hybrid(require_full=True)
        tier = report["tier"]["tier"]
        if tier != DegradationTier.FULL_HYBRID.value:
            assert ok is False


class TestRunFirstTimeSetup:
    def test_setup_includes_doctor(self, tmp_path):
        (tmp_path / ".env.example").write_text("EXECUTION_MODE=auto\n", encoding="utf-8")
        summary = run_first_time_setup(tmp_path)
        assert "doctor" in summary
        assert "tier" in summary
