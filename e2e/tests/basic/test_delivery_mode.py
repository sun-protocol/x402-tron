"""
E2E Tests: Delivery Mode

Tests for PAYMENT_ONLY mode endpoint.
"""

import pytest

from x402.types import (
    FeeInfo,
    PAYMENT_ONLY,
    PaymentRequirements,
    PaymentRequirementsExtra,
)

pytestmark = pytest.mark.e2e


class TestDeliveryMode:
    """Delivery mode endpoint tests"""

    # All tests removed - /protected-delivery endpoint and PAYMENT_AND_DELIVERY feature no longer supported
    pass
