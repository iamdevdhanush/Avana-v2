import logging
import httpx
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class OSRMService:
    BASE_URL = "https://router.project-osrm.org"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def get_route(
        self,
        source: Tuple[float, float],
        destination: Tuple[float, float],
        profile: str = "driving",
    ) -> Optional[dict]:
        src_lat, src_lng = source
        dst_lat, dst_lng = destination
        coordinates = f"{src_lng},{src_lat};{dst_lng},{dst_lat}"
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/{profile}/v1/driving/{coordinates}",
                params={
                    "overview": "full",
                    "geometries": "geojson",
                    "steps": "true",
                    "alternatives": "true",
                    "annotations": "true",
                },
            )
            response.raise_for_status()
            data = response.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                logger.warning(f"OSRM returned no routes: {data.get('code')}")
                return None
            route = data["routes"][0]
            geometry_coords = route.get("geometry", {}).get("coordinates", [])
            parsed_geometry = [[lng, lat] for lat, lng in geometry_coords] if geometry_coords else []
            parsed = {
                "distance": round(route.get("distance", 0), 2),
                "duration": round(route.get("duration", 0), 2),
                "geometry": parsed_geometry,
                "distance_km": round(route.get("distance", 0) / 1000, 2),
                "duration_minutes": round(route.get("duration", 0) / 60, 2),
                "weight": route.get("weight", 0),
                "weight_name": route.get("weight_name", ""),
            }
            if "legs" in route and route["legs"]:
                parsed["legs"] = []
                for leg in route["legs"]:
                    leg_data = {
                        "distance": leg.get("distance", 0),
                        "duration": leg.get("duration", 0),
                        "summary": leg.get("summary", ""),
                        "steps": [],
                    }
                    for step in leg.get("steps", []):
                        step_data = {
                            "distance": step.get("distance", 0),
                            "duration": step.get("duration", 0),
                            "name": step.get("name", ""),
                            "instruction": step.get("maneuver", {}).get("modifier", "") if step.get("maneuver") else "",
                            "bearing_before": step.get("maneuver", {}).get("bearing_before", 0) if step.get("maneuver") else 0,
                            "bearing_after": step.get("maneuver", {}).get("bearing_after", 0) if step.get("maneuver") else 0,
                            "location": step.get("maneuver", {}).get("location", []) if step.get("maneuver") else [],
                        }
                        leg_data["steps"].append(step_data)
                    parsed["legs"].append(leg_data)
            if len(data["routes"]) > 1:
                parsed["alternatives"] = []
                for alt in data["routes"][1:]:
                    alt_geom = alt.get("geometry", {}).get("coordinates", [])
                    parsed["alternatives"].append({
                        "distance": round(alt.get("distance", 0), 2),
                        "duration": round(alt.get("duration", 0), 2),
                        "geometry": [[lng, lat] for lat, lng in alt_geom] if alt_geom else [],
                        "distance_km": round(alt.get("distance", 0) / 1000, 2),
                        "duration_minutes": round(alt.get("duration", 0) / 60, 2),
                    })
            return parsed
        except httpx.TimeoutException:
            logger.warning(f"OSRM route timeout from {source} to {destination}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"OSRM HTTP error: {e.response.status_code} from {source} to {destination}")
            return None
        except Exception as e:
            logger.error(f"OSRM route error from {source} to {destination}: {e}")
            return None

    async def get_nearest_road(self, point: Tuple[float, float]) -> Optional[Tuple[float, float]]:
        lat, lng = point
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/nearest/v1/driving/{lng},{lat}.json",
                params={"number": 1},
            )
            response.raise_for_status()
            data = response.json()
            if data.get("code") != "Ok" or not data.get("waypoints"):
                logger.warning(f"No nearest road found for ({lat}, {lng})")
                return None
            waypoint = data["waypoints"][0]
            snapped_lng, snapped_lat = waypoint.get("location", [0, 0])
            return (float(snapped_lat), float(snapped_lng))
        except httpx.TimeoutException:
            logger.warning(f"Nearest road timeout for ({lat}, {lng})")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Nearest road HTTP error: {e.response.status_code} for ({lat}, {lng})")
            return None
        except Exception as e:
            logger.error(f"Nearest road error for ({lat}, {lng}): {e}")
            return None

    async def aclose(self):
        await self.client.aclose()
