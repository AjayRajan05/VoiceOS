"""Tests for VoiceOS doctor and degradation tiers."""

import os

from core.doctor.degradation import DegradationTier, resolve_degradation_tier, tier_summary
from core.doctor.runner import format_doctor_report, run_doctor_checks


class TestDegradationTier:
    def test_full_hybrid(self):
        tier = resolve_degradation_tier(docker_available=True, redis_available=True, worker_count=2)
        assert tier == DegradationTier.FULL_HYBRID

    def test_docker_partial(self):
        tier = resolve_degradation_tier(docker_available=True, redis_available=True, worker_count=0)
        assert tier == DegradationTier.DOCKER_PARTIAL

    def test_docker_only(self):
        tier = resolve_degradation_tier(docker_available=True, redis_available=False)
        assert tier == DegradationTier.DOCKER_ONLY

    def test_local_only(self):
        tier = resolve_degradation_tier(docker_available=False, redis_available=False)
        assert tier == DegradationTier.LOCAL_ONLY

    def test_tier_summary_has_recommendations(self):
        summary = tier_summary(DegradationTier.LOCAL_ONLY)
        assert summary["tier"] == "local_only"
        assert len(summary["recommendations"]) >= 1


class TestDoctorRunner:
    def test_run_doctor_checks_structure(self, monkeypatch):
        monkeypatch.setenv("EXECUTION_MODE", "local")
        report = run_doctor_checks()
        assert "checks" in report
        assert "tier" in report
        assert "healthy" in report
        assert any(c["name"] == "python" for c in report["checks"])

    def test_format_report_includes_tier(self, monkeypatch):
        monkeypatch.setenv("EXECUTION_MODE", "local")
        text = format_doctor_report(run_doctor_checks())
        assert "VOICEOS DOCTOR" in text
        assert "Degradation tier:" in text
