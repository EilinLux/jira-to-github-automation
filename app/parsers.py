from __future__ import annotations
from typing import Dict, Any, List, Optional
import re

# Import the AppLogger class from the 'app.logger' module.
# This class is expected to provide logging functionalities and base Jira connection details.
from app.logger import AppLogger


class PayloadParser(AppLogger):
    """
    PayloadParser Class

    This class is responsible for parsing the incoming Jira webhook payload
    and extracting relevant field values based on a predefined configuration.
    It extends AppLogger to utilize its logging capabilities and Jira commenting
    functionality for validation errors.

    It includes methods to process different types of Jira fields (dropdowns,
    people pickers, text fields, numeric fields, checklists) and perform
    validations (e.g., regex for text/numeric fields) as specified in the
    field configuration. It also checks for the presence of mandatory fields.

    Attributes:
        config_data (Dict[str, Any]): A dictionary that will store the extracted
                                      and processed configuration data from the Jira payload.
                                      This acts as the output container for parsed values.
        request_json (Dict[str, Any]): The raw JSON payload received from the Jira webhook.
                                       This is the input data source for parsing.
    """



    def _process_dropdown(self, field_config: Dict[str, Any], field_value: Optional[Dict[str, Any]]) -> None:
        """
        Processes dropdown field types from the Jira payload.

        Extracts the 'value' from the dropdown field and stores it in `self.config_data`
        under the specified `output_name`.

        Args:
            field_config (Dict[str, Any]): Configuration for the dropdown field,
                                           including its 'output_name'.
            field_value (Optional[Dict[str, Any]]): The raw value extracted from the Jira payload
                                                    for this dropdown field. Expected to be a dict
                                                    with a 'value' key.
        """
        # Check if the field value exists and contains the 'value' key.
        if field_value and 'value' in field_value:
            # Store the extracted value in config_data using the defined output name.
            self.config_data[field_config["output_name"]] = field_value['value']

    def _process_people(self, field_config: Dict[str, Any], field_value: Optional[List[Dict[str, Any]]]) -> None:
        """
        Processes 'people' (user picker) field types from the Jira payload.

        Extracts the 'displayName' of the first person in the list (if available)
        and stores it in `self.config_data`. This assumes a single-select user picker
        or that only the first user is relevant.

        Args:
            field_config (Dict[str, Any]): Configuration for the people field,
                                           including its 'output_name'.
            field_value (Optional[List[Dict[str, Any]]]): The raw value extracted from the Jira payload
                                                          for this people field. Expected to be a list
                                                          of dictionaries, each with a 'displayName' key.
        """
        # Check if field_value is a non-empty list and its first element has 'displayName'.
        if field_value and len(field_value) > 0 and "displayName" in field_value[0]:
            # Store the display name of the first person.
            self.config_data[field_config["output_name"]] = field_value[0]["displayName"]

    def _process_reporter(self, field_config: Dict[str, Any], field_value: Optional[Dict[str, Any]]) -> None:
        """
        Processes 'reporter' field type from the Jira payload.

        Extracts the 'displayName' of the reporter and stores it in `self.config_data`.

        Args:
            field_config (Dict[str, Any]): Configuration for the reporter field,
                                           including its 'output_name'.
            field_value (Optional[Dict[str, Any]]): The raw value extracted from the Jira payload
                                                    for the reporter field. Expected to be a dict
                                                    with a 'displayName' key.
        """
        # Check if field_value exists and contains the 'displayName' key.
        if field_value and "displayName" in field_value:
            # Store the reporter's display name.
            self.config_data[field_config["output_name"]] = field_value["displayName"]

    def _process_dropdown_nested(self, field_config: Dict[str, Any], field_value: Optional[Dict[str, Any]]) -> None:
        """
        Processes nested dropdown field types from the Jira payload.

        Extracts the 'value' from the nested 'child' dictionary within the field value
        and stores it in `self.config_data`.

        Args:
            field_config (Dict[str, Any]): Configuration for the nested dropdown field,
                                           including its 'output_name'.
            field_value (Optional[Dict[str, Any]]): The raw value extracted from the Jira payload
                                                    for this nested dropdown field. Expected to be
                                                    a dict with a 'child' key, which itself is a dict
                                                    with a 'value' key.
        """
        # Check if field_value exists, has a 'child' key, and the 'child' has a 'value' key.
        if field_value and 'child' in field_value and 'value' in field_value['child']:
            # Store the value from the nested child.
            self.config_data[field_config["output_name"]] = field_value['child']["value"]

    def _process_checklist(self, field_config: Dict[str, Any], field_value: Optional[List[Dict[str, Any]]]) -> None:
        """
        Processes checklist field types from the Jira payload.

        Extracts a list of 'value's from each item in the checklist and stores
        them in `self.config_data`.

        Args:
            field_config (Dict[str, Any]): Configuration for the checklist field,
                                           including its 'output_name'.
            field_value (Optional[List[Dict[str, Any]]]): The raw value extracted from the Jira payload
                                                          for this checklist field. Expected to be a list
                                                          of dictionaries, each with a 'value' key.
        """
        # Ensure the field_value is a list.
        if isinstance(field_value, list):
            # Use a list comprehension to extract 'value' from each item if present.
            values = [item['value'] for item in field_value if 'value' in item]
            # Store the list of extracted values.
            self.config_data[field_config["output_name"]] = values

    def _process_textfield(self, field_config: Dict[str, Any], attribute_found: Optional[str]) -> None:
        """
        Processes text field types, applying regex validation if specified.

        If a validation regex is provided in `field_config`, the extracted text
        is checked against it. If validation fails, an error is logged and
        a comment is added to the Jira issue. Otherwise, the text is stored.

        Args:
            field_config (Dict[str, Any]): Configuration for the text field,
                                           including 'output_name', optional 'validation' regex,
                                           and 'regex_error_message'.
            attribute_found (Optional[str]): The raw string value extracted from the Jira payload.
        """
        # Process only if an attribute value was found.
        if attribute_found is not None:
            # Get the regex validation pattern from the field configuration.
            regex_validation = field_config.get("validation")
            if regex_validation:
                # If a regex is defined, attempt to match it against the attribute.
                if not re.match(regex_validation, attribute_found):
                    # If the regex does not match, log an error and comment on Jira.
                    error_message = f"Invalid value '{attribute_found}' found for '{field_config['output_name']}'. {field_config.get('regex_error_message', '')}"
                    self.log_error(error_message)
                    # Add an error comment to the Jira issue.
                    # Note: self.add_comment_to_jira_issue expects jira_id.
                    # Assuming jira_id is available as self.config_data.get('ISSUE_KEY')
                    self.add_comment_to_jira_issue(
                        jira_id=self.config_data.get('ISSUE_KEY', 'UNKNOWN_JIRA_ID'),
                        comment_text=error_message,
                        comment_type="error"
                    )
                else:
                    # If validation passes, store the attribute.
                    self.config_data[field_config["output_name"]] = attribute_found
            else:
                # If no regex validation is specified, simply store the attribute.
                self.config_data[field_config["output_name"]] = attribute_found

    def _process_numericfield(self, field_config: Dict[str, Any], attribute_found: Optional[Any]) -> None:
        """
        Processes numeric field types, applying regex validation and type conversion to float.

        Similar to text fields, it applies regex validation. If validation passes,
        it attempts to convert the value to a float. Errors during validation or
        conversion are logged and commented on the Jira issue.

        Args:
            field_config (Dict[str, Any]): Configuration for the numeric field,
                                           including 'output_name', optional 'validation' regex,
                                           and 'regex_error_message'.
            attribute_found (Optional[Any]): The raw value extracted from the Jira payload.
                                             Can be string or numeric.
        """
        # Process only if an attribute value was found.
        if attribute_found is not None:
            regex_validation = field_config.get("validation")
            # Convert the attribute to a string for regex matching, as re.match expects string.
            str_attribute_found = str(attribute_found)
            if regex_validation:
                # If a regex is defined, attempt to match it.
                if not re.match(regex_validation, str_attribute_found):
                    # If regex does not match, log an error and comment on Jira.
                    error_message = f"Invalid value '{attribute_found}' for '{field_config['output_name']}'. {field_config.get('regex_error_message', '')}"
                    self.log_error(error_message)
                    # Add an error comment to the Jira issue.
                    self.add_comment_to_jira_issue(
                        jira_id=self.config_data.get('ISSUE_KEY', 'UNKNOWN_JIRA_ID'),
                        comment_text=error_message,
                        comment_type="error"
                    )
                else:
                    try:
                        # If validation passes, attempt to convert the value to a float.
                        self.config_data[field_config["output_name"]] = float(attribute_found)
                    except ValueError:
                        # Log and comment if conversion to float fails.
                        error_message = f"Could not convert '{attribute_found}' to float for '{field_config['output_name']}'."
                        self.log_error(error_message)
                        self.add_comment_to_jira_issue(
                            jira_id=self.config_data.get('ISSUE_KEY', 'UNKNOWN_JIRA_ID'),
                            comment_text=f"Invalid numeric value '{attribute_found}' for '{field_config['output_name']}'",
                            comment_type="error"
                        )
            else:
                try:
                    # If no regex validation, directly attempt to convert to float.
                    self.config_data[field_config["output_name"]] = float(attribute_found)
                except ValueError:
                    # Log and comment if conversion to float fails.
                    error_message = f"Could not convert '{attribute_found}' to float for '{field_config['output_name']}'."
                    self.log_error(error_message)
                    self.add_comment_to_jira_issue(
                        jira_id=self.config_data.get('ISSUE_KEY', 'UNKNOWN_JIRA_ID'),
                        comment_text=f"Invalid numeric value '{attribute_found}' for '{field_config['output_name']}'",
                        comment_type="error"
                    )

    def _check_mandatory_fields(self, ticket_fields: Dict[str, Any]) -> None:
        """
        Checks if all mandatory fields defined in `ticket_fields` configuration
        are present in the `self.config_data` (i.e., successfully extracted).

        If any mandatory field is missing, it logs an error and adds an error
        comment to the Jira issue. It then raises a ValueError to halt further
        processing, indicating a critical missing input.

        Args:
            ticket_fields (Dict[str, Any]): A dictionary defining the expected Jira fields,
                                            including their 'output_name' and a 'mandatory' flag.

        Raises:
            ValueError: If one or more mandatory fields are found to be missing.
        """
        missing_mandatory_fields = []
        # Iterate through the configured ticket fields.
        for key, config in ticket_fields.items():
            # Check if the field is marked as mandatory and if its output name is not in config_data.
            if config.get("mandatory") and config["output_name"] not in self.config_data:
                missing_mandatory_fields.append(config["output_name"])
                # Log the missing mandatory field.
                self.log_error(f"Mandatory field '{config['output_name']}' is missing in the extracted data.")
                # Add an error comment to the Jira issue.
                self.add_comment_to_jira_issue(
                    jira_id=self.config_data.get('ISSUE_KEY', 'UNKNOWN_JIRA_ID'),
                    comment_text=f"Mandatory field '{config['output_name']}' is missing in the request.",
                    comment_type="error"
                )

        # If any mandatory fields were missing, raise a ValueError.
        if missing_mandatory_fields:
            raise ValueError(f"Missing mandatory fields: {', '.join(missing_mandatory_fields)}")

    def _extract_field_value(self, field_config: Dict[str, Any]) -> Optional[Any]:
        """
        Extracts a single field value from the raw Jira payload (`self.request_json`)
        based on its input name defined in `field_config`.

        Args:
            field_config (Dict[str, Any]): Configuration for the field,
                                           including its 'input_name' (the key in the Jira payload).

        Returns:
            Optional[Any]: The extracted field value if found, otherwise None.
        """
        input_name = field_config["input_name"]
        try:
            # Attempt to access the field value using the input_name from the Jira payload.
            return self.request_json['issue']['fields'][input_name]
        except KeyError:
            # If the field is not found in the payload, log an info message and return None.
            self.log_info(f"Field '{input_name}' not found in Jira payload.")
            return None

