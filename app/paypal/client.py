import time
from typing import Dict, Any, Optional
import httpx
from app.config import settings


class PayPalClient:
    def __init__(self):
        self.base_url = settings.paypal_base_url
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    async def get_access_token(self) -> str:
        """Retrieves or reuses an active OAuth 2.0 access token from PayPal Sandbox."""
        # Reuse token if valid for at least another 60 seconds
        if self._access_token and time.time() < (self._token_expires_at - 60):
            return self._access_token

        url = f"{self.base_url}/v1/oauth2/token"
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }
        data = {"grant_type": "client_credentials"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET),
                headers=headers,
                data=data,
                timeout=15.0,
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"PayPal OAuth token fetch failed ({response.status_code}): {response.text}"
            )

        payload = response.json()
        self._access_token = payload["access_token"]
        expires_in = payload.get("expires_in", 3600)
        self._token_expires_at = time.time() + expires_in

        return self._access_token

    async def request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Authenticated HTTP helper for PayPal API endpoints."""
        token = await self.get_access_token()
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient() as client:
            res = await client.request(
                method=method,
                url=url,
                headers=req_headers,
                json=json,
                timeout=20.0,
            )
            
            # 204 No Content handling
            if res.status_code == 204:
                return {}
                
            if res.status_code not in (200, 201, 202):
                raise RuntimeError(
                    f"PayPal API {method} {endpoint} failed ({res.status_code}): {res.text}"
                )
            return res.json()


paypal_client = PayPalClient()