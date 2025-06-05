import os
from typing import Dict, Any, Tuple, List, Optional

# Import custom exception classes for specific error handling scenarios.
from app.exceptions import InvalidPayloadError, InvalidJiraConfigurationParser, MissingRequiredDataError, GcpProvisioningError, InvalidMethodError, GitHubOperationError
# Import the GitHub handler for repository operations.
from app.github import GitHubHandler

# Import provisioner classes (type hints as strings to avoid potential circular dependencies if the actual imports are deeper).
# These classes are responsible for generating GCP-specific configurations (e.g., Terraform).
from app.provisioners.hierarchy.folders import GcpFolderProvisioner
from app.provisioners.hierarchy.projects import GcpProjectProvisioner
# Import configurations for Jira ticket fields, mapping them to expected payload structures.
from configs.jira.configurations import project_creation_ticket_fields, folder_creation_ticket_fields
# Import the payload parser for extracting data from Jira webhooks.
from app.parsers import PayloadParser

import json
import traceback

# Debug flags for controlling logging verbosity.
DEBUG: bool = os.getenv('DEBUG', True)  
DEBUG_PAYLOAD: bool = os.getenv('DEBUG_PAYLOAD', True)  # bool(os.getenv('DEBUG_PAYLOAD')) # Controls logging of the full payload.

# Import GitHub repository credentials mapping issue types to specific repos.
from configs.github.credentials import github_configs


class AppManager(PayloadParser):
    """
    AppManager Class

    This class orchestrates the entire workflow of processing a Jira webhook,
    from initial payload validation and parsing to delegating provisioning tasks
    to appropriate GCP provisioners and finally pushing generated configurations
    to GitHub. It manages the shared state (config_data, request_json) throughout
    the process.

    It inherits payload parsing capabilities from PayloadParser and logging from AppLogger.
    """

    def __init__(self):
        """
        Initializes the AppManager, setting up empty containers for configuration
        data and the raw request payload. It also initializes other attributes
        that will hold state during the workflow.
        """
        super().__init__() # Initialize PayloadParser, passing an empty dict for request_json initially.

        self.config_data: Dict[str, Any] = {}  # Stores parsed configuration data extracted from Jira fields.
        self.request_json: Dict[str, Any] = {}  # Stores the raw incoming Jira webhook payload.

        # Attributes specific to provisioning flows, populated during validation and processing.
        self.dw_env_project_name_list: List[str] = [] # List of Datawave environment project names.
        self.parent_folder_id: Optional[str] = None # ID of the parent GCP folder.

        self.issue_type_name: str = "" # Name of the Jira issue type (e.g., "New GCP Project Provisioning").
        self.jira_id: str = "" # Key of the Jira issue (e.g., "PROJ-123").
        self.provisioner: Optional[Any] = None # Instance of the selected GCP provisioner (e.g., GcpProjectProvisioner).
        self.github_manager: Optional[GitHubHandler] = None # Instance of the GitHub handler for repository operations.

    def check_if_post_request(self, request: Any) -> None:
        """
        Validates if the incoming request method is POST.
        Raises an InvalidMethodError if the method is not POST.

        Args:
            request (Any): The incoming HTTP request object (e.g., Flask request object).
        """
        # Ensure only POST requests are processed for webhooks.
        if request.method != 'POST':
            self.log_error(f"Received non-POST request: {request.method}. Method Not Allowed.")
            raise InvalidMethodError("Received non-POST request. Method Not Allowed.")
        else:
            self.log_info("Received a POST request. Method Allowed.")

    def transform_into_json(self, request: Any) -> None:
        """
        Parses the incoming request body into a JSON payload.
        Validates the basic structure of the JSON payload to ensure it's a valid Jira webhook.
        Raises an InvalidPayloadError if the payload is empty or malformed.

        Args:
            request (Any): The incoming HTTP request object.
        """
        # Attempt to parse the request body as JSON. 'silent=True' prevents errors if not JSON.
        self.request_json = request.get_json(silent=True)
        # Validate critical keys expected in a Jira webhook payload.
        if not isinstance(self.request_json, dict) or \
           'issue' not in self.request_json or \
           'key' not in self.request_json['issue'] or \
           "fields" not in self.request_json['issue'] or \
           "issuetype" not in self.request_json['issue']['fields'] or \
           "name" not in self.request_json["issue"]["fields"]["issuetype"]:
            self.log_error("Empty or invalid JSON payload received from request body.")
            raise InvalidPayloadError("Empty or invalid JSON payload received from request body. "
                                      "If not empty, check that the fields 'key' under 'issue' is present "
                                      "and/or 'name' under 'issue'.'fields'.'issuetype'.")
        else:
            self.log_info("Valid JSON payload received from request body.")
            # Log the full payload if DEBUG_PAYLOAD is enabled.
            if DEBUG_PAYLOAD:
                self.log_info(f"Full Jira payload: {json.dumps(self.request_json, indent=2)}")

    def _extract_jira_id(self) -> str:
        """
        Extracts the Jira issue key (e.g., "PROJ-123") from the payload.
        Assumes the payload structure has been validated by `transform_into_json`.

        Returns:
            str: The Jira issue key.
        """
        # Store the Jira issue key in config_data and return it.
        self.config_data['ISSUE_KEY'] = self.request_json['issue']["key"]
        return self.request_json['issue']["key"]

    def _extract_issue_type_name(self) -> str:
        """
        Extracts the Jira issue type name (e.g., "New GCP Project Provisioning") from the payload.
        Assumes the payload structure has been validated by `transform_into_json`.

        Returns:
            str: The Jira issue type name.
        """
        return self.request_json["issue"]["fields"]["issuetype"]["name"]

    def extract_issue(self) -> None:
        """
        Extracts the Jira issue type name and Jira ID from the parsed payload.
        Performs basic validation on their presence and logs the start of processing,
        also adding a comment to the Jira issue.

        Raises:
            MissingRequiredDataError: If the issue type name or Jira ID are not found.
        """
        self.issue_type_name = self._extract_issue_type_name()
        self.jira_id = self._extract_jira_id()

        if not self.issue_type_name:
            self.log_error("Issue type name not found in the request.")
            raise MissingRequiredDataError("Issue type name not found in the request.")

        if not self.jira_id:
            self.log_error("Issue Jira ID not found in the request.")
            raise MissingRequiredDataError("Issue Jira ID not found in the request.")
        else:
            self.log_info(f"[START] Received Jira webhook payload from {self.jira_id} for a {self.issue_type_name}.")
            # Add an informational comment to the Jira issue indicating processing has started.
            self.add_comment_to_jira_issue(
                comment_text=f"[START] Received Jira webhook payload for {self.jira_id} ({self.issue_type_name}).",
                jira_id=self.jira_id,
                comment_type="info"
            )

    def _extract_config_field_values_for_issue_request(self) -> Dict[str, Any]:
        """
        Selects the appropriate Jira field configuration based on the issue type name.
        This configuration guides how to parse the Jira payload.

        Returns:
            Dict[str, Any]: The dictionary containing field configurations for the specific issue type.

        Raises:
            InvalidJiraConfigurationParser: If the issue type is not recognized in the configurations.
        """
        # Dispatch to different configuration based on issue type.
        if self.issue_type_name == "New GCP Project Provisioning":
            return project_creation_ticket_fields
        elif self.issue_type_name == "New GCP Folder Provisioning":
            return folder_creation_ticket_fields
        else:
            # If the issue type is not configured, raise an error.
            raise InvalidJiraConfigurationParser(f"Issue type '{self.issue_type_name}' not found in the configuration file to parse the request arguments.")

    def _log_request_details(self) -> None:
        """
        Logs the raw JSON payload if DEBUG_PAYLOAD is True.
        This is useful for debugging and understanding the incoming data structure.
        """
        if DEBUG_PAYLOAD:
            log_data = {
                "request_json": self.request_json,
            }
            self.log_info(f"Request details: {json.dumps(log_data, indent=2)}")

    def parse_jira_request(self) -> None:
        """
        Parses the Jira request payload using the configured ticket fields.
        It iterates through defined fields, extracts their values, processes them
        based on their type (dropdown, people, text, numeric, etc.), and stores
        them in `self.config_data`. It also performs mandatory field checks.

        Raises:
            ValueError: If there's a missing key in the Jira payload or an unexpected error during parsing.
        """
        # Get the specific ticket field configurations for the current issue type.
        ticket_fields = self._extract_config_field_values_for_issue_request()
        self._log_request_details() # Log the raw request for debugging.

        try:
            # Iterate through each field configuration to extract and process values.
            for key, element in ticket_fields.items():
                self.log_info(f"Processing field '{key}' with config: {element}")
                # Extract the raw field value from the Jira payload.
                field_value = self._extract_field_value(element)

                # Dispatch to the appropriate processing method based on the field type.
                if element["type"] == "dropdown":
                    self._process_dropdown(element, field_value)
                elif element["type"] == "people":
                    self._process_people(element, field_value)
                elif element["type"] == "reporter":
                    self._process_reporter(element, field_value)
                elif element["type"] == "dropdown_nested":
                    self._process_dropdown_nested(element, field_value)
                elif element["type"] == "checklist":
                    self._process_checklist(element, field_value)
                elif element["type"] == "textfield":
                    self._process_textfield(element, field_value)
                elif element["type"] == "numericfield":
                    self._process_numericfield(element, field_value)
                else:
                    self.log_warning(f"Unsupported field type: '{element['type']}' for field '{key}'. Skipping.")

            # After processing all fields, check if all mandatory fields are present.
            self._check_mandatory_fields(ticket_fields)

            self.log_info(f"Successfully extracted configuration data: {json.dumps(self.config_data, indent=2)}")

        except ValueError:
            # Re-raise ValueError exceptions (e.g., from _check_mandatory_fields or type conversions).
            raise
        except KeyError as e:
            # Catch and log missing keys in the Jira payload.
            error_message = f"Missing key in Jira payload during parsing: {e}"
            self.log_error(error_message)
            raise ValueError(error_message) # Re-raise as ValueError for consistent handling.
        except Exception as e:
            # Catch any other unexpected errors during parsing.
            error_message = f"An unexpected error occurred during parsing: {traceback.format_exc()}"
            self.log_error(error_message)
            raise ValueError(error_message) # Re-raise as ValueError.

    def select_provisioner(self) -> None:
        """
        Selects and initializes the appropriate GCP provisioner based on the Jira issue type.
        The provisioner is responsible for generating the necessary Terraform configurations.

        Raises:
            InvalidJiraConfigurationParser: If the issue type is not recognized for provisioning.
        """
        # Dispatch to different provisioner classes based on the issue type.
        if self.issue_type_name == "New GCP Project Provisioning":
            self.provisioner = GcpProjectProvisioner(config_data=self.config_data)
            self.log_info(f"Selected GcpProjectProvisioner for issue type '{self.issue_type_name}'.")
        elif self.issue_type_name == "New GCP Folder Provisioning":
            self.provisioner = GcpFolderProvisioner(config_data=self.config_data)
            self.log_info(f"Selected GcpFolderProvisioner for issue type '{self.issue_type_name}'.")
        else:
            # If no matching provisioner is found, raise an error.
            raise InvalidJiraConfigurationParser(f"Issue type '{self.issue_type_name}' not configured for provisioning.")

    def _get_github_credentials(self) -> Tuple[str, str, str]:
        """
        Retrieves GitHub credentials (token, repository owner, repository name)
        based on the current issue type or debug mode.

        Returns:
            Tuple[str, str, str]: A tuple containing the GitHub token, repository owner, and repository name.

        Raises:
            GitHubOperationError: If GitHub configuration is missing for the effective issue type.
        """
        # Determine the effective configuration key (debug_config if DEBUG is True, otherwise issue_type_name).
        effective_config_key = "debug_config" if DEBUG else self.issue_type_name

        credentials = github_configs.get(effective_config_key)
        if not credentials:
            # If credentials are not found, raise an error.
            raise GitHubOperationError(f"GitHub configuration missing for issue type: {effective_config_key}")

        return (credentials["GITHUB_TOKEN"], credentials["REPO_OWNER"], credentials["REPO_NAME"])

    def initialize_github_manager(self) -> None:
        """
        Initializes the GitHubHandler instance using the retrieved GitHub credentials.
        Logs the connection details and adds a comment to the Jira issue.

        Raises:
            MissingRequiredDataError: If the issue type name is not set before calling this method.
            Exception: For any errors during credential retrieval or GitHubHandler initialization.
        """
        if not self.issue_type_name:
            raise MissingRequiredDataError("Issue type not found in transformed data for GitHub credentials. Cannot initialize GitHub manager.")
        try:
            # Retrieve GitHub credentials.
            GITHUB_TOKEN, REPO_OWNER, REPO_NAME = self._get_github_credentials()
            # Initialize the GitHubHandler.
            self.github_manager = GitHubHandler(GITHUB_TOKEN, REPO_OWNER, REPO_NAME)
            self.log_info(f"Initialized GitHubManager for repo '{REPO_NAME}' under '{REPO_OWNER}'.")
            # Add an informational comment to Jira about the GitHub connection.
            self.add_comment_to_jira_issue(
                comment_text=f"Connecting to GitHub '{REPO_NAME}' under '{REPO_OWNER}' for '{self.issue_type_name}'.",
                jira_id=self.jira_id,
                comment_type="info"
            )
        except Exception as e:
            self.log_error(f"Failed to initialize GitHub manager: {e}")
            raise e # Re-raise the exception for higher-level handling.

    def validate_jira_request(self) -> None:
        """
        Performs specific validation of the parsed Jira request data using the selected provisioner.
        If validation fails, it logs an error, adds an error comment to Jira, and changes the issue status.

        Raises:
            GcpProvisioningError: If the provisioner's validation fails.
        """
        try:
            # Call the provisioner's internal validation method.
            if self.provisioner:
                self.provisioner._validate_jira_request()
                self.log_info("Jira request data validated successfully by the provisioner.")
                # Add a comment to Jira with the request summary from the provisioner.
                self.add_comment_to_jira_issue(
                    comment_text=self.provisioner._get_request_comment_message(),
                    jira_id=self.jira_id,
                    comment_type="info"
                )
            else:
                self.log_error("Provisioner not initialized before validation.")
                raise GcpProvisioningError("Provisioner not initialized.")

        except GcpProvisioningError as e:
            # If GCP provisioning validation fails, log the error, comment on Jira, and block the issue.
            self.log_error(f"GCP provisioning validation failed: {e}")
            self.add_comment_to_jira_issue(comment_text=str(e), jira_id=self.jira_id, comment_type="error")
            self.change_issue_status(jira_id=self.jira_id, transition_name="Set as blocked")
            raise # Re-raise the exception to propagate the error.

    def built_terraform_yaml(self) -> None:
        """
        Instructs the selected provisioner to build the necessary Terraform YAML configurations.
        If an error occurs during this process, it logs the error, adds an error comment to Jira,
        and changes the issue status to "Set as blocked".

        Raises:
            GcpProvisioningError: If the provisioner fails to build the Terraform YAMLs.
        """
        try:
            # Call the provisioner's method to build Terraform YAMLs.
            if self.provisioner:
                self.provisioner._built_terraform_yamls()
                self.log_info("Terraform YAMLs built successfully by the provisioner.")
            else:
                self.log_error("Provisioner not initialized before building Terraform YAMLs.")
                raise GcpProvisioningError("Provisioner not initialized.")

        except GcpProvisioningError as e:
            # If building YAMLs fails, log the error, comment on Jira, and block the issue.
            self.log_error(f"Failed to build Terraform YAMLs: {e}")
            self.add_comment_to_jira_issue(comment_text=str(e), jira_id=self.jira_id, comment_type="error")
            self.change_issue_status(jira_id=self.jira_id, transition_name="Set as blocked")
            raise # Re-raise the exception to propagate the error.

    def push_to_github(self) -> None:
        """
        Pushes the generated Terraform YAML files to GitHub by committing them to a new branch
        and creating a pull request. It iterates through the `github_payload` generated by
        the provisioner. It handles auto-approval and updates Jira issue status accordingly.

        Raises:
            GcpProvisioningError: If any GitHub operation fails or if the provisioner's payload is invalid.
        """
        try:
            if not self.github_manager:
                self.log_error("GitHub manager not initialized before pushing to GitHub.")
                raise GcpProvisioningError("GitHub manager not initialized.")
            if not self.provisioner or not hasattr(self.provisioner, 'github_payload'):
                self.log_error("Provisioner or its github_payload is not available.")
                raise GcpProvisioningError("Provisioner did not generate GitHub payload.")

            # Iterate through the generated GitHub payload, which contains data for each project/environment.
            for dw_project_data in self.provisioner.github_payload.values():
                # Iterate through the encoded YAML content for each file type within the project data.
                for file_type_key, file_data in dw_project_data.get("yaml_content_encoded", {}).items():
                    self.log_info(f"Committing file: {file_data.get('path')} to branch: {dw_project_data.get('new_branch_name')}")
                    # Commit each file to the new branch using the GitHub manager.
                    self.github_manager._commit_new_file(
                        file_data.get("path"),
                        file_data.get("commit_message"),
                        file_data.get("file"), # This is the base64 encoded content
                        dw_project_data.get("new_branch_name")
                    )
                self.log_info(f"All files committed for project data: {dw_project_data.get('pr_title')}")

                # Define a generic body for the pull request.
                pr_body = "This pull request adds new files with YAML content, autogenerated by the Jira to GitHub application."
                # Create the pull request using the GitHub manager.
                pr_url = self.github_manager._create_pull_request_logic(
                    dw_project_data.get("pr_title"),
                    pr_body,
                    dw_project_data.get("autoapprove"),
                    dw_project_data.get("new_branch_name")
                )
                self.log_info(f"Pull request creation initiated for: {dw_project_data.get('pr_title')}. URL: {pr_url}")

                # Update Jira issue status based on auto-approval setting.
                if dw_project_data.get("autoapprove") is True:
                    self.add_comment_to_jira_issue(
                        comment_text=f"Created and auto-approved PR at {pr_url}",
                        jira_id=self.jira_id,
                        comment_type="info"
                    )
                    self.change_issue_status(jira_id=self.jira_id, transition_name="Set as done")
                    self.log_info(f"Jira issue {self.jira_id} status changed to 'Set as done'.")
                else:
                    self.add_comment_to_jira_issue(
                        comment_text=f'Created a PR that needs manual approval at {pr_url}',
                        jira_id=self.jira_id,
                        comment_type="manual"
                    )
                    self.change_issue_status(jira_id=self.jira_id, transition_name="Set as to be reviewed")
                    self.log_info(f"Jira issue {self.jira_id} status changed to 'Set as to be reviewed'.")

        except GcpProvisioningError as e:
            # Catch and handle errors specific to GCP provisioning or related GitHub operations.
            self.log_error(f"GCP provisioning or GitHub push failed: {e}")
            self.add_comment_to_jira_issue(comment_text=str(e), jira_id=self.jira_id, comment_type="error")
            self.change_issue_status(jira_id=self.jira_id, transition_name="Set as blocked")
            raise # Re-raise the exception to propagate the error.
        except Exception as e:
            # Catch any other unexpected errors during the GitHub push process.
            self.log_error(f"An unexpected error occurred during GitHub push: {traceback.format_exc()}")
            self.add_comment_to_jira_issue(comment_text=f"An unexpected error occurred during GitHub push: {e}", jira_id=self.jira_id, comment_type="error")
            self.change_issue_status(jira_id=self.jira_id, transition_name="Set as blocked")
            raise # Re-raise the exception.

