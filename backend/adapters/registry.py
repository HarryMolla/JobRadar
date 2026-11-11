"""
Adapter registry.
Central place to register and instantiate all adapters.
Supports enable/disable per adapter and custom config injection.
"""
from __future__ import annotations

import logging
import yaml
from pathlib import Path
from typing import Optional

from backend.adapters.base import BaseAdapter
from backend.adapters.himalayas import HimalayasAdapter
from backend.adapters.remoteok import RemoteOKAdapter
from backend.adapters.remotive import RemotiveAdapter
from backend.adapters.weworkremotely import WeWorkRemotelyAdapter
from backend.adapters.jobicy import JobicyAdapter
from backend.adapters.workingnomads import WorkingNomadsAdapter
from backend.adapters.greenhouse import GreenhouseAdapter
from backend.adapters.lever import LeverAdapter
from backend.adapters.ashby import AshbyAdapter
from backend.adapters.smartrecruiters import SmartRecruitersAdapter
from backend.adapters.workable import WorkableAdapter
from backend.adapters.wellfound import WellfoundAdapter
from backend.adapters.dynamitejobs import DynamiteJobsAdapter
from backend.adapters.ycombinator import YCombinatorAdapter
from backend.adapters.recruitee import RecruiteeAdapter
from backend.adapters.rss_feeds import RSSFeedsAdapter
from backend.adapters.personio import PersonioAdapter
from backend.adapters.workday import WorkdayAdapter
from backend.adapters.email_alerts import EmailAlertsAdapter
from backend.adapters.sawatech import SawaTechAdapter
from backend.adapters.prism_digital import PrismDigitalAdapter
from backend.adapters.hays_uae import HaysUAEAdapter

logger = logging.getLogger(__name__)

# All registered adapters — remote + UAE job source integrations
ALL_ADAPTERS: list[type[BaseAdapter]] = [
    RemoteOKAdapter,
    RemotiveAdapter,
    WeWorkRemotelyAdapter,
    JobicyAdapter,
    WorkingNomadsAdapter,
    HimalayasAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    AshbyAdapter,
    SmartRecruitersAdapter,
    WorkableAdapter,
    WellfoundAdapter,
    DynamiteJobsAdapter,
    YCombinatorAdapter,
    RecruiteeAdapter,
    PersonioAdapter,
    WorkdayAdapter,
    RSSFeedsAdapter,
    EmailAlertsAdapter,
    SawaTechAdapter,
    PrismDigitalAdapter,
    HaysUAEAdapter,
]


def load_sources_config() -> dict:
    """Load sources_config.yaml from the project root."""
    config_path = Path(__file__).parent.parent.parent / "sources_config.yaml"
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as exc:
            logger.error("Failed to load sources_config.yaml: %s", exc)
    return {}


def get_enabled_adapters(
    disabled_sources: Optional[list[str]] = None,
    sources_config: Optional[dict] = None,
) -> list[BaseAdapter]:
    """
    Instantiate and return all enabled adapters.

    Args:
        disabled_sources: List of SOURCE_IDs to skip.
        sources_config: Dict from sources_config.yaml (passed to each adapter).
    """
    if disabled_sources is None:
        disabled_sources = []
    if sources_config is None:
        sources_config = load_sources_config()

    adapters = []
    for adapter_cls in ALL_ADAPTERS:
        if adapter_cls.SOURCE_ID in disabled_sources:
            logger.info("Adapter %s is disabled by configuration", adapter_cls.SOURCE_ID)
            continue
        if not adapter_cls.ENABLED:
            logger.info("Adapter %s is disabled by default", adapter_cls.SOURCE_ID)
            continue
        try:
            instance = adapter_cls(config=sources_config)
            adapters.append(instance)
        except Exception as exc:
            logger.error("Failed to instantiate adapter %s: %s", adapter_cls.SOURCE_ID, exc)

    logger.info("Enabled adapters: %s", [a.SOURCE_ID for a in adapters])
    return adapters
