"""CSCC Helper."""
import re
from jsonschema import validate
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from .cscc_exceptions import (
    MappingValidationError,
)
from enum import Enum


class DataTypes(Enum):
    """DataType class."""

    ALERT = "alerts"
    EVENT = "events"


def handle_data(data, logger):
    """Handle Unexpected values in data and transform it.

    :param logger: Logging object for logging purpose
    :param data: Source Property of findings to be ingested.
    """
    try:
        if isinstance(data, dict):
            for variable in list(data):
                # isinstance check is required otherwise this will replace int 0 with None
                if not isinstance(data.get(variable), int) and not data.get(
                    variable
                ):
                    data[variable] = "None"
                if not re.match("[a-zA-Z][a-zA-Z_]+", variable):
                    new_name = re.findall("[a-zA-Z][a-zA-Z_]+", variable)[0]
                    data[new_name] = data.pop(variable)
                    variable = new_name
                value = get_data(data, variable)
                if value:
                    data[variable] = value

            return data
        else:
            logger.error("Could not parse data.")
            return None
    except Exception as err:
        logger.error("Could not parse data \n{}. \nError:{}".format(data, err))


def get_data(data, variable):
    """Perform transformations on raw data and int and converts them to supported types.

    :param data: Raw data dict object
    :param variable: key of dictionary to be transformed

    :returns transformed data (str)
    """
    if isinstance(data.get(variable), list):
        return ",".join(map(str, data.get(variable)))
    if isinstance(data.get(variable), (dict, int)):
        return str(data.get(variable))


def get_external_url(data):
    """Retrieve external URL from given Netskope data object.

    :param data: JSON object retrieved from Netskope
    :return: Extracted external URL
    """
    external_url = data.get("url")
    if external_url and not (
        external_url.startswith("http://")
        or external_url.startswith("https://")
    ):
        external_url = "http://" + external_url
    return external_url


def map_cscc_data(mappings, data, logger, data_type, subtype):
    """Filter the raw data and returns the filtered data, which will be further pushed to GCP.

    :param mappings: List of fields to be pushed to GCP (read from cscc_mappings.json)
    :param data: Data to be mapped (retrieved from Netskope)
    :param logger: Logger object for logging purpose
    :return: Mapped data based on fields given in mapping file
    """
    # Add mandatory fields required in GCP ['timestamp', 'url', 'alert_type']
    mandatory_fields = ["timestamp", "url", "alert_type"]

    for field in mandatory_fields:
        if field not in mappings:
            mappings.append(field)

    mapped_dict = {}
    ignored_fields = []
    for key in mappings:
        if key in data:
            mapped_dict[key] = data[key]
        else:
            ignored_fields.append(key)

    return mapped_dict


def validate_subtype(instance):
    """JSON schema validate the subtype object mapped in mapping JSON files.

    :param instance: The subtype object to be validated
    """
    schema = {
        "type": "array",
    }

    validate(instance=instance, schema=schema)


def get_cscc_mappings(mappings, data_type):
    """Read the given mapping file and returns the dict of mappings to be applied to raw data.

    :param mapping_file: Name of mapping file
    :param data_type: Data type (alert/event) for which the mappings are to be fetched
    :return: Read mappings
    """
    mappings = mappings["taxonomy"][data_type]

    # Validate each subtype
    for subtype, subtype_map in mappings.items():
        try:
            validate_subtype(subtype_map)
        except JsonSchemaValidationError as err:
            raise MappingValidationError(
                'Error occurred while validating CSCC mappings for type "{}". '
                "Error: {}".format(subtype, err)
            )
    return mappings
