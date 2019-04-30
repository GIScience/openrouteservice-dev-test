from locust import HttpLocust, TaskSet, task, events, web
import time
import sys
import os
import yaml
from statistics import mean, median

# Append current path to PYTHONPATH to find the orsdev module
sys.path.append(os.getcwd())

import openrouteservice as ors
from orsdev.generator import ORSGenerator

template = 'orsdev/templates/openrouteservice_optimization.yaml'
geojson = 'geojson/regbez_karlsruhe.geojson'

# Define client-side timeout in seconds
timeout = 1800
api_key = '5b3ce3597851110001cf62484d5d4d0972b540009af270b62e0a5dee'

# stats_page will accessible via http://localhost:8089/<stats_page>
stats_page = "/ors-stats"

# Statistics counters
jobs_amount = []
veh_amount = []
seconds = []
apierror = []

class OrsStressTest(TaskSet):
    """Task set to complete by each spawned user."""

    with open(os.path.realpath(template)) as f:
        template_dict = yaml.safe_load(f)

    gen = ORSGenerator('optimization',
                       template_dict,
                       geojson)

    @task
    def optimization(self):
        """Does the real request."""

        # Create random requests defined by 'template' variable
        params = self.gen.create_requests()

        start = time.time()
        try:
            result = ors.optimization.optimization(self.client, **params)

        # ref. https://medium.com/locust-io-lets-get-some-fun/locust-custom-client-23e205f4611f
        except ors.exceptions.ApiError as e:
            total = int((time.time() - start) * 1000)

            apierror.append(e.message)
            print(e.message)

            # needed to count towards locust statistics
            events.request_failure.fire(request_type="POST",
                                        name='optimization',
                                        response_time=total,
                                        exception=e)
        else:
            total = int((time.time() - start) * 1000)
            seconds.append(total)

            # count stats and send them to locust
            jobs_amount.append(len(params['jobs']))
            veh_amount.append(len(params['vehicles']))
            events.request_success.fire(request_type="POST",
                                        name='optimization',
                                        response_time=total,
                                        response_length=0)


class ORSclient(ors.Client):
    """redefine built-in client to openrouterservice-py Client class"""
    def __init__(self, host):
        super(ORSclient, self).__init__(base_url=host,
                                        key=api_key,
                                        timeout=timeout)


class ORSlocust(HttpLocust):
    """needed to bind the ORS client to Locust"""
    def __init__(self):
        super(ORSlocust, self).__init__()
        self.client = ORSclient(self.host)


class OptimizationUser(ORSlocust):
    """The actual user doing things."""
    task_set = OrsStressTest
    min_wait = 15  # msec
    max_wait = 15  # msec


@web.app.route(stats_page)
def total_content_length():
    """
    Add a route to the Locust web app, where we can see the total content-length
    """
    return """
    <b>JOBS<br></b>
        Mean: {0:.2f}<br>
        Median: {1:.2f}<br>
        Max: {2}<br>
        Min: {3}<br><br>
    <b>VEHICLES<br></b>
        Mean: {4:.2f}<br>
        Median: {5:.2f}<br>
        Max: {6}<br>
        Min: {7}<br><br>
    <b>SECONDS<br></b>
        Mean: {8:.2f}<br>
        Median: {9:.2f}<br>
        Max: {10}<br>
        Min: {11}<br><br>
    <b>API ERRORS:<br></b>
        Total: {12}<br>
        
    """.format(mean(jobs_amount),
               median(jobs_amount),
               max(jobs_amount),
               min(jobs_amount),
               mean(veh_amount),
               median(veh_amount),
               max(veh_amount),
               min(veh_amount),
               mean(seconds),
               median(seconds),
               max(seconds),
               min(seconds),
               len(apierror)
               )