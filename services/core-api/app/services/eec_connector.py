"""
HTTP connector for the EEC OData API (portal.eaeunion.org).

Handles pagination, X-RequestDigest token management for POST requests,
retry logic with exponential backoff, and response parsing.
"""
import time
from datetime import date
from typing import Optional

import httpx
import structlog

from .eec_classifier_config import EEC_PORTAL_BASE_URL, EEC_PORTAL_CONTEXT_URL

logger = structlog.get_logger()

ACCEPT_JSON = "application/json;odata=verbose"
PAGE_SIZE = 100
MAX_RETRIES = 3


class EecODataConnector:
    """Async HTTP client for portal.eaeunion.org OData API."""

    def __init__(self, base_url: str = EEC_PORTAL_BASE_URL, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._context_url = EEC_PORTAL_CONTEXT_URL
        self._timeout = timeout
        self._digest: Optional[str] = None
        self._digest_expiry: float = 0

    async def get_items(
        self,
        guid: str,
        select_fields: Optional[list[str]] = None,
    ) -> list[dict]:
        """Fetch all items from a classifier list using GET with pagination.

        No auth required for GET requests.
        """
        params = f"$top={PAGE_SIZE}"
        if select_fields:
            params += f"&$select={','.join(select_fields)}"

        url: Optional[str] = f"{self._base_url}(guid'{guid}')/Items?{params}"
        all_items: list[dict] = []

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            while url:
                data = await self._request_with_retry(client, "GET", url)
                results = data.get("d", {}).get("results", [])
                all_items.extend(results)
                url = data.get("d", {}).get("__next")

        logger.info("eec_get_items", guid=guid, total=len(all_items))
        return all_items

    async def get_items_modified_since(
        self,
        guid: str,
        since: date,
    ) -> list[dict]:
        """Fetch items modified since a given date using POST with CAML filter.

        Requires X-RequestDigest token. The CAML query is passed as a URL
        parameter (not as a JSON body) per the SharePoint REST API convention.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            digest = await self._ensure_digest(client)

            since_str = since.isoformat()
            caml_query = (
                '<View><Query><Where>'
                '<Geq><FieldRef Name="ModificationDate"/>'
                f'<Value Type="DateTime">{since_str}</Value>'
                '</Geq></Where></Query></View>'
            )
            import urllib.parse
            encoded_v1 = urllib.parse.quote(
                f"{{'ViewXml':'{caml_query}'}}", safe=""
            )

            url = (
                f"{self._base_url}(guid'{guid}')"
                f"/GetItems(query=@v1)?@v1={encoded_v1}"
            )

            all_items: list[dict] = []
            data = await self._request_with_retry(
                client, "POST", url,
                headers={"X-RequestDigest": digest},
            )
            results = data.get("d", {}).get("results", [])
            all_items.extend(results)

        logger.info(
            "eec_get_modified",
            guid=guid, since=since_str, total=len(all_items),
        )
        return all_items

    async def get_fields(self, guid: str) -> list[dict]:
        """Retrieve field definitions for a classifier (useful for debugging)."""
        url = f"{self._base_url}(guid'{guid}')/Fields"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            data = await self._request_with_retry(client, "GET", url)
        return data.get("d", {}).get("results", [])

    async def _ensure_digest(self, client: httpx.AsyncClient) -> str:
        """Obtain or reuse the X-RequestDigest token (valid for 30 min)."""
        if self._digest and time.time() < self._digest_expiry:
            return self._digest

        resp = await client.post(
            self._context_url,
            headers={"Accept": ACCEPT_JSON},
        )
        resp.raise_for_status()
        info = resp.json()["d"]["GetContextWebInformation"]
        self._digest = info["FormDigestValue"]
        ttl = info.get("FormDigestTimeoutSeconds", 1800)
        self._digest_expiry = time.time() + ttl - 60
        logger.debug("eec_digest_refreshed", ttl=ttl)
        return self._digest

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> dict:
        """Execute an HTTP request with retry logic and exponential backoff."""
        hdrs = {"Accept": ACCEPT_JSON}
        if headers:
            hdrs.update(headers)

        import asyncio

        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                if method == "GET":
                    resp = await client.get(url, headers=hdrs)
                else:
                    resp = await client.post(url, headers=hdrs, json=json_body)

                if resp.status_code == 403 and attempt < MAX_RETRIES - 1:
                    logger.warning("eec_digest_expired, refreshing")
                    self._digest = None
                    self._digest_expiry = 0
                    new_digest = await self._ensure_digest(client)
                    hdrs["X-RequestDigest"] = new_digest
                    continue

                if resp.status_code in (500, 503) and attempt < MAX_RETRIES - 1:
                    delay = 2 ** attempt
                    logger.warning("eec_server_error", status=resp.status_code, retry_in=delay)
                    await asyncio.sleep(delay)
                    continue

                resp.raise_for_status()
                return resp.json()

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    delay = 2 ** attempt
                    logger.warning("eec_http_error", status=exc.response.status_code, retry_in=delay)
                    await asyncio.sleep(delay)
                else:
                    raise
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    delay = 2 ** attempt
                    logger.warning("eec_connection_error", error=str(exc), retry_in=delay)
                    await asyncio.sleep(delay)
                else:
                    raise

        raise last_exc  # type: ignore[misc]
