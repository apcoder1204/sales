"""Thin async client for the self-hosted OpenWA WhatsApp gateway.

Confirmed against OpenWA 0.32.1's OpenAPI spec (/api/docs-json):
  GET  /api/sessions/{id}                        -> 200 {"status": "ready" | "qr_ready" | ...}
  POST /api/sessions/{id}/messages/send-document -> 201 on success
       body {chatId: "<digits>@c.us", base64, mimetype, filename, caption}
       409 = session not connected (engine exists but not `ready`)
       404 = session not found
       400 "Session ... is not active" = session never started / stopped
  Auth header: X-API-Key
"""
import base64
import logging

import httpx

from app.config import settings

logger = logging.getLogger("dukani.whatsapp")


class GatewayError(Exception):
    pass


class GatewayUnreachable(GatewayError):
    pass


class GatewayTimeout(GatewayError):
    pass


class GatewaySessionNotReady(GatewayError):
    pass


class GatewayRejected(GatewayError):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"OpenWA rejected the send: {status_code} {body[:300]}")
        self.status_code = status_code
        self.body = body


class WhatsAppGateway:
    def __init__(
        self, base_url: str, api_key: str, session_id: str, timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._session_id = session_id
        self._timeout = timeout
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers={"X-API-Key": self._api_key},
            timeout=self._timeout,
            transport=self._transport,
        )

    async def session_status(self) -> str:
        """OpenWA session status string; "unreachable" if the gateway cannot
        be reached or answers unexpectedly. Never raises."""
        try:
            async with self._client() as c:
                resp = await c.get(f"/sessions/{self._session_id}")
            if resp.status_code != 200:
                return "unreachable"
            return str(resp.json().get("status") or "unreachable")
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("OpenWA status check failed: %s", e)
            return "unreachable"

    async def send_document(self, phone: str, pdf: bytes, filename: str, caption: str) -> None:
        payload = {
            "chatId": f"{phone}@c.us",
            "base64": base64.b64encode(pdf).decode("ascii"),
            "mimetype": "application/pdf",
            "filename": filename,
            "caption": caption,
        }
        try:
            async with self._client() as c:
                resp = await c.post(
                    f"/sessions/{self._session_id}/messages/send-document", json=payload
                )
        except httpx.TimeoutException as e:
            raise GatewayTimeout(str(e)) from e
        except httpx.HTTPError as e:
            raise GatewayUnreachable(str(e)) from e
        if resp.is_success:
            return
        if resp.status_code in (404, 409) or (
            # A session that exists but was never started (or was stopped)
            # answers 400 "Session '<id>' is not active" rather than 409.
            resp.status_code == 400 and "not active" in resp.text
        ):
            raise GatewaySessionNotReady(resp.text[:300])
        raise GatewayRejected(resp.status_code, resp.text)


def get_whatsapp_gateway() -> WhatsAppGateway:
    return WhatsAppGateway(
        base_url=settings.OPENWA_BASE_URL,
        api_key=settings.OPENWA_API_KEY,
        session_id=settings.OPENWA_SESSION_ID,
        timeout=settings.OPENWA_TIMEOUT_SECONDS,
    )
