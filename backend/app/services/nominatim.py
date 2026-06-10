import asyncio
import logging
import time
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class NominatimService:
    BASE_URL = "https://nominatim.openstreetmap.org"

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={
                "User-Agent": "AvanaSafetyApp/2.0 (karnataka-safety-app@example.com)",
                "Accept": "application/json",
            },
        )
        self._last_request_time = 0.0

    async def _rate_limit(self):
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        self._last_request_time = time.monotonic()

    async def geocode(self, query: str) -> Optional[dict]:
        if not query or not query.strip():
            return None
        await self._rate_limit()
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/search",
                params={"q": query, "format": "json", "limit": 1, "addressdetails": 1},
            )
            response.raise_for_status()
            data = response.json()
            if data and len(data) > 0:
                result = data[0]
                return {
                    "lat": float(result.get("lat", 0)),
                    "lng": float(result.get("lon", 0)),
                    "display_name": result.get("display_name", ""),
                    "place_id": result.get("place_id", ""),
                    "osm_type": result.get("osm_type", ""),
                    "osm_id": result.get("osm_id", ""),
                    "category": result.get("category", ""),
                    "type": result.get("type", ""),
                    "importance": result.get("importance", 0),
                }
            logger.info(f"No geocoding results for: {query}")
            return None
        except httpx.TimeoutException:
            logger.warning(f"Geocoding timeout for: {query}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Geocoding HTTP error for '{query}': {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Geocoding error for '{query}': {e}")
            return None

    async def reverse_geocode(self, lat: float, lng: float) -> Optional[dict]:
        await self._rate_limit()
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/reverse",
                params={"lat": lat, "lon": lng, "format": "json", "addressdetails": 1},
            )
            response.raise_for_status()
            data = response.json()
            if data:
                return {
                    "lat": float(data.get("lat", 0)),
                    "lng": float(data.get("lon", 0)),
                    "display_name": data.get("display_name", ""),
                    "place_id": data.get("place_id", ""),
                    "osm_type": data.get("osm_type", ""),
                    "osm_id": data.get("osm_id", ""),
                    "address": data.get("address", {}),
                }
            return None
        except httpx.TimeoutException:
            logger.warning(f"Reverse geocoding timeout for ({lat}, {lng})")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Reverse geocoding HTTP error ({lat}, {lng}): {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Reverse geocoding error for ({lat}, {lng}): {e}")
            return None

    async def search_structured(
        self,
        street: Optional[str] = None,
        city: Optional[str] = None,
        district: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Optional[dict]:
        await self._rate_limit()
        params = {"format": "json", "limit": 1, "addressdetails": 1, "country": "India"}
        if street:
            params["street"] = street
        if city:
            params["city"] = city
        if district:
            params["county"] = district
        if state:
            params["state"] = state
        try:
            response = await self.client.get(f"{self.BASE_URL}/search", params=params)
            response.raise_for_status()
            data = response.json()
            if data and len(data) > 0:
                result = data[0]
                return {
                    "lat": float(result.get("lat", 0)),
                    "lng": float(result.get("lon", 0)),
                    "display_name": result.get("display_name", ""),
                    "place_id": result.get("place_id", ""),
                    "osm_type": result.get("osm_type", ""),
                    "osm_id": result.get("osm_id", ""),
                }
            return None
        except httpx.TimeoutException:
            logger.warning(f"Structured search timeout: {street}, {city}, {district}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Structured search HTTP error: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Structured search error: {e}")
            return None

    async def aclose(self):
        await self.client.aclose()
