"""
Shared AsyncTron client factory.

Centralizes tronpy AsyncTron initialization with TronGrid API key support.
"""

import logging
import os
from typing import Any

from tronpy import AsyncTron
from tronpy.defaults import conf_for_name
from tronpy.providers.async_http import AsyncHTTPProvider

logger = logging.getLogger(__name__)


def create_async_tron_client(network: str) -> Any:
    """Create an AsyncTron client for the given network.

    Automatically uses TronGrid API key from TRON_GRID_API_KEY env var if set.

    Args:
        network: TRON network name (mainnet/shasta/nile)

    Returns:
        tronpy.AsyncTron instance
    """
    api_key = os.getenv("TRON_GRID_API_KEY")
    if not api_key:
        logger.warning(
            "TRON_GRID_API_KEY is not set. Mainnet requests may be rate-limited or fail; "
            "set TRON_GRID_API_KEY in your environment/.env to use TronGrid reliably."
        )

        logger.info("Creating AsyncTron client for network=%s", network)
        return AsyncTron(network=network)

    conf = conf_for_name(network)
    if not conf:
        raise ValueError(
            f"Unknown TRON network '{network}'. Expected one of: mainnet, nile, shasta."
        )

    endpoint_uri = conf["fullnode"]
    provider = AsyncHTTPProvider(endpoint_uri=endpoint_uri, api_key=api_key)
    logger.info(
        "Creating AsyncTron client with TronGrid API key for network=%s (%s)",
        network,
        endpoint_uri,
    )
    return AsyncTron(provider=provider, network=network)
