from orsdev import generator

import openrouteservice as ors

from os import path
import multiprocessing
import time
import csv
import logging
import json
import yaml
import dictdiffer

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M',
                    level=logging.INFO,
                    filename="{}_DevTester.log".format(time.strftime('%Y%m%d-%H%M')),
                    filemode='w')
logger = logging.getLogger(__name__)


class ORSprocessor(object):

    def __init__(self,
                 endpoint,
                 template,
                 geojson,
                 cycles=100):
        """
        Initializes a processing client to request dev or load testing.

        :param endpoint: Endpoint to test, one of 'directions', 'isochrones', 'matrix', 'optimization'.
        :type endpoint: str

        :param template_dict: Input parameter template YAML. Needs a fully qualified file path. See ../templates/ for options.
        :type template_dict: str

        :param geojson: Polygon to limit coordinate generation. Depends on server settings. Needs a fully qualified file path.
        :type geojson: str

        :param cycles: how many requests should be generated.
        :type cycles: int
        """

        if not template.endswith('.yaml'):
            template += '.yaml'

        with open(path.realpath(template)) as f:
            template_dict = yaml.safe_load(f)
            self._endpoint_dict = template_dict['endpoints'][endpoint]
            self.error_rules = template_dict['error_handler']['errors']
            self.apierrors = 0
            self.jsonerrors = 0
            self.error_breaker = 0

        self._endpoint = endpoint
        self._cycles = cycles
        self.cycle = None

        self.requester = generator.ORSGenerator(endpoint, template_dict, geojson)
        self.params = dict()

        self.out = list()
        self.filename = "{}_{}.csv".format(time.strftime('%Y%m%d-%H%M'), template.split('/')[-1])

    def dev_test(self,
                 client_stable,
                 client_dev,
                 method="differ"):
        """
        Constructs tests for dev purposes.

        :param client_stable: ors-py client with base_url pointing to server to test against.
        :type client_stable: openrouteservice.Client()

        :param client_dev: ors-py client with base_url pointing to server to test from.
        :type client_dev: openrouteservice.Client()

        :param method: What needs to be done. One of ["differ"].

        :return:
        """

        clients = (client_stable, client_dev)

        logger.info("Starting testing on\nStable server: {}\nDev Server: {}".format(*map(lambda x: x.base_url, clients)))

        if method == 'differ':
            self.out.append(("Cycle", "Key", "Change (Stable to Dev)", "Parameters"))

        pool = multiprocessing.Pool(2)
        for self.cycle in range(self._cycles):
            self.error_breaker = 0
            self._call_function(pool, clients, method)
            if self.cycle % (self._cycles / 10) == 0:
                logger.info("{} requests processed.".format(self.cycle + 1))
                self._write_results(method)
        logger.info("Testing finished!\nCycles: {}\nApiErrors: {}\nJSONDecodeErrors:{}".format(self._cycles,
                                                                                               self.apierrors,
                                                                                               self.jsonerrors))

    def _write_results(self, method):
        with open(self.filename, 'a+') as f:
            writer = csv.writer(f, delimiter=',')
            writer.writerows(self.out)
            self.out = list()

    def _call_function(self, pool, clients, method="differ"):
        """
        Wrapper to call different functions. This is necessary to be able to call itself again upon error.

        :param pool:
        :param clients:
        :param method:
        :return:
        """
        logger.debug("Starting cycle {}..".format(self.cycle))
        try:
            if method == "differ":
                # Get a new set of parameters
                self._get_request_parameters()
                lookups = []  # Initialize values so it can't be empty if pool.map fails with an exception
                lookups = pool.map(self._compare, clients)
                # if no element was found, raise error
                if not lookups:
                    raise KeyError("Method {} doesn't have valid lookup keys for endpoint {}".format(method,
                                                                                                     self._endpoint))

                assert lookups[0].keys() == lookups[1].keys()
                for lookup_key in lookups[0].keys():
                    collection = list(dictdiffer.diff(lookups[0][lookup_key],
                                                      lookups[1][lookup_key],
                                                      tolerance=0.0001,
                                                      expand=True))
                    if collection:
                        for diff in collection:
                            changeset = diff[0]
                            if changeset in ('remove', 'add'):
                                for change in diff[2]:
                                    change_text = "{} --> {}: {}".format(changeset, *change)

                            if changeset == 'change':
                                change_text = "Stable: {}\n\nDev: {}".format(*diff[2])
                            self.out.append((self.cycle, lookup_key, change_text, self.params))
            else:
                raise ValueError("{} is not a valid method.".format(method))
        except Exception as e:
            # Follow the rules set up in yaml
            if self.error_breaker > 50:
                raise Exception("More than 50 exceptions raised consecutively. Check log and change the config.yaml")
            self.error_breaker += 1

            error_name = e.__class__.__name__
            if error_name == 'JSONDecodeError':
                self.jsonerrors += 1
            elif error_name == 'ApiError':
                self.apierrors += 1
            rule = self.error_rules.get(error_name, None)
            if rule in ('skip', 'log') and error_name in self.error_rules.keys():
                self._call_function(pool, clients, method)
            else:
                raise e

    def _compare(self, client):

        if self._endpoint == 'directions':
            client_func = client.directions
        elif self._endpoint == 'isochrones':
            client_func = client.isochrones
        elif self._endpoint == 'matrix':
            client_func = client.distance_matrix
        else:
            raise ValueError("{} not a valid endpoint".format(self._endpoint))
        # Make actual request and log errors which don't have skip config.yaml values
        try:
            resp = client_func(**self.params, validate=False)
        except Exception as e:
            error_name = e.__class__.__name__
            if client.req.body:
                params = json.dumps(json.loads(client.req.body))
            else:
                params = client.req.url
            if self.error_rules.get(error_name) not in ("skip", "raise"):
                logger.error("Cycle {}:\n{} threw a {}: {}\nURL: {}\nParams: {}".format(self.cycle,
                                                                                        client.base_url,
                                                                                        e.__class__.__name__,
                                                                                        e,
                                                                                        client.req.url,
                                                                                        params))
            raise e

        # Compare lookup keys defined in config.yaml
        # Continue with next key if lookup key doesn't exist (ref. json vs. geojson)
        values = dict()
        for lookup in self._endpoint_dict['methods']['differ']:
            try:
                values[lookup] = dictdiffer.dot_lookup(resp, lookup)
            except (KeyError, IndexError):
                continue
        return values

    def _get_request_parameters(self):
        self.params = self.requester.create_requests()


if __name__ == "__main__":
    dev_clnt = ors.Client(base_url='http://129.206.5.136:8080/ors', timeout=120)
    test = ORSprocessor('matrix',
                     '../templates/openrouteservice_isochrones_matrix.yaml',
                     '../../geojson/regbez_karlsruhe.geojson',
                     300)
    test.dev_test(
                 dev_clnt)
    # test.create_parameters()