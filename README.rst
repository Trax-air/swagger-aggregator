.. image:: https://travis-ci.org/Trax-air/swagger-aggregator.svg?branch=master
   :alt: Travis status
   :target: https://travis-ci.org/Trax-air/swagger-aggregator

swagger-aggregator
==================

Swagger-aggregator allow you to create a swagger REST API from several other swagger REST APIs.

This can be really useful if you want to make an API Gateway accessing some of your internal APIs.
You can also filter which path you want to deliver, and which properties of your definitions you don't want to show.

Example Usage
-------------

Here is an example of an aggregate configuration.

.. code:: yaml

  args: pet_url

  info:
    version: "0.1"
    title: "API Gateway"

  basePath: /v2

  apis:
      pet: http://pet_url/v2

  exclude_paths:
    - DELETE /pets/{petId}

  exclude_fields:
    petPet:
      - id

This is not the most useful aggregation, as it only aggregate one API.
The first part, `args`, define that the first parameter we will send to the aggregate will be pet_url. Then pet_url will be replaced by the given value everywhere in the config.
The two next part, `info` and `basePath`, are the same as the ones you can find in every swagger API.
`apis`, define the different APIs you want to aggregate. A name is associated with it URL.
Then `exclude_paths` allow you to not deliver some path. In this case we don't want the user to delete a pet.

Finally, `exclude_fields` define the attributes of the definitions we do not want to show.
The value of the keys is the name of the API followed by the name of the definition. The value of each key will be a list of all properties to exclude.

Then use this command to generate the aggregated swagger file:

.. code:: python

  from traxit_aggregator import SwaggerAggregator

  SwaggerAggregator('config.yaml', 'pet.com')

Documentation
-------------

More documentation is available at https://swagger-aggregator.readthedocs.org/en/latest/.

Setup
-----

`make install` or `pip install swagger-aggregator`

License
-------

swagger-aggregator is licensed under http://opensource.org/licenses/MIT.
