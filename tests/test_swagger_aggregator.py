#!/usr/bin/env python
# -*- coding: utf-8 -*-

from mock import MagicMock
import pytest

from swagger_aggregator import SwaggerAggregator


@pytest.fixture
def yaml_file():
    return {
        "args": "identifications_url, ingestion_url",
        "info": {
            "version": "0.1",
            "title": "API Gateway"
        },
        "basePath": "/v1",
        "apis": {
            "identifications": "http://identifications_url/v1",
            "ingestion": "http://ingestion_url/v1"
        },
        "exclude_paths": [
            "POST /identifications/{id}/history/",
            "GET /identifications/",
            "DELETE /ingestions/{id}/resources",
            "PUT /ingestions/{id}",
            "GET /ingestions",
            "PUT /identifications/{id}/source/audio_url"
        ],
        'exclude_fields': {
            'identificationsTest': ['id'],
            'identificationsSubTest': ['id']
        }
    }


def test_get_args(yaml_file, mocker):
    try:
        mocker.patch('__builtin__.open', create=True)
    except Exception:  # Python3
        mocker.patch('builtins.open', create=True)
    mocker.patch('swagger_aggregator.swagger_aggregator.yaml.load', return_value=yaml_file)
    agg = SwaggerAggregator('config.yaml', 'trax', 'air')

    assert agg.args_dict == {'identifications_url': 'trax', 'ingestion_url': 'air'}


def test_parse_value(yaml_file, mocker):
    try:
        mocker.patch('__builtin__.open', create=True)
    except Exception:  # Python3
        mocker.patch('builtins.open', create=True)
    mocker.patch('swagger_aggregator.swagger_aggregator.yaml.load', return_value=yaml_file)
    agg = SwaggerAggregator('config.yaml', 'trax', 'air')

    assert agg.parse_value('toto') == 'toto'
    assert agg.parse_value('totoidentifications_url') == 'tototrax'
    assert agg.parse_value('identifications_urlingestion_url') == 'traxair'


def test_get_aggregate_swagger(yaml_file, mocker):
    try:
        mocker.patch('__builtin__.open', create=True)
    except Exception:  # Python3
        mocker.patch('builtins.open', create=True)
    mocker.patch('swagger_aggregator.swagger_aggregator.yaml.load', return_value=yaml_file)
    mock_request = mocker.patch('swagger_aggregator.swagger_aggregator.requests')
    mock_request.get.return_value.json.return_value = 'swagger'
    agg = SwaggerAggregator('config.yaml', 'trax', 'air')

    assert agg.get_aggregate_swagger() == {'identifications': {'spec': 'swagger', 'url': 'http://trax/v1'},
                                           'ingestion': {'spec': 'swagger', 'url': 'http://air/v1'}}


def test_exclude_paths(mocker, yaml_file):
    swagger = {
        'paths': {
            '/identifications/{id}/history/': {
                'get': {},
                'post': {}
            },
            'path': {
                'get': {},
                'post': {}
            }
        }
    }

    try:
        mocker.patch('__builtin__.open', create=True)
    except Exception:  # Python3
        mocker.patch('builtins.open', create=True)
    mocker.patch('swagger_aggregator.swagger_aggregator.yaml.load', return_value=yaml_file)
    agg = SwaggerAggregator('config.yaml', 'trax', 'air')

    assert agg.exclude_paths(swagger) == {
        'paths': {
            '/identifications/{id}/history/': {
                'get': {}
            },
            'path': {
                'get': {},
                'post': {}
            }
        }
    }


def test_get_spec_from_uri(mocker, yaml_file):
    try:
        mocker.patch('__builtin__.open', create=True)
    except Exception:  # Python3
        mocker.patch('builtins.open', create=True)
    mocker.patch('swagger_aggregator.swagger_aggregator.yaml.load', return_value=yaml_file)
    agg = SwaggerAggregator('config.yaml', 'trax', 'air')

    identifications_spec = {
        'paths': {
            'test': {
                'get': {'get': {}}
            },
            'path': {
                'get': {},
                'post': {}
            }
        }
    }

    ingestion_spec = {
        'paths': {
            'test2': {
                'post': {'post': {}}
            },
            'path2': {
                'get': {},
                'post': {}
            }
        }
    }

    agg.swagger_apis = {'identifications': {'spec': identifications_spec, 'url': 'http://trax/v1'},
                        'ingestion': {'spec': ingestion_spec, 'url': 'http://air/v1'}}

    assert agg.get_spec_from_uri('test', 'get') == ({'get': {}}, 'http://trax/v1')
    assert agg.get_spec_from_uri('test2', 'post') == ({'post': {}}, 'http://air/v1')


def test_generate_operation_id_function(mocker, yaml_file):
    try:
        mocker.patch('__builtin__.open', create=True)
    except Exception:  # Python3
        mocker.patch('builtins.open', create=True)
    mocker.patch('swagger_aggregator.swagger_aggregator.yaml.load', return_value=yaml_file)
    agg = SwaggerAggregator('config.yaml', 'trax', 'air')

    mock_request = mocker.patch('swagger_aggregator.swagger_aggregator.requests')
    flask_mock = mocker.patch('swagger_aggregator.swagger_aggregator.flask')
    flask_mock.request.data = '{"trax": "air"}'
    flask_mock.request.query_string = 'query=test&test=success'
    flask_mock.request.form = {'form_test': ['success']}
    file_mock = MagicMock()
    flask_mock.request.files = {'file': file_mock}

    spec = {
        'func_name': {
            'operationId': 'test.operationid',
            'parameters': [{
                'name': 'data',
                'in': 'body'
            },
                {
                'name': 'file',
                'in': 'form',
                'type': 'file'
            }]
        }
    }

    agg.generate_operation_id_function(spec, {'func_name': 'url'}, {'func_name': '/path/'}, {'func_name': 'post'}, 'func_name')()

    assert len(mock_request.post.call_args_list) == 1


def test_filter_definition(mocker, yaml_file):
    try:
        mocker.patch('__builtin__.open', create=True)
    except Exception:  # Python3
        mocker.patch('builtins.open', create=True)
    mocker.patch('swagger_aggregator.swagger_aggregator.yaml.load', return_value=yaml_file)
    agg = SwaggerAggregator('config.yaml', 'trax', 'air')

    agg.swagger_parser = MagicMock()
    agg.swagger_parser.get_dict_definition.side_effect = ['identificationsTest', 'identificationsSubTest']

    doc = [
        {'id': '123',
            'test': '456',
            'sub': {
                'id': '789',
                'test': '147'
            }}
    ]

    assert agg.filter_definition(doc) == [
        {'test': '456',
            'sub': {
                'test': '147'
            }}
    ]


def test_generate_swagger_json(mocker, yaml_file):
    try:
        mocker.patch('__builtin__.open', create=True)
    except Exception:  # Python3
        mocker.patch('builtins.open', create=True)
    mocker.patch('swagger_aggregator.swagger_aggregator.yaml.load', return_value=yaml_file)
    mock_yaml = mocker.patch('swagger_aggregator.swagger_aggregator.yaml.dump')
    mocker.patch('swagger_aggregator.swagger_aggregator.SwaggerParser')
    mocker.patch('swagger_aggregator.swagger_aggregator.SwaggerAggregator.generate_operation_id_function')
    mocker.patch('swagger_aggregator.swagger_aggregator.SwaggerAggregator.get_spec_from_uri', return_value=('uri', {}))
    mocker.patch('swagger_aggregator.swagger_aggregator.uuid', return_value='string')
    agg = SwaggerAggregator('config.yaml', 'trax', 'air')

    def exclude_paths(swagger):
        return swagger
    agg.exclude_paths = exclude_paths

    def swagger_aggregate():
        return {'identifications': {'spec': {'paths': {'123': {'get': {}}}, 'definitions': {'456': {'post': {}}}}, 'url': 'http://trax/v1'},
                'ingestion': {'spec': {'paths': {'789': {'delete': {}}}, 'definitions': {'147': {'put': {}}}}, 'url': 'http://air/v1'}}
    agg.get_aggregate_swagger = swagger_aggregate

    agg.generate_swagger_json()

    mock_yaml.assert_called_once_with({'info': {'version': '0.1', 'title': 'API Gateway'},
                                       'definitions': {'ingestion147': {'put': {}}, 'identifications456': {'post': {}}},
                                       'basePath': '/v1', 'swagger': '2.0',
                                       'paths': {'123': {'get': {'operationId': 'swagger_aggregator.string'}},
                                                 '789': {'delete': {'operationId': 'swagger_aggregator.string'}}}},
                                      default_flow_style=False)
