from os import path
import json
import yaml
from copy import deepcopy
import random
import numpy as np
from shapely.geometry import shape, Point

from pprint import pprint


class ORSGenerator(object):

    def __init__(self,
                 endpoint,
                 template_dict,
                 geojson,
                 cycles=100):

        self._endpoint_params = template_dict['endpoints'][endpoint]['params']
        self.accept_distance = template_dict['distance']

        if not geojson.endswith('.geojson'):
            geojson += '.geojson'

        with open(path.realpath(geojson)) as f:
            geojson_dict = json.load(f)

        self.polygon = shape(geojson_dict)
        self.minx, self.miny, self.maxx, self.maxy = self.polygon.bounds

        self._endpoint = endpoint
        self._multi_params = self._get_multi_params_map()[endpoint]
        self._cycles = cycles

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

