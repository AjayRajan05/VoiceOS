"""Graceful degradation tiers for VoiceOS hybrid execution."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List


class DegradationTier(str, Enum):
    """How much of the hybrid Docker stack is available."""

    FULL_HYBRID = "full_hybrid"
    DOCKER_PARTIAL = "docker_partial"
    DOCKER_ONLY = "docker_only"
    LOCAL_ONLY = "local_only"


TIER_LABELS: Dict[DegradationTier, str] = {
    DegradationTier.FULL_HYBRID: "Full hybrid - voice/OS on host, heavy work in Docker workers",
    DegradationTier.DOCKER_PARTIAL: "Partial hybrid - Redis is up but no workers registered",
    DegradationTier.DOCKER_ONLY: "Docker available - start Redis/workers for offload",
    DegradationTier.LOCAL_ONLY: "Local only - all tasks run on this machine",
}


TIER_RECOMMENDATIONS: Dict[DegradationTier, List[str]] = {
    DegradationTier.FULL_HYBRID: [
        "You are on the recommended setup. Run: python main.py --mode hybrid",
    ],
    DegradationTier.DOCKER_PARTIAL: [
        "Start workers: docker compose --profile workers up -d --scale voiceos-worker=2",
        "Or run: .\\scripts\\start_hybrid.ps1  /  ./scripts/start_hybrid.sh",
    ],
    DegradationTier.DOCKER_ONLY: [
        "Start infra: docker compose --profile core --profile workers up -d",
        "Without Redis, heavy tasks use host CPU.",
    ],
    DegradationTier.LOCAL_ONLY: [
        "Install Docker Desktop and run: .\\scripts\\start_hybrid.ps1",
        "CLI-only fallback: python main.py --mode cli",
    ],
}


def resolve_degradation_tier(
    *,
    docker_available: bool,
    redis_available: bool,
    worker_count: int = 0,
) -> DegradationTier:
    if docker_available and redis_available and worker_count > 0:
        return DegradationTier.FULL_HYBRID
    if docker_available and redis_available:
        return DegradationTier.DOCKER_PARTIAL
    if docker_available:
        return DegradationTier.DOCKER_ONLY
    return DegradationTier.LOCAL_ONLY


def tier_summary(tier: DegradationTier) -> Dict[str, Any]:
    return {
        "tier": tier.value,
        "label": TIER_LABELS[tier],
        "recommendations": list(TIER_RECOMMENDATIONS[tier]),
    }
