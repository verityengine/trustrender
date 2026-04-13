"""Source adapters for common billing platforms.

Convert raw API responses into the dict shape that
ingest_invoice() and validate_invoice() already understand.

Adapters are pure functions. No network, no filesystem,
no side effects. They do minimal structural transformation
and leave missing data missing — the validation pipeline
catches what's wrong.
"""

from .stripe import from_stripe
from .shopify import from_shopify

__all__ = ["from_stripe", "from_shopify"]
