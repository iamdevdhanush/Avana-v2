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
                "User-Agent": "Avana/2.0 (Safety Intelligence Platform; +https://avana.app; contact@avana.app)",
                "Referer": "https://avana.app/",
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
        last_exc = None
        for attempt in range(1, 4):
            try:
                await self._rate_limit()
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
            except httpx.TimeoutException as e:
                last_exc = e
                if attempt < 3:
                    delay = 1.0 * (2 ** (attempt - 1))
                    logger.warning(f"Nominatim timeout (attempt {attempt}/3): {query}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.warning(f"Nominatim timeout after 3 attempts: {query}")
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 403, 503, 502) and attempt < 3:
                    delay = 1.0 * (2 ** (attempt - 1))
                    logger.warning(f"Nominatim HTTP {e.response.status_code} (attempt {attempt}/3): {query}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"Geocoding HTTP error for '{query}': {e.response.status_code}")
                return None
            except Exception as e:
                last_exc = e
                if attempt < 3:
                    delay = 1.0 * (2 ** (attempt - 1))
                    logger.warning(f"Nominatim error (attempt {attempt}/3): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Geocoding error for '{query}': {e}")
                    return None
        return None

    async def reverse_geocode(self, lat: float, lng: float) -> Optional[dict]:
        last_exc = None
        for attempt in range(1, 4):
            try:
                await self._rate_limit()
                response = await self.client.get(
                    f"{self.BASE_URL}/reverse",
                    params={"lat": lat, "lon": lng, "format": "json", "addressdetails": 1},
                )
                response.raise_for_status()
                data = response.json()
                if data:
                    address = data.get("address", {})
                    return {
                        "lat": float(data.get("lat", 0)),
                        "lng": float(data.get("lon", 0)),
                        "display_name": data.get("display_name", ""),
                        "place_id": data.get("place_id", ""),
                        "osm_type": data.get("osm_type", ""),
                        "osm_id": data.get("osm_id", ""),
                        "address": address,
                        "locality": address.get("suburb", "") or address.get("quarter", "") or address.get("neighbourhood", "") or "",
                        "suburb": address.get("suburb", "") or "",
                        "district": address.get("state_district", "") or address.get("county", "") or address.get("district", "") or "",
                        "city": address.get("city", "") or address.get("town", "") or address.get("village", "") or address.get("municipality", "") or "",
                        "state": address.get("state", "") or "",
                        "country": address.get("country", "") or "",
                    }
                logger.info(f"No reverse geocoding result for ({lat}, {lng})")
                return None
            except httpx.TimeoutException as e:
                last_exc = e
                if attempt < 3:
                    delay = 1.0 * (2 ** (attempt - 1))
                    logger.warning(f"Reverse geocode timeout (attempt {attempt}/3): ({lat}, {lng}). Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.warning(f"Reverse geocode timeout after 3 attempts: ({lat}, {lng})")
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 403, 503, 502) and attempt < 3:
                    delay = 1.0 * (2 ** (attempt - 1))
                    logger.warning(f"Reverse geocode HTTP {e.response.status_code} (attempt {attempt}/3): ({lat}, {lng}). Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"Reverse geocode HTTP error for ({lat}, {lng}): {e.response.status_code}")
                return None
            except Exception as e:
                last_exc = e
                if attempt < 3:
                    delay = 1.0 * (2 ** (attempt - 1))
                    logger.warning(f"Reverse geocode error (attempt {attempt}/3): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Reverse geocode error for ({lat}, {lng}): {e}")
                    return None
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
            if e.response.status_code in (429, 403, 503, 502):
                logger.warning(f"Structured search HTTP {e.response.status_code}, retrying once...")
                await self._rate_limit()
                try:
                    response2 = await self.client.get(f"{self.BASE_URL}/search", params=params)
                    response2.raise_for_status()
                    data2 = response2.json()
                    if data2 and len(data2) > 0:
                        r2 = data2[0]
                        return {"lat": float(r2.get("lat", 0)), "lng": float(r2.get("lon", 0)), "display_name": r2.get("display_name", ""), "place_id": r2.get("place_id", ""), "osm_type": r2.get("osm_type", ""), "osm_id": r2.get("osm_id", "")}
                except Exception:
                    pass
            logger.error(f"Structured search HTTP error: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Structured search error: {e}")
            return None

    async def aclose(self):
        await self.client.aclose()
