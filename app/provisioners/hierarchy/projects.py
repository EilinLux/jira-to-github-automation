from app.provisioners.base import HierarchyrProvisioner
from app.exceptions import GcpProvisioningError
# Import configuration mappings for environments and data security levels.
from configs.jira.configurations import env_mapping, data_security_mapping
from typing import Dict, Any, List, Optional
import os

# Define a global budget limit for auto-approval in development environments.
BUDGET_LIMIT: int = os.getenv('BUDGET_LIMIT', 150)


class GcpProjectProvisioner(HierarchyrProvisioner):
    """
    GcpProjectProvisioner Class

    This concrete provisioner handles the end-to-end provisioning flow for a new
    GCP Project based on a Jira request. It extends `HierarchyrProvisioner`
    to leverage common functionalities for interacting with the GCP resource
    hierarchy and `AppLogger` for logging.

    It performs detailed validation of project-specific Jira request data,
    generates Terraform YAML configurations for both the project and its budget,
    and prepares the necessary payload for GitHub operations (committing files
    and creating pull requests).

    Attributes:
        config_data (Dict[str, Any]): A dictionary containing the parsed configuration
                                      data extracted from the Jira webhook payload.
                                      This data drives the project provisioning process.
        logger (AppLogger): An instance of the AppLogger for logging messages.
        elements_to_format (List[str]): A list of keys in `config_data` whose values
                                        should be formatted for labels.
        dw_env_project_name_list (List[str]): A list to store the generated
                                              Datawave environment-specific project names.
        env_mapping (Dict[str, str]): A mapping from environment names (e.g., "dev")
                                      to their corresponding folder names (e.g., "development").
        github_payload (Dict[str, Any]): A dictionary that will be populated with
                                         the structured data required for GitHub operations.
    """

    def __init__(self, config_data: Dict[str, Any]):
        """
        Initializes the GcpProjectProvisioner with the parsed configuration data.
        Calls the constructor of the parent `HierarchyrProvisioner` class.

        Args:
            config_data (Dict[str, Any]): The configuration data extracted from the Jira issue.
        """
        super().__init__() # Initialize the parent HierarchyrProvisioner (which also initializes AppLogger).
        self.config_data = config_data # Store the parsed configuration data.

        # Define elements in config_data that need special formatting for GCP labels.
        self.elements_to_format = ["ENGAGEMENT_MANAGER", "PROJECT_NAME", "FOLDER_NAME", "WBS", "DATASECURITY"]
        self.dw_env_project_name_list: List[str] = [] # List to store generated project IDs (e.g., dw-dev-myproject).
        self.env_mapping = env_mapping # Mapping for environment names to folder names.
        self.github_payload: Dict[str, Any] = {} # Dictionary to store GitHub-related payload for each project.

    def _get_request_comment_message(self) -> str:
        """
        Generates a formatted summary message about the project creation request.
        This message is intended to be posted as a comment on the Jira issue.
        It includes general project details and specific details for each target environment.

        Returns:
            str: A multi-line string summarizing the project creation request details.
        """
        # Retrieve general project details from config_data, providing 'N/A' as a fallback.
        issue_key = self.config_data.get('ISSUE_KEY', 'N/A')
        folder_name = self.config_data.get('FOLDER_NAME', 'N/A')
        project_type = self.config_data.get('PROJECT_TYPE', 'N/A')
        project_type_folder = self.config_data.get('PROJECT_TYPE_FOLDER', 'N/A')
        data_security = self.config_data.get('DATASECURITY', 'N/A')

        # Create a list of initial description parts, using emojis for clarity.
        description_parts = [
            f"*Jira Issue:* 🔑 {issue_key}",
            f"*Target Folder:* 📂 {folder_name}",
            f"*Project Type:* 🏷️ {project_type}",
            f"*Project Type Folder:* 🗂️ {project_type_folder}",
            f"*Data Security Level:* {data_security} 🛡️",
            "*Target Environments:* 🌐",
        ]

        environment_details = []
        # Iterate through the list of generated Datawave environment project names.
        for dw_env_project_name in self.dw_env_project_name_list:
            # Extract the environment name (e.g., "dev", "test", "prod") from the project name.
            env = self.extract_dw_environment(dw_env_project_name)
            # Construct the key for retrieving the budget for this specific environment.
            budget_key = f"BUDGET_{env.upper()}"
            # Retrieve the budget value, defaulting to 'N/A' if not found.
            budget = self.config_data.get(budget_key, 'N/A')
            # Add formatted environment-specific details to the list.
            environment_details.append(f"- *{env.upper()}*: Name: `{dw_env_project_name}`, Budget (euros): `{budget}`")

        # Extend the main description parts with the environment-specific details.
        description_parts.extend(environment_details)

        # Join all parts with newline characters to form the final message.
        return "\n".join(description_parts)

    @staticmethod
    def check_budget_keys(data: Dict[str, Any]) -> bool:
        """
        Checks if for each environment specified in the 'ENVIRONMENT' field of the
        `config_data`, there is a corresponding budget key (e.g., "BUDGET_DEV").

        Args:
            data (Dict[str, Any]): The `config_data` dictionary containing environment
                                   list and budget values.

        Returns:
            bool: True if all environments have a corresponding budget key.

        Raises:
            ValueError: If the `data` dictionary is empty, or if 'ENVIRONMENT' field
                        is missing/empty, or if any environment lacks a budget key.
        """
        if not data:
            raise ValueError("The config_data structure is empty.")

        # Ensure the 'ENVIRONMENT' field exists and is not empty.
        if "ENVIRONMENT" not in data or not data["ENVIRONMENT"]:
            raise ValueError("The 'ENVIRONMENT' field in config_data is empty or missing.")
        else:
            env_list = data["ENVIRONMENT"] # List of environments (e.g., ["dev", "test", "prod"]).

        # Iterate through each environment and check for its corresponding budget key.
        for env in env_list:
            budget_key = f"BUDGET_{env.upper()}"
            if budget_key not in data:
                # If a budget key is missing, raise a ValueError.
                raise ValueError(f"The '{env}' environment has no associated budget key ('{budget_key}'). "
                                 "Please ensure this information is included in the Jira request.")

        return True # All budget keys are present.

    def _validate_folder_existence(self) -> None:
        """
        Validates if the specified parent folder (where the new projects will reside)
        exists in the Google Cloud resource hierarchy.

        Raises:
            ValueError: If the specified folder is not found.
        """
        folder_name = self.config_data['FOLDER_NAME']
        self.log_info(f"Checking if parent folder '{folder_name}' exists.")
        # Use the inherited method to check for folder existence.
        if not self.check_if_resource_exist(folder_name, resource_type="cloudresourcemanager.googleapis.com/Folder"):
            # If the folder does not exist, log an error and raise a ValueError.
            error_message = f"Parent folder '{folder_name}' not found in the resource hierarchy."
            self.log_error(error_message)
            raise ValueError(error_message)
        self.log_info(f"Parent folder '{folder_name}' found. Proceeding with project validation.")

    def _validate_project_name_uniqueness(self, project_name: str, environment: str) -> None:
        """
        Validates that a new GCP project name, constructed with the environment prefix,
        does not already exist in the Google Cloud resource hierarchy.
        Appends the generated project name to `self.dw_env_project_name_list` if unique.

        Args:
            project_name (str): The base project name from Jira (e.g., "myproject").
            environment (str): The environment (e.g., "dev", "test", "prod").

        Raises:
            ValueError: If a project with the constructed name already exists.
        """
        # Construct the full Datawave environment-prefixed project name.
        dw_env_project_name = f'dw-{environment}-{project_name}'
        self.log_info(f"Checking uniqueness for project name '{dw_env_project_name}'.")
        # Check if a project with this name already exists.
        if self.check_if_resource_exist(dw_env_project_name, resource_type="cloudresourcemanager.googleapis.com/Project"):
            # If it exists, log an error and raise a ValueError.
            error_message = f"Project '{dw_env_project_name}' exists already in the resource hierarchy."
            self.log_error(error_message)
            raise ValueError(error_message)

        self.log_info(f"Project '{dw_env_project_name}' does not exist. Proceeding.")
        # Add the unique project name to the list for later use.
        self.dw_env_project_name_list.append(dw_env_project_name)

    def _validate_environment_subfolder(self, folder_name: str, environment: str) -> None:
        """
        Validates if the environment-specific subfolder (e.g., 'development', 'production')
        exists directly under the main parent folder. It also stores the ID of this subfolder
        in `self.config_data` (e.g., `self.config_data['FOLDER_DEV']`).

        Args:
            folder_name (str): The display name of the main parent folder.
            environment (str): The environment (e.g., "dev", "test", "prod").

        Raises:
            ValueError: If no mapping is found for the environment or if the subfolder is not found.
        """
        # Get the expected subfolder display name from the environment mapping.
        subfolder_to_find = self.env_mapping.get(environment)
        if not subfolder_to_find:
            # If no mapping exists for the environment, log a warning and raise an error.
            self.log_warning(f"No folder mapping found for environment '{environment}'.")
            raise ValueError(f"No folder mapping found for environment '{environment}'.")

        self.log_info(f"Checking for subfolder '{subfolder_to_find}' under parent folder '{folder_name}'.")
        # Get the full resource ID of the environment-specific subfolder.
        env_folder_id = self.get_project_subfolder_id(folder_name, subfolder_to_find)
        if env_folder_id:
            # If found, extract the clean folder ID and store it in config_data.
            self.config_data[f"FOLDER_{environment.upper()}"] = self._extract_folder_id(env_folder_id)
            self.log_info(f"ID of subfolder '{subfolder_to_find}' under '{folder_name}': {env_folder_id}")
        else:
            # If the subfolder is not found, log an error and raise a ValueError.
            self.log_error(f"Subfolder '{subfolder_to_find}' not found under '{folder_name}'.")
            raise ValueError(f"Subfolder '{subfolder_to_find}' not found under '{folder_name}'.")

    def validate_folder_and_projects_name(self) -> None:
        """
        Orchestrates the validation of the main parent folder's existence,
        the uniqueness of each environment-specific project name, and the
        existence of environment-specific subfolders.

        Raises:
            Exception: Catches and re-raises any exceptions occurring during validation.
        """
        try:
            self.log_info("Starting validation of folder and project names.")
            # Validate the existence of the main parent folder.
            self._validate_folder_existence()

            project_name = self.config_data["PROJECT_NAME"]
            # Iterate through each environment specified in the Jira request.
            for each_env in self.config_data["ENVIRONMENT"]:
                # Validate uniqueness of the project name for the current environment.
                self._validate_project_name_uniqueness(project_name, each_env)
                # Validate the existence of the environment-specific subfolder.
                self._validate_environment_subfolder(self.config_data['FOLDER_NAME'], each_env)
            self.log_info("Folder and project name validation completed successfully.")
        except Exception as e:
            # Log the error and re-raise to be handled by the AppManager.
            self.log_error(f"Error during folder and project name validation: {e}")
            raise GcpProvisioningError(f"Validation error during folder/project name check: {e}")


    def get_project_subfolder_id(self, parent_folder_name: str, subfolder_name: str) -> Optional[str]:
        """
        Retrieves the full resource ID (e.g., "folders/12345") of a subfolder
        given its parent folder's display name and the subfolder's display name.
        It searches within the assets fetched from Cloud Asset Inventory.

        Args:
            parent_folder_name (str): The display name of the parent folder.
            subfolder_name (str): The display name of the subfolder to find.

        Returns:
            Optional[str]: The full resource name (folder ID) of the subfolder if found
                           under the specified parent folder, otherwise None.

        Raises:
            Exception: If the parent folder is not found, preventing subfolder search.
        """
        self.log_info(f"Searching for subfolder '{subfolder_name}' under parent '{parent_folder_name}'.")
        # First, get the full resource ID of the parent folder.
        parent_folder_id_match = self.check_if_resource_exist(parent_folder_name, resource_type="cloudresourcemanager.googleapis.com/Folder")
        if not parent_folder_id_match:
            # If the parent folder is not found, log an error and raise an exception.
            error_message = f"Parent folder '{parent_folder_name}' not found. Cannot search for subfolder '{subfolder_name}'."
            self.log_error(error_message)
            raise GcpProvisioningError(error_message)

        # Extract the clean folder ID from the matched parent folder resource name.
        parent_folder_id = self._extract_folder_id(parent_folder_id_match)
        if not parent_folder_id:
            error_message = f"Could not extract ID for parent folder '{parent_folder_name}'. Cannot search for subfolder '{subfolder_name}'."
            self.log_error(error_message)
            raise GcpProvisioningError(error_message)

        # Iterate through all fetched assets to find the subfolder.
        for asset in self.assets:
            # Check if the asset is a folder and its display name matches the subfolder name.
            if (asset.asset_type == "cloudresourcemanager.googleapis.com/Folder" and
                    asset.resource.data.get("displayName") == subfolder_name):
                # Check if the parent_folder_id is in the asset's ancestors list.
                # Ancestors are typically in the format "folders/ID" or "organizations/ID".
                if asset.ancestors and parent_folder_id in asset.ancestors:
                    self.log_info(f"Subfolder '{subfolder_name}' found under '{parent_folder_name}'. ID: {asset.name}")
                    return asset.name
                # Fallback for direct parent relationship if ancestors list is not comprehensive or direct parent is needed.
                elif asset.resource.data.get("parent") == parent_folder_id:
                    self.log_info(f"Subfolder '{subfolder_name}' found under '{parent_folder_name}'. ID: {asset.name}")
                    return asset.name

        self.log_info(f"Subfolder '{subfolder_name}' not found directly under folder '{parent_folder_name}'.")
        return None # Return None if the subfolder is not found under the specified parent.


    def _validate_jira_request(self) -> None:
        """
        Orchestrates the complete validation process for a Jira project creation request.
        This includes formatting labels, validating folder and project names,
        and checking budget key consistency.

        Raises:
            GcpProvisioningError: If any validation step fails.
        """
        self.log_info("Starting comprehensive validation of Jira request for GCP project provisioning.")
        try:
            # Format specific elements in config_data for use as GCP labels.
            self._format_label_elements()
            # Validate the existence of the main folder and uniqueness/existence of project names/subfolders.
            self.validate_folder_and_projects_name()
            # Check if all specified environments have corresponding budget keys.
            self.check_budget_keys(self.config_data)
            self.log_info("Jira request validation for GCP project provisioning completed successfully.")
        except Exception as e:
            # Log the error and re-raise it as a GcpProvisioningError for consistent handling.
            self.log_error(f"GCP project provisioning validation failed: {e}")
            raise GcpProvisioningError(f"Project provisioning validation error: {e}")


    def build_project_terraform_yaml(self, dw_env_project_name: str, env: str, data_type_tag: str) -> Dict[str, Any]:
        """
        Builds the Terraform YAML configuration for a single GCP project.
        This includes parent folder, Shared VPC settings, billing budgets,
        tag bindings, and various labels.

        Args:
            dw_env_project_name (str): The full Datawave environment-prefixed project ID.
            env (str): The environment (e.g., "dev", "test", "prod").
            data_type_tag (str): The data type tag (e.g., "data-type/l0").

        Returns:
            Dict[str, Any]: A dictionary representing the Terraform configuration for the project.
        """
        self.log_info(f"Building Terraform YAML for project '{dw_env_project_name}' in environment '{env}'.")
        # Get the specific folder ID for the current environment from config_data.
        env_folder = f"FOLDER_{env.upper()}"

        return {
            "parent": self.config_data[env_folder], # Parent folder for this specific environment.
            "shared_vpc_service_config": { # Configuration for Shared VPC.
                "host_project": f"{env}-spoke-0", # Example host project for Shared VPC.
                "network_users": [
                    "gcp-devops" # Service accounts or groups that can use the shared VPC.
                ]
            },
            "billing_budgets": [ # List of billing budgets to apply to this project.
                dw_env_project_name # Reference to the budget resource for this project.
            ],
            "tag_bindings": { # GCP Tag Bindings for policy enforcement.
                "data-type": data_type_tag # e.g., "data-type/l0" based on data security.
            },
            "labels": { # GCP Labels for organization and cost allocation.
                "environment": env, # e.g., "dev", "test", "prod".
                "project_type": self.config_data["PROJECT_TYPE"], # e.g., "internal" or "client".
                "project_sub_type": self.config_data["PROJECT_TYPE_FOLDER"], # e.g., "asset", "sandbox", "poc".
                "project_name_folder": self.config_data["FOLDER_NAME"], # Name of the overarching folder.
                "project_name": dw_env_project_name, # Complete project ID with environment prefix.
                "data_security": self.config_data["DATASECURITY"], # Data security level.
                "engagement_manager": self.config_data["ENGAGEMENT_MANAGER"], # Engagement manager's name.
                "wbs": self.config_data["WBS"] # Work Breakdown Structure code.
            }
        }

    def build_budget_terraform_yaml(self, dw_env_project_name: str, env: str) -> Dict[str, Any]:
        """
        Builds the Terraform YAML configuration for a single GCP billing budget
        associated with a project.

        Args:
            dw_env_project_name (str): The full Datawave environment-prefixed project ID.
            env (str): The environment (e.g., "dev", "test", "prod").

        Returns:
            Dict[str, Any]: A dictionary representing the Terraform configuration for the budget.
        """
        self.log_info(f"Building Terraform YAML for budget of project '{dw_env_project_name}'.")
        # Get the budget amount for the specific environment.
        env_budget_key = f"BUDGET_{env.upper()}"
        return {
            'display_name': f'budget for {dw_env_project_name}', # Display name in Cloud Billing.
            'amount': {
                'units': self.config_data[env_budget_key] # Budget amount in units (e.g., euros).
            },
            'filter': {
                'period': {
                    'calendar': 'MONTH' # Monthly budget period.
                },
                'projects': [
                    dw_env_project_name # The project ID this budget applies to.
                ]
            },
            'threshold_rules': [ # Rules for sending notifications at certain budget thresholds.
                {'percent': 0.5}, # Notify at 50% of budget.
                {'percent': 0.75} # Notify at 75% of budget.
            ],
            'update_rules': { # Rules for budget notifications and actions.
                'default': {
                    'disable_default_iam_recipients': True, # Disable default billing admins as recipients.
                    'monitoring_notification_channels': [
                        'billing-default' # Custom monitoring notification channel.
                    ]
                }
            }
        }

    @staticmethod
    def allow_autoapprove_on_dev_budget_limit(data_security: str, budget_dev: float) -> bool:
        """
        Determines if a pull request can be auto-approved based on the data security level
        and the development environment's budget. Auto-approval is allowed only for 'l0'
        data security and if the development budget is below a predefined limit.

        Args:
            data_security (str): The data security level (e.g., "l0", "l1", "l2").
            budget_dev (float): The budget allocated for the development environment.

        Returns:
            bool: True if auto-approval is allowed, False otherwise.
        """
        # Auto-approval is restricted to 'l0' data security.
        if data_security == "l0":
            # For 'l0', auto-approval is further restricted by the development budget.
            if budget_dev is not None and budget_dev < BUDGET_LIMIT:
                return True # Auto-approve if budget is within limit.
            else:
                return False # Do not auto-approve if budget exceeds limit or is missing.
        else:
            return False # Do not auto-approve for other data security levels.

    def _built_terraform_yamls(self) -> None:
        """
        Generates the Terraform YAML configurations for each environment-specific project
        and its corresponding budget. It then structures this information into
        `self.github_payload`, which is used to drive GitHub operations (commits and PRs).
        It also determines if auto-approval is allowed for each project.

        This method fulfills the abstract method requirement from `BaseProvisioner`.

        Raises:
            GcpProvisioningError: If any error occurs during YAML generation or payload preparation.
        """
        self.log_info("Starting to build Terraform YAMLs for project creation and budgets.")
        try:
            # Generate a new branch name based on the Jira issue key.
            new_branch_name = f'ticket-{self.config_data["ISSUE_KEY"]}'
            # Get the data type tag based on the data security level.
            data_type_tag = data_security_mapping[self.config_data["DATASECURITY"]]

            # Iterate through each environment-specific project name that was validated earlier.
            # It's important to process 'dev' first if auto-approval is a consideration.
            for dw_env_project_name in self.dw_env_project_name_list:
                self.log_info(f"Processing project: {dw_env_project_name}")

                # Initialize a dictionary for this specific project within the github_payload.
                self.github_payload[dw_env_project_name] = {}
                # Set the pull request title for this project.
                self.github_payload[dw_env_project_name]["pr_title"] = \
                    f'[{self.config_data.get("ISSUE_KEY", "N/A")}] PR for project creation: {dw_env_project_name}'

                # Extract the environment (e.g., "dev") from the project name.
                self.github_payload[dw_env_project_name]["env"] = self.extract_dw_environment(dw_env_project_name)
                self.github_payload[dw_env_project_name]["data_type_tag"] = data_type_tag
                self.github_payload[dw_env_project_name]["new_branch_name"] = new_branch_name

                # Initialize a nested dictionary for encoded YAML content for this project.
                self.github_payload[dw_env_project_name]["yaml_content_encoded"] = {}

                # Loop to build both budget and project YAML files.
                for type_file in ["budget", "project"]:
                    self.github_payload[dw_env_project_name]["yaml_content_encoded"][type_file] = {}
                    if type_file == "budget":
                        # Build and encode the budget Terraform YAML.
                        self.github_payload[dw_env_project_name]["yaml_content_encoded"][type_file]["file"] = \
                            self.encode_yaml_file(self.build_budget_terraform_yaml(
                                dw_env_project_name, self.github_payload[dw_env_project_name]["env"]))
                    elif type_file == "project":
                        # Build and encode the project Terraform YAML.
                        self.github_payload[dw_env_project_name]["yaml_content_encoded"][type_file]["file"] = \
                            self.encode_yaml_file(self.build_project_terraform_yaml(
                                dw_env_project_name, self.github_payload[dw_env_project_name]["env"], data_type_tag))

                    # Set commit message and file path for the current YAML file.
                    self.github_payload[dw_env_project_name]["yaml_content_encoded"][type_file]["commit_message"] = \
                        f'[{self.config_data.get("ISSUE_KEY", "N/A")}] Add configuration {type_file} for {dw_env_project_name} project.'
                    self.github_payload[dw_env_project_name]["yaml_content_encoded"][type_file]["path"] = \
                        f'data/{type_file}s/{dw_env_project_name}.yaml'

                # Determine if auto-approval is allowed for this project.
                # Auto-approval is currently only for 'dev' environment with 'l0' data security and within budget limit.
                if (self.github_payload[dw_env_project_name]["env"] == "dev" and
                        self.allow_autoapprove_on_dev_budget_limit(
                            self.config_data["DATASECURITY"],
                            self.config_data.get("BUDGET_DEV", 0.0))): # Use .get with default for safety
                    self.github_payload[dw_env_project_name]["autoapprove"] = True
                    self.log_info(f"Auto-approval enabled for {dw_env_project_name} (dev, l0, budget within limit).")
                else:
                    self.github_payload[dw_env_project_name]["autoapprove"] = False
                    self.log_info(f"Auto-approval disabled for {dw_env_project_name}.")

            self.log_info("Terraform YAMLs built and GitHub payload prepared for all projects.")

        except Exception as e:
            # Log and re-raise any unexpected errors during YAML building.
            self.log_error(f"An error occurred during building Terraform YAMLs: {e}")
            raise GcpProvisioningError(f"Failed to build Terraform YAMLs: {e}")

