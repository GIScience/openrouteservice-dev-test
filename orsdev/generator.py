from os import path
import json
from copy import deepcopy
import random
from math import ceil
import numpy as np
import yaml
from shapely.geometry import shape, Point
import time

from openrouteservice import optimization
import openrouteservice as ors


class ORSGenerator(object):

    def __init__(self,
                 endpoint,
                 template_dict,
                 geojson):

        self._endpoint_dict = template_dict['endpoints'][endpoint]

        self._endpoint_params = template_dict['endpoints'][endpoint]['params']
        self.accept_distance = template_dict['distance']

        if not geojson.endswith('.geojson'):
            geojson += '.geojson'

        with open(path.realpath(geojson)) as f:
            geojson_dict = json.load(f)

        self.polygon = shape(geojson_dict)
        self.minx, self.miny, self.maxx, self.maxy = self.polygon.bounds

        self._endpoint = endpoint
        self._multi_params = self._get_multi_params_map().get(endpoint, [])

        self.params = dict()

    def create_requests(self):

        # First create all random parameters and pick all random parameters from template
        self._reset_params()
        self._pick_random_parameters(self.params)

        # Create all endpoint specific parameters
        # Coordinates are already initialized to an integer representing the amount of coordinates (through
        # _pick_random_paramters), so this will generate a varying number of coordinates per request with a
        # minimum_distance if specified within the GeoJSON supplied
        if self._endpoint == 'directions':
            self.params['coordinates'] = self._random_coordinates(n=self.params['coordinates'])

            # Define dynamic parameters
            if self.params.get('options'):
                isAvoidCountries = self.params['options'].get('avoid_countries')
                if isAvoidCountries is not None:
                    if isAvoidCountries is True:
                        num = random.choice(range(1, 3))
                        self.params['options']['avoid_countries'] = random.sample(range(1, 236), num)
                    else:
                        del self.params['options']['avoid_countries']

            if self.params.get('radiuses') is not None:
                if self.params['radiuses'] is True:
                    num = len(self.params['coordinates'])
                    pop = range(-1, 1000 * num, 1000)
                    self.params['radiuses'] = random.sample(pop, num)
                else:
                    del self.params['radiuses']

        if self._endpoint == 'isochrones':
            self.params['locations'] = self._random_coordinates(n=self.params['locations'])
            if self.params['profile'].startswith('driving'):
                factor = 2000 if self.params['range_type'] == 'distance' else 60
            if self.params['profile'].startswith('cycling'):
                factor = 2000 if self.params['range_type'] == 'distance' else 60
            if self.params['profile'].startswith('foot'):
                factor = 2000 if self.params['range_type'] == 'distance' else 60

            # self.params['range'] = random.sample(range(100, 60 * factor, 100), self.params['range'])
            self.params['range'] = random.sample(range(100, 2 * factor, 100), self.params['range'])
            if len(self.params['range']) == 1:
                self.params['interval'] = int(self.params['range'][0]/random.choice(range(1, 10)))

        if self._endpoint == 'matrix':
            self.params['locations'] = self._random_coordinates(n=self.params['locations'])

        if self._endpoint == 'optimization':
            params = {}
            jobs, vehicles = list(), list()

            job_amount, vehicle_capacity = None, None
            if self.params.get('capacities'):
                job_amount = 10
                vehicle_capacity = job_amount * ceil(self.params['jobs']/self.params['vehicles'])

            job_time_window, veh_time_window = None, None
            if self.params.get('time_windows'):
                job_time_window = [[28800, 64800]]
                veh_time_window = [28800, 64800]
            for idx, coord in enumerate(self._random_coordinates(self.params['jobs'])):
                jobs.append(optimization.Job(
                    id=idx,
                    location=coord,
                    service=120,
                    amount=[job_amount],
                    time_windows=job_time_window
                ))
            for idx, coord in enumerate(self._random_coordinates(self.params['vehicles'])):
                vehicles.append(optimization.Vehicle(
                    id=idx,
                    profile=self.params['profile'],
                    start=coord,
                    end=coord,
                    capacity=[vehicle_capacity],
                    time_window=veh_time_window
                ))
            params['jobs'] = jobs
            params['vehicles'] = vehicles

            return params

        return self.params

    def _reset_params(self):
        """Reset parameters before each request"""
        self.params = deepcopy(self._endpoint_params)
        self._init_parameters(self.params)

    def _init_parameters(self, d):
        """
        Updates self.init_params: when value is a dict not being able to call np.arange() on its values,
        it will call itself again with this dict value.
        """
        for k in d:
            if isinstance(d[k], dict):
                try:
                    d[k] = np.arange(*d[k].values())
                except:
                    self._init_parameters(d[k])

    @staticmethod
    def _get_multi_params_map():
        m = {
            "directions": ["extra_info", "attributes", "avoid_features"],
            "isochrones": ["attributes"],
            "matrix": ['metrics']
        }
        return m

    def _pick_random_parameters(self, d):
        for k in d:
            if isinstance(d[k], dict):
                self._pick_random_parameters(d[k])
            elif isinstance(d[k], (list, range, tuple, np.ndarray)):
                if k in self._multi_params:
                    num = random.choice(range(1, len(d[k])))
                    d[k] = random.sample(d[k], num)
                else:
                    d[k] = random.choice(d[k])

                # Sanitize to be regular Python builtin types
                if isinstance(d[k], np.int64):
                    d[k] = int(d[k])
                if isinstance(d[k], np.float64):
                    d[k] = float(d[k])

            elif isinstance(d[k], int):
                d[k] = range(d[k])
            else:
                raise ValueError

        return d

    def _random_coordinates(self, n):
        """
        Populates coordinates list depending on geojson given and if minimum_distance is given, it checks whether the
        last coordinate is further away from the one generated in that cycle.

        :param n:
        :return:
        """
        coordinates = []

        for _ in range(n):
            counter = 0
            in_geojson = False
            while not in_geojson:
                x = random.uniform(self.minx, self.maxx)
                y = random.uniform(self.miny, self.maxy)
                p = Point(x, y)
                if self.polygon.contains(p):
                    if self.accept_distance and coordinates:
                        if not self.accept_distance['min'] < p.distance(Point(coordinates[-1])) < self.accept_distance['max']:
                            continue
                    coordinates.append([x, y])
                    in_geojson = True
                if counter > 1000:
                    raise ValueError("Distance settings are too restrictive. Try a wider range and remember it's in degrees.")
                counter += 1

        return coordinates

if __name__ == '__main__':
    gen = ORSGenerator('optimization',
                 './templates/openrouteservice_optimization.yaml',
                 '..//geojson/regbez_karlsruhe.geojson')
    r = gen.create_requests()
    print("request successfully prepared:\n{}".format(r))
    clnt = ors.Client('5b3ce3597851110001cf62484d5d4d0972b540009af270b62e0a5dee',
                      timeout=1200)
    start = time.time()
    try:
        o = clnt.optimization(**r)
    except:
        print("Error from {}".format(clnt.req.body.decode('utf-8')))
        raise
    print("request took {} secs.".format(time.time() - start))
    print("Jobs: {}, Vehicles: {}".format(len(r['jobs']), len(r['vehicles'])))
    print(o)
