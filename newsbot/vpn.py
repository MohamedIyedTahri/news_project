"""vpn.py

Placeholder abstraction for VPN / IP rotation integration.

This module **does not implement actual VPN logic**. Instead it provides a
clean interface the scraper can call when it detects repeated blocking (e.g.
HTTP 403 from paywalled or protected sources like major newspapers).

Integration Strategy (to be implemented externally):
  * System-level VPN CLI (e.g., mullvad, nordvpn) invoked via subprocess.
  * Cloud proxy gateway API call that assigns a fresh exit IP.
  * Residential proxy rotation service.

Safety & Ethics:
  * Always respect robots.txt, site Terms of Service and local laws.
  * Do not use aggressive rotation to circumvent legitimate paywalls.
  * Limit frequency of rotation to avoid suspicious patterns.

Public API:
  rotate_vpn(reason: str) -> bool
      Attempts to rotate / switch the external IP. Returns True if an
      operation was triggered (not necessarily that IP changed), False if
      rotation is rate-limited or skipped.

  can_rotate() -> bool
      Indicates whether sufficient cooldown time has elapsed since the last
      rotation attempt.
"""
from __future__ import annotations

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Minimal in-memory state for cooldown tracking
_LAST_ROTATION_TS: float = 0.0
_COOLDOWN_SECONDS = 60  # prevent excessive rotation attempts


def can_rotate() -> bool:
    """Return True if we are allowed to attempt a rotation now."""
    global _LAST_ROTATION_TS
    return (time.time() - _LAST_ROTATION_TS) >= _COOLDOWN_SECONDS


def rotate_vpn(reason: str = "block_detected", executor: Optional[callable] = None) -> bool:
    """Attempt a VPN / IP rotation.

    Args:
        reason: Context string explaining why rotation was requested.
        executor: Optional callable performing the actual rotation. If not
                  provided, a placeholder log entry is created.

    Returns:
        bool: True if a rotation was initiated (or simulated), False if skipped.
    """
    global _LAST_ROTATION_TS

    if not can_rotate():
        logger.info("VPN rotation skipped due to cooldown")
        return False

    _LAST_ROTATION_TS = time.time()
    if executor:
        try:
            executor()  # real implementation provided by integrator
            logger.info(f"VPN rotation executed via custom executor (reason={reason})")
            return True
        except Exception as e:
            logger.error(f"VPN rotation executor failed: {e}")
            return False
    else:
        # Placeholder simulation
        logger.info(f"[SIMULATED] VPN rotation requested (reason={reason})")
        return True

__all__ = ["rotate_vpn", "can_rotate"]
