import json
import logging

import jsonschema
from kafka import KafkaConsumer
from jobsubmitter.validate.message import validate_message
from jobsubmitter.validate.schema import create_validator

logging.getLogger('kafka').setLevel(logging.WARNING)  # kafka is so loud
logger = logging.getLogger(__name__)


def create_consumer(client_id: str, bs_servers: list[str],
                    topic: str = 'pipeline-launch',
                    group: str = 'jobsubmitter') -> KafkaConsumer:
    """Create a Kafka consumer that reads and validates JSON job requests """
    validator = create_validator()

    return KafkaConsumer(topic,
                         client_id=client_id,
                         group_id=group,
                         bootstrap_servers=bs_servers,
                         value_deserializer=lambda m: _read_message(m, validator),
                         enable_auto_commit=True)


def _read_message(m: bytes, validator: jsonschema.Draft202012Validator) -> dict:
    """ Decode and validate the JSON content of a message """
    try:
        message = json.loads(m.decode('utf-8'))
        logger.debug("Valid JSON decoded")
        return validate_message(message, validator)
    except (json.decoder.JSONDecodeError, UnicodeDecodeError):
        logger.error("Invalid JSON", exc_info=True)
        return json.loads('{}')
