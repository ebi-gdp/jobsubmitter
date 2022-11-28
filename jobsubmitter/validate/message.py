import jsonschema
import logging

logger = logging.getLogger(__name__)


def validate_message(message, validator: jsonschema.Draft202012Validator) -> dict:
    """ Validate JSON message structure against API schema """
    try:
        validator.validate(message)
        logger.debug("JSON passes validation")
        return message
    except jsonschema.exceptions.ValidationError:
        logger.error("JSON fails validation")
        logger.error(f"Invalid JSON content: {message}")
        logger.error("Exception traceback", exc_info=True)
        return {}
