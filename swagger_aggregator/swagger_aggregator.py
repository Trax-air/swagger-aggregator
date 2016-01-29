# -*- coding: utf-8 -*-

from copy import deepcopy
import json
import logging
import os
import random
import re
import six
import sys
import time
import yaml

import flask
import requests
from requests.exceptions import ConnectionError
from shortuuid import uuid
from simplejson.scanner import JSONDecodeError

from swagger_parser import SwaggerParser

logger = logging.getLogger(__name__)


def retry_http(call):
    """Wrapper used to retry HTTP Errors with an exponential backoff

    Args:
        call: function being wrapped

    Returns:
        the wrapped function
    """

    def _retry_http(*args, **kwargs):
        """Retry a function call when catching requests.exceptions.RequestException"""
        last_exception = None
        multiplier = 1.5
        retry_interval = 0.5
        randomization_factor = 0.5
        total_sleep_time = 0
        # Capped to 10 seconds
        max_sleep_time = 10

        request_nb = 0
        while total_sleep_time < max_sleep_time:
            try:
                return call(*args, **kwargs)
            except ConnectionError as exc:
                # Inspired from https://developers.google.com/api-client-library/java/google-http-java-client/reference/
                # 1.20.0/com/google/api/client/util/ExponentialBackOff
                next_retry_sleep = (multiplier ** request_nb * (retry_interval *
                                    (random.randint(0, int(2 * randomization_factor * 1000)) / 1000. + 1 - randomization_factor)))

                total_sleep_time += next_retry_sleep
                request_nb += 1

                last_exception = exc
                logger.warning('Got an exception: {exc}. Slept ({retry} seconds / {total} seconds)'
                               .format(exc=exc,
                                       retry=total_sleep_time,
                                       total=max_sleep_time))
                time.sleep(next_retry_sleep)
        logger.error('Max sleep time exceeded, raising exception.')
        raise last_exception

    # Keep the doc
    _retry_http.__doc__ += call.__doc__

    return _retry_http


class SwaggerAggregator(object):
    """Create an API from an aggregation of API."""

    def __init__(self, config_file, *args):
        """Init the aggregation.

        Extra args will be used to replace args in the config file.

        Args:
            config_file: aggregation config.
        """
        self.config_file = config_file
        self.swagger_args = args
        self.errors = []
        self.swagger_apis = {}

        # Get config
        with open(self.config_file, 'r') as f:
            self.yaml_file = yaml.load(f.read())

        self.get_args()

    def get_args(self):
        """Get args of the config file.

        Returns
            Dict of arg name : arg value
        """
        self.args_dict = {}
        if 'args' in self.yaml_file:  # Check if args category is in the config
            # Get a list of args
            args_name = [i.replace(' ', '') for i in self.yaml_file['args'].split(',')]

            # Associate each arg name with a args given in the init.
            index = 0
            for arg_name in args_name:
                self.args_dict[arg_name] = self.swagger_args[index]
                index += 1
        return self.args_dict

    def parse_value(self, value):
        """Replace in the value all args.

        For example if you have an arg 'toto': 'test'
        and a value: 'http://toto.com'. The function will return
        'http://test.com'

        Args:
            value: the str to parse.

        Returns:
            Parsed value.
        """
        if isinstance(value, (six.text_type, six.string_types)):
            for key in self.args_dict.keys():
                value = value.replace(key, self.args_dict[key])
        return value

    def get_swagger_from_url(self, api_url):
        """Get the swagger file of the microservice at the given url.

        Args:
            api_url: url of the microservice.
        """
        return requests.get('{0}/swagger.json'.format(self.parse_value(api_url))).json()

    def get_aggregate_swagger(self):
        """Get swagger files associated with the aggregates.

        Returns:
            A dict of swagger spec.
        """
        if 'apis' in self.yaml_file:  # Check if apis is in the config file
            for api_name, api_url in self.yaml_file['apis'].items():
                if api_name not in self.swagger_apis:
                    # Get the swagger.json
                    try:
                        self.swagger_apis[api_name] = {'spec': self.get_swagger_from_url(api_url),
                                                       'url': self.parse_value(api_url)}
                        self.errors.remove(api_url)
                    except (ConnectionError, JSONDecodeError):
                        if api_url not in self.errors:
                            self.errors.append(api_url)
                        logger.warning(u'Cannot get swagger from {0}'.format(api_url))
                    except ValueError:
                        logger.info(u'Cannot remove {0} from errors'.format(api_url))
        return self.swagger_apis

    def exclude_paths(self, swagger):
        """Exclude path in the given swagger.

        Path to exclude are definded in the exclude_paths section of the config file.

        Args:
            swagger: dict of swagger spec.

        Returns:
            Swagger spec without the excluded paths.
        """
        # Get exclude_paths
        path_exclude = {p.split(' ')[1]: [p.split(' ')[0].lower()] for p in self.yaml_file.get('exclude_paths', [])}

        # Remove excluded paths
        swagger_filtered = deepcopy(swagger)
        for path, path_spec in swagger['paths'].items():
            if path in path_exclude.keys():
                for action, _ in path_spec.items():
                    if action in path_exclude[path]:
                        del swagger_filtered['paths'][path][action]
        return swagger_filtered

    def merge_aggregates(self, swagger):
        """Merge aggregates.

        Args:
            swagger: swagger spec to merge apis in.

        Returns:
            Aggregate of all apis.
        """
        swagger_apis = deepcopy(self.get_aggregate_swagger())
        for api, api_spec in swagger_apis.items():
            # Rename definition to avoid collision.
            api_spec['spec'] = json.loads(json.dumps(api_spec['spec']).replace('#/definitions/', u'#/definitions/{0}'.format(api)))

            if 'definitions' in api_spec['spec']:
                for definition_name, definition_spec in api_spec['spec']['definitions'].items():
                    if not definition_name.startswith(api):
                        swagger['definitions'][u'{0}{1}'.format(api, definition_name)] = definition_spec
                    else:
                        swagger['definitions'][definition_name] = definition_spec

            if 'paths' in api_spec['spec']:
                swagger['paths'].update(deepcopy(api_spec['spec']['paths']))

    def generate_swagger_json(self):
        """Generate a swagger from all the apis swagger."""
        # Base swagger
        base_swagger = {
            'swagger': '2.0',
            'info': self.yaml_file.get('info'),
            'basePath': self.yaml_file.get('basePath'),
            'definitions': {},
            'paths': {}
        }

        # Merge aggregates
        self.merge_aggregates(base_swagger)

        base_swagger = self.exclude_paths(base_swagger)

        # Change operation id
        spec = {}
        uri = {}
        path_list = {}
        action_list = {}
        current_module = sys.modules[__name__]
        for path, path_spec in base_swagger['paths'].items():
            for action, action_spec in path_spec.items():
                # Generate function name and get spec and api url for the path
                func_name = uuid()
                path_list[func_name] = path
                action_list[func_name] = action
                spec[func_name], uri[func_name] = self.get_spec_from_uri(path, action)

                # Export generated function to a module level function
                setattr(current_module, func_name, self.generate_operation_id_function(spec, uri, path_list, action_list, func_name))

                # Set operationId
                action_spec['operationId'] = 'swagger_aggregator.{0}'.format(func_name)

        self.swagger_parser = SwaggerParser(swagger_dict=deepcopy(base_swagger))

        # Remove exclude_fields from swagger
        for definition_name, definition_spec in base_swagger['definitions'].items():
            if definition_name in self.yaml_file.get('exclude_fields', {}):
                for key in self.yaml_file['exclude_fields'][definition_name]:
                    if key in definition_spec['required']:
                        definition_spec['required'].remove(key)
                    if key in definition_spec['properties']:
                        del definition_spec['properties'][key]

        # Write swagger.yaml
        with open(os.path.join(os.path.dirname(os.path.realpath(self.config_file)), 'swagger.yaml'), 'w') as f:
            f.write(yaml.dump(base_swagger, default_flow_style=False))

    def filter_definition(self, doc):
        """Filter the definition in the given doc.

        Args:
            doc: doc to filter.

        Returns:
            A filtered doc.
        """
        if isinstance(doc, dict):  # Filter dict
            doc_definition = self.swagger_parser.get_dict_definition(doc)

            # Get keys to remove
            keys_to_remove = self.yaml_file.get('exclude_fields', {}).get(doc_definition, [])

            # Remove keys
            for key in keys_to_remove:
                del doc[key]

            # Filter sub definition
            for k, v in doc.items():
                doc[k] = self.filter_definition(v)

            return doc
        elif isinstance(doc, list):  # List => filter every item
            for index, value in enumerate(doc):
                doc[index] = self.filter_definition(value)
            return doc
        else:
            return doc

    def generate_operation_id_function(self, spec, uri, path, action, func_name):
        """Generate a function to handle the current path.

        Args:
            spec: spec of the action the generated function should handle.
            uri: uri of the microservice corresponding to the spec.
            func_name: name the generated function should have.

        Returns:
            A function with func_name as name.
        """
        @retry_http
        def func(*args, **kwargs):
            """Handle a flask request for the current action.

            """
            # Get url from spec and flask query
            url = u'{0}{1}?{2}'.format(uri[func.__name__], path[func.__name__], flask.request.query_string)
            p = re.compile('{(.+)}')
            for path_param in re.findall(p, url):
                for k, v in kwargs.items():
                    if k == path_param:
                        url = url.replace('{{{0}}}'.format(k), str(v))

            requests_meth = getattr(requests, action[func.__name__])

            headers = {k: v for k, v in dict(flask.request.headers).items() if v}

            if not flask.request.headers.get('Content-Type', '').startswith('multipart/form-data'):
                req = requests_meth(url, data=flask.request.data, headers=headers)
            else:
                # Remove Content-Length because it cause error on nginx side
                if 'Content-Length' in headers:
                    headers['X-Content-Length'] = headers['Content-Length']
                    del headers['Content-Length']

                req = requests_meth(url, data=flask.request.stream, headers=headers)

            try:
                return (self.filter_definition(req.json()), req.status_code)
            except JSONDecodeError:
                return (req.text, req.status_code)
        func.__name__ = func_name
        return func

    def get_spec_from_uri(self, url, action):
        """Get spec from an path uri and an action.

        Args:
            url: url of the action.
            action: http action.

        Returns:
            (path spec, microservice url)
        """
        for api, api_spec in self.swagger_apis.items():
            for path_name, path_spec in api_spec['spec']['paths'].items():
                if path_name == url:
                    return path_spec[action], api_spec['url']
