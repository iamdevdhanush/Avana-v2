"""Test heatmap with correct numeric zoom."""
import httpx, asyncio

async def test():
    async with httpx.AsyncClient(timeout=60) as c:
        # Correct payload with numeric zoom
        r = await c.post('http://localhost:8000/api/v1/risk/heatmap', json={
            'sw_lat': 12.5, 'sw_lng': 77.0,
            'ne_lat': 13.5, 'ne_lng': 78.0,
            'zoom': 12,
            'min_score': 0
        })
        print(f'Status: {r.status_code}')
        j = r.json()
        if r.status_code == 200:
            pts = j.get('points', [])
            print(f'Points: {len(pts)}')
            dists = j.get('district_summaries') or []
            print(f'District summaries: {len(dists)}')
            if pts:
                p = pts[0]
                print(f'Sample: lat={p.get("latitude","?")} weight={p.get("weight","?")} cat={p.get("risk_category","?")}')
            if dists:
                d = dists[0]
                print(f'District: {d.get("district","?")} avg={d.get("avg_score","?")} total={d.get("total_incidents","?")}')
        else:
            print(f'Error: {r.text[:300]}')

asyncio.run(test())
