# openrouteservice-dev-test

This whole module is under construction and the only functionality valid for usage: **load testing**.

## Installation

```bash
git clone https://github.com/GIScience/openrouteservice-dev-test.git
cd openrouteservice-dev-test

# virtual env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Purpose

This repository is targeting 

- easy testing of openrouteservice development code, either by itself or benchmarked to another ORS instance.
- load testing openrouteservice infrastructure

Requests emitted from this package are randomized from parameter specific 

## Load testing

**Note**, this is still in development. A brief description how to load the `optimization` endpoint:

> **Prerequisite**: The endpoint on the host has to be named `optimization` for it to work out-of-the-box. If not,
replace the name in the `openrouteservice-py/openrouteservice/optimization.py:optimization` return statement of the `ors-py`
library this virtual environment uses.

1. Review the settings in `openrouteservice_optimization.yaml`. If OSRM is used, alter the `Profiles` section.

2. Choose a load test plan from `./locusts/`. E.g. `test_optimization.py`.

3. Review (and alter) the parameters below the `import` statements:
    
    - `template` takes any template as defined in 1.
    - `geojson` is used to randomly calculate coordinates for jobs/vehicles, i.e. if the random coordinates fall within 
    the GeoJSON and `template.distance.min` < coordinate - 1 < `template.distance.max` == `True`, the coordinate is valid.
    It's important to keep the constraints not too tight in the `template` (which again depends on the area of the GeoJSON)
    - `api_key` can be empty, only valid for ORS API
    - `stats_page` is the URL slug where you can see basic statistics of the load testing process, such as mean number of vehicles, jobs etc.

4. Try to run `locust` from the terminal and the root of the project. You have to alter the `host` to your own instance. 
See **Prerequisite**: the URL for the request is `<host><endpoint>?` with the endpoint name having a leading slash. E.g. for 
the ORS instance: `--host=https://api.openrouteservice.org` and registered endpoint `/optimization` requests to `https://api.openrouteservice.org/optimization`.

`locust -f locusts/test_optimization.py --host=https://api.openrouteservice.org`

5. Open <http://localhost:8089>, enter the amount of users and their hatch rate and watch the live feed:) 
See more statistics on <http://localhost:8089/stats_page>, e.g. <http://localhost:8089/ors_stats>
