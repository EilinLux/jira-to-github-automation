from app.provisioners.base import HierarchyrProvisioner
from app.logger import AppLogger
import re
from app.exceptions import GcpProvisioningError

from typing import Dict, Any 


class GcpFolderProvisioner(HierarchyrProvisioner):
    """
    GcpFolderProvisioner Class

    This class is a concrete implementation of a provisioner specifically designed
    for creating new Google Cloud Platform (GCP) folders. It extends `HierarchyrProvisioner`
    to leverage common functionalities for interacting with the GCP resource hierarchy
    (like checking for existing resources).

    It handles the validation of Jira request data for folder creation,
    generates the corresponding Terraform YAML configuration, and prepares
    messages for Jira comments.

    Attributes:
        config_data (Dict[str, Any]): A dictionary containing the parsed configuration
                                      data extracted from the Jira webhook payload.
                                      This data drives the folder provisioning process.
        logger (AppLogger): An instance of the AppLogger for logging messages.
    """

    def __init__(self, config_data: Dict[str, Any]):
        """
        Initializes the GcpFolderProvisioner with the parsed configuration data.
        Calls the constructor of the parent `HierarchyrProvisioner` class.

        Args:
            config_data (Dict[str, Any]): The configuration data extracted from the Jira issue.
        """
        super().__init__() # Initialize the parent HierarchyrProvisioner (which also initializes AppLogger).
        self.config_data = config_data # Store the parsed configuration data.


    def _get_request_comment_message(self) -> str:
        """
        Generates a formatted summary message about the folder creation request.
        This message is intended to be posted as a comment on the Jira issue.

        Returns:
            str: A multi-line string summarizing the folder creation request details.
        """
        # Retrieve relevant data from config_data, providing 'N/A' as a fallback.
        issue_key = self.config_data.get('ISSUE_KEY', 'N/A')
        folder_name = self.config_data.get('FOLDER_NAME', 'N/A')
        project_type = self.config_data.get('PROJECT_TYPE', 'N/A')
        project_type_folder = self.config_data.get('PROJECT_TYPE_FOLDER', 'N/A')

        # Create a list of formatted description parts, using emojis for clarity.
        description_parts = [
            f"*Jira Issue:* 🔑 {issue_key}",
            f"*Target Folder:* 📂 {folder_name}",
            f"*Project Type:* 🏷️ {project_type}",
            f"*Project Type Folder:* 🗂️ {project_type_folder}"
        ]
        # Join the parts with newline characters to form the final message.
        return "\n".join(description_parts)

    def _validate_folder_name_uniqueness(self) -> None:
        """
        Validates that the requested folder name does not already exist in the
        Google Cloud resource hierarchy. It uses the `check_if_resource_exist`
        method inherited from `HierarchyrProvisioner`.

        Raises:
            ValueError: If a folder with the specified name already exists.
        """
        folder_name = self.config_data['FOLDER_NAME']
        self.log_info(f"Checking if folder '{folder_name}' already exists.")
        # Check if the folder exists by its display name.
        if self.check_if_resource_exist(folder_name, resource_type="cloudresourcemanager.googleapis.com/Folder"):
            # If it exists, log an error and raise a ValueError.
            error_message = f"Folder '{folder_name}' exists already in the resource hierarchy."
            self.log_error(error_message)
            raise ValueError(error_message)
        self.log_info(f"Folder '{folder_name}' does not exist. Proceeding with creation validation.")

    def _extract_project_type_folder_name(self) -> str:
        """
        Extracts and validates the ID of the parent folder (e.g., 'poc', 'sandbox')
        under which the new folder will be created. It checks if this parent folder
        exists in the GCP hierarchy.

        Returns:
            str: The full resource name of the parent folder (e.g., "folders/1234567890").

        Raises:
            GcpProvisioningError: If the specified parent folder does not exist.
        """
        folder_name = self.config_data["PROJECT_TYPE_FOLDER"]
        self.log_info(f"Attempting to retrieve ID for parent folder '{folder_name}'.")
        # Check if the parent folder exists and extract its ID.
        project_type_folder_name = self._extract_folder_id(
            self.check_if_resource_exist(folder_name, resource_type="cloudresourcemanager.googleapis.com/Folder")
        )
        if not project_type_folder_name:
            # If the parent folder is not found, log an error and raise GcpProvisioningError.
            error_message = f"Parent folder '{folder_name}' does not exist in the resource hierarchy. Cannot create sub-folder."
            self.log_error(error_message)
            raise GcpProvisioningError(error_message)
        else:
            self.log_info(f"Retrieved Parent Folder ID for '{folder_name}' as '{project_type_folder_name}'. Proceeding.")
            return project_type_folder_name

    def _validate_jira_request(self) -> None:
        """
        Performs comprehensive validation of the Jira request for GCP folder provisioning.
        This includes checking for folder name uniqueness and the existence of the parent folder.

        Raises:
            GcpProvisioningError: If any validation step fails.
            Exception: Catches and re-raises any unexpected exceptions during validation.
        """
        try:
            self.log_info("Starting validation of Jira request for GCP folder provisioning.")
            # Validate that the new folder name is unique.
            self._validate_folder_name_uniqueness()

            # Extract and validate the parent folder ID.
            parent_folder_id = self._extract_project_type_folder_name()
            # Store the extracted parent folder ID in config_data for later use in YAML generation.
            self.config_data["PARENT_FOLDER_ID"] = parent_folder_id
            self.log_info("Jira request validation for GCP folder provisioning completed successfully.")

        except GcpProvisioningError as e:
            # Re-raise specific provisioning errors.
            self.log_error(f"GCP folder provisioning validation failed: {e}")
            raise
        except ValueError as e:
            # Re-raise specific value errors (e.g., from uniqueness check).
            self.log_error(f"Validation error during GCP folder provisioning: {e}")
            raise GcpProvisioningError(f"Validation error: {e}")
        except Exception as e:
            # Catch any other unexpected exceptions and re-raise as a generic provisioning error.
            self.log_error(f"An unexpected error occurred during GCP folder provisioning validation: {e}")
            raise GcpProvisioningError(f"An unexpected error occurred during validation: {e}")


    def build_project_folder_terraform_yaml(self, config_data: Dict[str, Any], folder_parent_id: str) -> Dict[str, Any]:
        """
        Builds the Terraform YAML configuration for creating a new GCP folder.

        Args:
            config_data (Dict[str, Any]): The configuration data for the folder,
                                         including FOLDER_NAME, PROJECT_TYPE, PROJECT_TYPE_FOLDER.
            folder_parent_id (str): The full resource ID of the parent folder (e.g., "folders/12345").

        Returns:
            Dict[str, Any]: A dictionary representing the Terraform configuration for the folder.
        """
        self.log_info(f"Building Terraform YAML for folder '{config_data['FOLDER_NAME']}' under parent '{folder_parent_id}'.")
        return {
            "parent": folder_parent_id, # The parent folder ID where the new folder will reside.
            "name": config_data["FOLDER_NAME"], # The display name of the new folder.
            "labels": { # GCP labels for organizing and categorizing the folder.
                "project_type": self.format_for_label_system(config_data["PROJECT_TYPE"]), # e.g., "internal" or "client".
                "project_sub_type": self.format_for_label_system(config_data["PROJECT_TYPE_FOLDER"]), # e.g., "asset", "sandbox", "poc".
                "project_name_folder": self.format_for_label_system(config_data["FOLDER_NAME"]), # The formatted name of the folder itself.
            }
        }

    def _built_terraform_yamls(self) -> None:
        """
        Generates the Terraform YAML configuration for the new GCP folder
        and prepares the GitHub payload for committing this configuration.

        This method fulfills the abstract method requirement from `BaseProvisioner`.

        Raises:
            GcpProvisioningError: If required configuration data is missing or if
                                  the parent folder ID is not available.
        """
        self.log_info("Starting to build Terraform YAMLs for folder creation.")
        # Ensure that PARENT_FOLDER_ID is available from previous validation steps.
        parent_folder_id = self.config_data.get("PARENT_FOLDER_ID")
        if not parent_folder_id:
            error_message = "Parent folder ID is missing in config_data. Cannot build Terraform YAMLs."
            self.log_error(error_message)
            raise GcpProvisioningError(error_message)

        # Build the Terraform YAML content for the folder.
        terraform_yaml_content = self.build_project_folder_terraform_yaml(
            self.config_data, parent_folder_id
        )
        self.log_info(f"Generated Terraform YAML content for folder: {terraform_yaml_content}")

        # Encode the YAML content to base64.
        encoded_yaml = self.encode_yaml_file(terraform_yaml_content)

        # Define the file path for the Terraform YAML in the GitHub repository.
        # Example path: 'gcp/folders/my-new-folder/folder.yaml'
        file_path = f"gcp/folders/{self.format_for_label_system(self.config_data['FOLDER_NAME'])}/folder.yaml"
        commit_message = f"feat: Add GCP folder '{self.config_data['FOLDER_NAME']}' via Jira {self.config_data.get('ISSUE_KEY')}"
        pr_title = f"feat: GCP Folder '{self.config_data['FOLDER_NAME']}' - Jira {self.config_data.get('ISSUE_KEY')}"
        new_branch_name = f"feature/jira-{self.config_data.get('ISSUE_KEY')}-folder-{self.format_for_label_system(self.config_data['FOLDER_NAME'])}"

        # Prepare the GitHub payload structure.
        # This structure is designed to be consumed by the GitHubHandler.
        self.github_payload = {
            self.config_data['FOLDER_NAME']: { # Use folder name as a key for this specific folder's data
                "new_branch_name": new_branch_name,
                "pr_title": pr_title,
                "autoapprove": self.config_data.get("AUTO_APPROVE", False), # Assuming AUTO_APPROVE comes from Jira config
                "yaml_content_encoded": {
                    "folder_yaml": {
                        "path": file_path,
                        "commit_message": commit_message,
                        "file": encoded_yaml
                    }
                }
            }
        }
        self.log_info("Terraform YAMLs for folder creation built and GitHub payload prepared.")

