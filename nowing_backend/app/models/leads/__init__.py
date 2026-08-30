"""Leads domain models package."""

from __future__ import annotations

from .core import ChainLensIngestJob, DshMission, TelegramCheckpointMessage
from .enrichment import (
    CompanyDecisionMaker,
    CrmConnection,
    CrmSyncLog,
    EnrichmentRequest,
    LinkedinCompany,
    LinkedinJob,
    PhoneWaterfallLog,
    VerifiedContact,
)
from .main import (
    ExportJob,
    Lead,
    LeadActivityLog,
    LeadAssignment,
    LeadPipelineStage,
    LeadScore,
)
from .sequences import (
    Sequence,
    SequenceEnrollment,
    SequenceEvent,
    SequenceRun,
    SequenceStep,
)
from .signals import SignalEvent, SignalSubscription
from .social import (
    OutcomeEvent,
    SocialMonitoredTarget,
    SocialPost,
    ZaloConnection,
    ZaloMessageLog,
)

# Backwards-compatible alias for legacy naming.
OutboundMessage = ZaloMessageLog

__all__ = [
    "ChainLensIngestJob",
    "CompanyDecisionMaker",
    "CrmConnection",
    "CrmSyncLog",
    "DshMission",
    "EnrichmentRequest",
    "ExportJob",
    "Lead",
    "LeadActivityLog",
    "LeadAssignment",
    "LeadPipelineStage",
    "LeadScore",
    "LinkedinCompany",
    "LinkedinJob",
    "OutboundMessage",
    "OutcomeEvent",
    "PhoneWaterfallLog",
    "Sequence",
    "SequenceEnrollment",
    "SequenceEvent",
    "SequenceRun",
    "SequenceStep",
    "SignalEvent",
    "SignalSubscription",
    "SocialMonitoredTarget",
    "SocialPost",
    "TelegramCheckpointMessage",
    "VerifiedContact",
    "ZaloConnection",
    "ZaloMessageLog",
]
