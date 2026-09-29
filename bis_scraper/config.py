from __future__ import annotations

import os

DEFAULT_LISTING_URL = "https://standards.bis.gov.in/website/published-standards/published-standards-list?selectedType=7&totalRow=1"
ALLOWED_HOST = "standards.bis.gov.in"
DEFAULT_DELAY_SECONDS = 2.0
DEFAULT_TIMEOUT_SECONDS = 25
DETAIL_LINK_SELECTOR = os.environ.get("BIS_DETAIL_LINK_SELECTOR", 'a[href*="/standard-details?encryptedId="]')
USER_AGENT = os.environ.get("BIS_SCRAPER_USER_AGENT", "StandardLensMVP/0.1 (metadata-only; configure contact email)")
