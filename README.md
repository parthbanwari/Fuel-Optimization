# Fuel Route Optimizer API

> Plan a cost-optimal road trip. Give it two US cities -- get back the full driving route, the cheapest fuel stops, and the exact gallons to buy at each one.

Built with Django 5.2 LTS | OSRM | OpenRouteService | Python 3.12

---

## What it does

```
POST /api/v1/routes/
{ "origin": "Dallas, TX", "destination": "Los Angeles, CA" }
```

Returns:
- Full driving route as **GeoJSON** -- drop it straight into any map library
- Ordered fuel stops with **station name, highway exit, price, and exact gallons to buy**
- Total fuel cost for the trip
- Everything cached -- repeat requests return in under 50ms

---

## Features

- **Cost-optimal stops** -- greedy algorithm that tracks real fuel levels, not approximations
- **Real prices** -- 8,151 US truck-stop stations from the OPIS dataset
- **500-mile vehicle range** | **10 mpg** -- fully configurable via environment variables
- **Route simplification** -- 13,000+ OSRM waypoints reduced to ~280 before spatial search (48x fewer calculations)
- **Fast spatial search** -- equirectangular projection instead of haversine per segment (5–8x faster)
- **Two-tier cache** -- geocodes cached 30 days, routes cached 24 hours
- **Zero-config local dev** -- SQLite + in-memory cache, no Docker required to get started
- **Production-ready** -- PostgreSQL + Redis + Gunicorn via Docker Compose
- **Auto-generated API docs** -- Swagger UI at `/api/docs/`

---

## Quick start

### 1. Get a free ORS API key

Sign up at [openrouteservice.org](https://openrouteservice.org/dev/#/signup) -> Dashboard -> Tokens -> Request a token.
Free tier: 2,000 requests/day. No credit card needed.

### 2. Clone and install

```bash
git clone https://github.com/your-username/fuel-route-optimizer.git
cd fuel-route-optimizer

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set:

```bash
SECRET_KEY=your-secret-key-here   # generate one below
ORS_API_KEY=your-ors-key-here
```

Generate a secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4. Set up the database and load data

```bash
python manage.py migrate
python manage.py import_stations        # loads 8,151 stations from CSV (~6 seconds)
python manage.py load_coordinates       # geocodes all stations offline (~2 seconds)
```

### 5. Run

```bash
python manage.py runserver
```

API is live at `http://localhost:8000`

---

## Try it

```bash
curl -X POST http://localhost:8000/api/v1/routes/ \
  -H "Content-Type: application/json" \
  -d '{"origin": "Dallas, TX", "destination": "Los Angeles, CA"}'
```

Or open the interactive docs: **http://localhost:8000/api/docs/**

---

## API reference

### `POST /api/v1/routes/`

**Request**

```json
{
    "origin": "Dallas, TX",
    "destination": "Los Angeles, CA"
}
```

**Response**

```json
{
    "origin": {
        "input": "Dallas, TX",
        "latitude": 32.736212,
        "longitude": -96.784359
    },
    "destination": {
        "input": "Los Angeles, CA",
        "latitude": 34.05513,
        "longitude": -118.25703
    },
    "route": {
        "total_distance_miles": 1443.55,
        "total_duration_hours": 24.85,
        "total_duration_human": "24h 50m",
        "geometry": {
            "type": "LineString",
            "coordinates": [[-96.784463, 32.736158], "..."]
        }
    },
    "fuel_stops": [
        {
            "stop_number": 1,
            "name": "ROSCOE TRAVEL PLAZA",
            "address": "I-20, EXIT 235",
            "city": "Roscoe",
            "state": "TX",
            "latitude": 32.44595,
            "longitude": -100.53872,
            "route_distance_miles": 229.5,
            "distance_from_route_miles": 0.81,
            "price_per_gallon": 2.759,
            "gallons_purchased": 12.373,
            "cost_at_stop": 34.14
        }
    ],
    "summary": {
        "total_fuel_cost_usd": 262.28,
        "total_gallons_purchased": 94.355,
        "num_stops": 5,
        "avg_price_per_gallon": 2.7797
    },
    "meta": {
        "cached": false,
        "response_time_ms": 3375,
        "stations_evaluated": 308,
        "route_waypoints_raw": 13455,
        "route_waypoints_simplified": 279,
        "corridor_miles": 30,
        "vehicle_range_miles": 500,
        "vehicle_mpg": 10
    }
}
```

### `GET /api/v1/health/`

```json
{
    "status": "ok",
    "stations_total": 6738,
    "stations_geocoded": 6620
}
```

---

## Docker (production stack)

```bash
cp .env.example .env
# set SECRET_KEY and ORS_API_KEY in .env

docker compose up --build
```

Runs three services:

| Service | Image | Purpose |
|---|---|---|
| `web` | Python 3.12 + Gunicorn | Django app, 4 workers, port 8000 |
| `db` | PostgreSQL 16 | Production database |
| `redis` | Redis 7 | Route + geocode cache |

Then load data inside the container:

```bash
docker compose exec web python manage.py import_stations
docker compose exec web python manage.py load_coordinates
```

---

## Project structure

```
apps/
├── stations/                   # Data layer
│   ├── models.py               # FuelStation table
│   └── management/commands/
│       ├── import_stations.py  # Load CSV into DB
│       └── load_coordinates.py # Geocode stations offline (2s, no API)
│
└── routes/                     # API layer
    ├── views.py                # POST /api/v1/routes/
    ├── serializers.py          # Input validation + OpenAPI schema
    └── services/
        ├── geocoder.py         # City name -> coordinates (ORS, cached 30d)
        ├── routing_client.py   # Driving route (OSRM, cached 24h)
        ├── spatial.py          # Find stations near route
        ├── fuel_optimizer.py   # Cheapest stop algorithm
        └── route_service.py    # Orchestrator

config/
├── settings/
│   ├── base.py                 # Shared settings + all constants
│   ├── local.py                # SQLite + in-memory cache
│   └── production.py           # PostgreSQL + Redis

data/
├── fuel-prices-for-be-assessment.csv   # OPIS station prices (provided)
└── fuel_city_coordinates.csv           # City coordinates from GeoNames (offline)
```

---

## Configuration

All tunable via `.env`:

| Variable | Default | Description |
|---|---|---|
| `ORS_API_KEY` | -- | Required. OpenRouteService key for geocoding |
| `VEHICLE_MAX_RANGE_MILES` | `500` | Tank range in miles |
| `VEHICLE_MPG` | `10` | Fuel efficiency |
| `ROUTE_CORRIDOR_MILES` | `30` | Search width around route |
| `ROUTE_SIMPLIFY_SPACING_MILES` | `5` | Waypoint spacing after simplification |
| `ROUTE_CACHE_TTL_SECONDS` | `86400` | Route cache duration (24h) |
| `GEOCODE_CACHE_TTL_SECONDS` | `2592000` | Geocode cache duration (30d) |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` | Routing server |
| `REDIS_URL` | `redis://localhost:6379/0` | Cache backend (production) |
| `DATABASE_URL` | -- | PostgreSQL URL (production) |

---

## How the algorithm works

The vehicle starts with a full tank (500 miles). At each decision point:

- **Cheaper station within range ->** buy minimum fuel to reach it. No point paying more now for fuel available cheaper ahead.
- **Everything ahead costs more ->** fill the tank completely. Lock in the best price for as many miles as possible.
- **Destination within range ->** buy only what's needed to arrive.

This greedy approach is provably optimal -- it produces the lowest possible total fuel spend while respecting the 500-mile range constraint.

**Why the math checks out for Dallas -> LA:**
```
1,443 miles ÷ 10 mpg  = 144.3 gallons needed
Starting full tank     =  50.0 gallons (free)
Purchased along route  =  94.3 gallons  ← matches API response exactly
```

---

## Running tests

```bash
pip install -r requirements-dev.txt
python -m pytest -v
```

20 tests across three files:

| File | What it tests |
|---|---|
| `test_fuel_optimizer.py` | Algorithm correctness -- price preference, fill logic, arithmetic |
| `test_spatial.py` | Distance math -- haversine accuracy, simplification, projection |
| `test_views.py` | HTTP layer -- validation, error handling, cache behaviour |

---

## Tech stack

| | |
|---|---|
| Framework | Django 5.2 LTS |
| REST API | Django REST Framework |
| Routing | OSRM (free, no API key, no rate limit) |
| Geocoding | OpenRouteService (free tier, cached) |
| Cache | Redis (prod) / LocMemCache (dev) |
| Database | PostgreSQL (prod) / SQLite (dev) |
| API docs | drf-spectacular (OpenAPI 3.0 + Swagger UI) |
| Container | Docker + Docker Compose |
| Python | 3.12 |
#   F u e l - O p t i m i z e d - r o u t e s 
 
 #   F u e l - O p t i m i z a t i o n 
 
 