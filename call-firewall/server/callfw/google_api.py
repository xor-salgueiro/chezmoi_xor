"""Google Contacts (People API) and Calendar free/busy via OAuth refresh token."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from .phone import normalize

log = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
PEOPLE_URL = "https://people.googleapis.com/v1/people/me/connections"
FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"
SCOPES = [
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


class Google:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, contacts_ttl_s: int = 1800):
        self._cid, self._secret, self._refresh = client_id, client_secret, refresh_token
        self._token: str | None = None
        self._token_exp = 0.0
        self._contacts: dict[str, str] = {}  # E.164 -> display name
        self._contacts_at = 0.0
        self._ttl = contacts_ttl_s
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self._cid and self._secret and self._refresh)

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        r = await client.post(TOKEN_URL, data={
            "client_id": self._cid, "client_secret": self._secret,
            "refresh_token": self._refresh, "grant_type": "refresh_token",
        })
        r.raise_for_status()
        body = r.json()
        self._token, self._token_exp = body["access_token"], time.time() + body.get("expires_in", 3600)
        return self._token

    async def contacts(self, default_region: str = "ES") -> dict[str, str]:
        if not self.enabled:
            return {}
        async with self._lock:
            if time.time() - self._contacts_at < self._ttl:
                return self._contacts
            try:
                self._contacts = await self._fetch_contacts(default_region)
                self._contacts_at = time.time()
            except httpx.HTTPError as exc:  # keep last good copy
                log.warning("contacts refresh failed: %s", exc)
            return self._contacts

    async def _fetch_contacts(self, default_region: str) -> dict[str, str]:
        result: dict[str, str] = {}
        async with httpx.AsyncClient(timeout=10) as client:
            token = await self._access_token(client)
            page_token = None
            while True:
                params = {"personFields": "names,phoneNumbers", "pageSize": 1000}
                if page_token:
                    params["pageToken"] = page_token
                r = await client.get(PEOPLE_URL, params=params, headers={"Authorization": f"Bearer {token}"})
                r.raise_for_status()
                body = r.json()
                for person in body.get("connections", []):
                    name = (person.get("names") or [{}])[0].get("displayName", "")
                    for ph in person.get("phoneNumbers", []):
                        number = normalize(ph.get("canonicalForm") or ph.get("value"), default_region)
                        if number:
                            result[number] = name
                page_token = body.get("nextPageToken")
                if not page_token:
                    return result

    async def is_busy_now(self) -> bool:
        """True when the primary calendar has a busy block covering now. Fails open (False)."""
        if not self.enabled:
            return False
        now = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                token = await self._access_token(client)
                r = await client.post(FREEBUSY_URL, headers={"Authorization": f"Bearer {token}"}, json={
                    "timeMin": now.isoformat(), "timeMax": (now + timedelta(minutes=1)).isoformat(),
                    "items": [{"id": "primary"}],
                })
                r.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("freebusy failed: %s", exc)
            return False
        return bool(r.json().get("calendars", {}).get("primary", {}).get("busy"))
