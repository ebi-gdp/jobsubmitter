import jsonschema
import logging

logger = logging.getLogger(__name__)


def validate_message(message, validator: jsonschema.Draft202012Validator) -> dict:
    """ Validate JSON message structure against API schema """
    try:
        validator.validate(message)
        logger.debug("Good job request: JSON passes validation, submitting job")
        return message
    except jsonschema.exceptions.ValidationError:
        logger.error("Bad job request: JSON fails validation, skipping job", exc_info=True)
        return {}
