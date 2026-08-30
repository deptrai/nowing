"""SequencerService orchestrator for multi-channel drip campaigns."""

from __future__ import annotations

import logging

from app.redis_client import get_redis_client
from app.services.billing_event_service import BillingEventService
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption
from app.services.sequencer.analytics import SequencerAnalyticsMixin
from app.services.sequencer.compliance import SequencerComplianceMixin
from app.services.sequencer.dispatch import SequencerDispatchMixin
from app.services.sequencer.enrollments import SequencerEnrollmentMixin
from app.services.sequencer.inbound import SequencerInboundMixin

logger = logging.getLogger(__name__)


class SequencerService(
    SequencerComplianceMixin,
    SequencerDispatchMixin,
    SequencerEnrollmentMixin,
    SequencerInboundMixin,
    SequencerAnalyticsMixin,
):
    """Orchestration service for automated multi-step sequences."""

    def __init__(self) -> None:
        self.encryption = VerifiedContactEncryption()
        self.billing_service = BillingEventService()

    def _get_redis(self):
        return get_redis_client()
