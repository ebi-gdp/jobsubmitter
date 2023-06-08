import json
import importlib.resources
from jsonschema import Draft202012Validator, RefResolver
from . import schemas


def create_validator() -> Draft202012Validator:
    """ Make a validator object from local schema.

     Don't use jsonschema.validate to validate multiple instances. The Draft202012Validator will cache the resolved
     references after the first fetch from pgsc_calc repository (checked against debug logs) .
    """
    schemas_path = importlib.resources.path(schemas, 'api.json').parent

    schema = json.loads(importlib.resources.read_text(schemas, 'api.json'))
    resolver = RefResolver(base_uri=f"{schemas_path.as_uri()}/",
                           referrer=schema)

    return Draft202012Validator(schema, resolver)



