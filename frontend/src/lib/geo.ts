export function haversineDistance(
  coord1: { lat: number; lng: number },
  coord2: { lat: number; lng: number }
): number {
  const R = 6371000
  const lat1 = toRad(coord1.lat)
  const lat2 = toRad(coord2.lat)
  const deltaLat = toRad(coord2.lat - coord1.lat)
  const deltaLng = toRad(coord2.lng - coord1.lng)

  const a =
    Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) * Math.sin(deltaLng / 2)

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))

  return R * c
}

export function toRad(deg: number): number {
  return (deg * Math.PI) / 180
}

export function toDeg(rad: number): number {
  return (rad * 180) / Math.PI
}

export function calculateBounds(
  center: { lat: number; lng: number },
  radiusKm: number
): { north: number; south: number; east: number; west: number } {
  const latChange = (radiusKm / 6371) * (180 / Math.PI)
  const lngChange = (radiusKm / 6371) * (180 / Math.PI) / Math.cos(toRad(center.lat))

  return {
    north: center.lat + latChange,
    south: center.lat - latChange,
    east: center.lng + lngChange,
    west: center.lng - lngChange,
  }
}

export function formatCoordinate(lat: number, lng: number, format: 'dms' | 'decimal' = 'decimal'): string {
  if (format === 'dms') {
    return `${toDMS(lat, 'lat')}, ${toDMS(lng, 'lng')}`
  }
  return `${lat.toFixed(6)}, ${lng.toFixed(6)}`
}

function toDMS(coordinate: number, type: 'lat' | 'lng'): string {
  const absolute = Math.abs(coordinate)
  const degrees = Math.floor(absolute)
  const minutes = Math.floor((absolute - degrees) * 60)
  const seconds = ((absolute - degrees - minutes / 60) * 3600).toFixed(2)

  const direction = type === 'lat'
    ? coordinate >= 0 ? 'N' : 'S'
    : coordinate >= 0 ? 'E' : 'W'

  return `${degrees}°${minutes}'${seconds}"${direction}`
}

export function midpoint(
  coord1: { lat: number; lng: number },
  coord2: { lat: number; lng: number }
): { lat: number; lng: number } {
  return {
    lat: (coord1.lat + coord2.lat) / 2,
    lng: (coord1.lng + coord2.lng) / 2,
  }
}

export function getZoomLevelForRadius(radiusKm: number): number {
  if (radiusKm > 50) return 10
  if (radiusKm > 20) return 11
  if (radiusKm > 10) return 12
  if (radiusKm > 5) return 13
  if (radiusKm > 2) return 14
  if (radiusKm > 1) return 15
  return 16
}

export function isPointInBounds(
  point: { lat: number; lng: number },
  bounds: { north: number; south: number; east: number; west: number }
): boolean {
  return (
    point.lat >= bounds.south &&
    point.lat <= bounds.north &&
    point.lng >= bounds.west &&
    point.lng <= bounds.east
  )
}

export function clusterPoints<T extends { lat: number; lng: number }>(
  points: T[],
  radiusKm: number
): (T & { count: number })[] {
  const clusters: (T & { count: number })[] = []
  const visited = new Set<number>()

  for (let i = 0; i < points.length; i++) {
    if (visited.has(i)) continue

    const cluster: (T & { count: number })[] = []
    for (let j = i; j < points.length; j++) {
      if (visited.has(j)) continue

      const distance = haversineDistance(points[i], points[j])
      if (distance <= radiusKm * 1000) {
        cluster.push({ ...points[j], count: 1 })
        visited.add(j)
      }
    }

    if (cluster.length > 0) {
      const avgLat = cluster.reduce((sum, p) => sum + p.lat, 0) / cluster.length
      const avgLng = cluster.reduce((sum, p) => sum + p.lng, 0) / cluster.length
      clusters.push({
        ...cluster[0],
        lat: avgLat,
        lng: avgLng,
        count: cluster.length,
      })
    }
  }

  return clusters
}
