import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List, Optional
import re
import yaml
import base64


# Import the base logging class.
from app.logger import AppLogger # Assuming AppLogger is defined in app/logger.py



DEBUG: bool = os.getenv('DEBUG', True) # Controls debug logging and potentially other debug behaviors.
# ORG_ID is the Google Cloud Organization ID. It changes based on DEBUG mode.
if DEBUG is True:
    ORG_ID: str = os.getenv('ORG_ID_DEBUG', '1234567890')
else:
    ORG_ID: str = os.getenv('ORG_ID', '1234567890')


# Define the default branch name for GitHub operations.
BRANCH_NAME: str = os.getenv('BRANCH_NAME', 'main')

# Import Google Cloud Asset Inventory client.
from google.cloud import asset_v1


class BaseProvisioner(ABC, AppLogger): # Inherit from AppLogger to use logging methods
    """
    Abstract Base Class for provisioning workflows.

    This class defines the common structure and abstract methods that all
    concrete provisioner implementations (e.g., for GCP projects, folders)
    must adhere to. It also provides utility methods common to provisioning
    tasks, such as YAML encoding and name formatting for labels.

    Inherits:
        ABC: Abstract Base Class for defining abstract methods.
        AppLogger: Provides logging functionalities (log_info, log_error, etc.).
    """

    def __init__(self):
        """
        Initializes the BaseProvisioner.
        Calls the constructor of the parent AppLogger class.
        Sets the default branch name for GitHub operations.
        """
        super().__init__() # Initialize the base AppLogger class.
        self.branch_name = BRANCH_NAME # Default Git branch name for operations.

    @abstractmethod
    def _validate_jira_request(self) -> None:
        """
        Abstract method to perform validation specific to the type of provisioning request.
        Concrete subclasses must implement this method to validate the extracted Jira data.
        """
        pass # Placeholder for implementation in subclasses.

    @abstractmethod
    def _get_request_comment_message(self) -> str:
        """
        Abstract method to generate a summary message for Jira comments
        after a request has been validated or processed.
        Concrete subclasses must implement this to provide relevant feedback.

        Returns:
            str: A formatted string containing a summary of the request details.
        """
        pass # Placeholder for implementation in subclasses.

    @abstractmethod
    def _built_terraform_yamls(self) -> None:
        """
        Abstract method to generate an object containing GitHub payload configurations
        for Terraform YAML files. This method is responsible for creating the
        Terraform configuration files based on the parsed Jira request data.
        Concrete subclasses must implement this.
        """
        pass # Placeholder for implementation in subclasses.

    @staticmethod
    def encode_yaml_file(yaml_data: Dict[str, Any]) -> str:
        """
        Encodes a Python dictionary into a base64-encoded YAML string.
        This is typically used before sending YAML content to APIs that require base64 encoding.

        Args:
            yaml_data (Dict[str, Any]): The dictionary containing data to be converted to YAML.

        Returns:
            str: The base64-encoded string representation of the YAML content.
        """
        # Dump the dictionary to a YAML string with 2-space indentation.
        yaml_string = yaml.dump(yaml_data, indent=2)
        # Encode the YAML string to UTF-8 bytes, then base64 encode it, and finally decode to a string.
        yaml_content_encoded = base64.b64encode(yaml_string.encode('utf-8')).decode('utf-8')
        return yaml_content_encoded

    def format_for_label_system(self, name: str) -> str:
        """
        Formats a given string for use in a label system (e.g., GCP labels).
        Converts the string to lowercase and replaces one or more whitespace
        characters with a single underscore.

        Args:
            name (str): The input string to be formatted.

        Returns:
            str: The formatted string suitable for labels. Returns an empty string
                 if the input is not a string.
        """
        if not isinstance(name, str):
            # Log a warning if a non-string input is received for formatting.
            self.log_warning(f"Received non-string input for label formatting: {type(name)}. Returning empty string.")
            return ""

        # Convert the name to lowercase.
        formatted_name = name.lower()
        # Replace one or more whitespace characters with a single underscore.
        return re.sub(r'\s+', '_', formatted_name)


class HierarchyrProvisioner(BaseProvisioner):
    """
    HierarchyrProvisioner Class

    This class extends BaseProvisioner and provides common functionalities
    for provisioning resources within a GCP hierarchy (folders and projects).
    It interacts with the Google Cloud Asset Inventory API to list existing
    resources and check for resource existence.

    Inherits:
        BaseProvisioner: Provides abstract methods and common utilities.
    """

    def __init__(self):
        """
        Initializes the HierarchyrProvisioner.
        Calls the constructor of the parent BaseProvisioner class.
        Initializes the Google Cloud Asset Inventory client and fetches
        a list of existing projects and folders under the configured organization.
        """
        super().__init__() # Initialize the base BaseProvisioner (and AppLogger).
        self.client = asset_v1.AssetServiceClient() # Google Cloud Asset Inventory client.
        self.parent = f"organizations/{ORG_ID}" # The parent organization ID for asset listing.
        self.assets = self._list_projects_and_folders() # List of all projects and folders under the organization.

    def _list_projects_and_folders(self) -> List[Dict[str, Any]]:
        """
        Lists all projects and folders directly under the configured Google Cloud organization
        using the Cloud Asset Inventory API. The results are stored in `self.assets`.

        Returns:
            list: A list of asset dictionaries. Each dictionary represents a project or a folder
                  and contains its metadata. Returns an empty list on error or if no assets are found.
        """
        assets = []
        # Define the asset types to retrieve.
        asset_types = [
            "cloudresourcemanager.googleapis.com/Project",
            "cloudresourcemanager.googleapis.com/Folder"
        ]
        # Create the request object for listing assets.
        request = {"parent": self.parent, "asset_types": asset_types, "content_type": "RESOURCE"}

        try:
            # Send the request to list assets and iterate through the paged results.
            paged_result = self.client.list_assets(request=request)
            for page in paged_result.pages:
                for asset in page.assets:
                    assets.append(asset)
            self.log_info(f"Successfully listed {len(assets)} projects and folders under {self.parent}.")
            return assets
        except Exception as e:
            # Log any errors encountered during asset listing.
            self.log_error(f"Error listing projects and folders under {self.parent}: {e}")
            return []

    def check_if_resource_exist(self, resource_name: str, resource_type: str = "cloudresourcemanager.googleapis.com/Folder") -> Optional[str]:
        """
        Checks if a resource with the given display name/ID and type exists
        within the assets fetched from the Cloud Asset Inventory.

        Args:
            resource_name (str): The display name (for Folder) or display name/ID (for Project)
                                 of the resource to check for existence.
            resource_type (str, optional): The Cloud Asset Inventory type of the resource.
                                           Defaults to "cloudresourcemanager.googleapis.com/Folder".

        Returns:
            Optional[str]: The full resource name (e.g., "folders/12345" or "projects/my-project-id")
                           of the found resource if it exists, otherwise None.
        """
        for asset in self.assets:
            # Check if the asset type matches the requested resource type.
            if asset.asset_type == resource_type:
                data = asset.resource.data # Access the resource data for display name/ID.
                # For Folders, compare by 'displayName'.
                if resource_type == "cloudresourcemanager.googleapis.com/Folder" and data.get("displayName") == resource_name:
                    self.log_info(f"Found existing folder '{resource_name}' (type: {resource_type}) with full name: {asset.name}")
                    return asset.name
                # For Projects, compare by 'name' (e.g., "projects/project-id") or 'projectId'.
                elif resource_type == "cloudresourcemanager.googleapis.com/Project" and (data.get("name") == f"projects/{resource_name}" or data.get("projectId") == resource_name):
                    self.log_info(f"Found existing project '{resource_name}' (type: {resource_type}) with full name: {asset.name}")
                    return asset.name
        self.log_info(f"Resource '{resource_name}' (type: {resource_type}) not found.")
        return None

    def _format_label_elements(self) -> None:
        """
        Formats specific configuration elements (defined in `self.elements_to_format`)
        for use as labels. It applies the `format_for_label_system` method to these elements.
        Logs a warning if an element specified for formatting is not found in `self.config_data`.
        """
        # Iterate through the list of elements that need to be formatted for labels.
        # `self.elements_to_format` is expected to be defined in concrete subclasses.
        for element in getattr(self, 'elements_to_format', []): # Use getattr for safety
            if element in self.config_data:
                # Apply the label formatting.
                self.config_data[element] = self.format_for_label_system(self.config_data[element])
                self.log_info(f"Formatted '{element}' for labels: {self.config_data[element]}")
            else:
                self.log_warning(f"Key '{element}' not found in config_data for formatting. Skipping.")

    def _extract_folder_id(self, parent_folder_id_match: Optional[str]) -> Optional[str]:
        """
        Extracts the numerical folder ID from a full folder resource name string.
        Expected format: "folders/12345".

        Args:
            parent_folder_id_match (Optional[str]): The full folder resource name string
                                                    (e.g., "folders/12345") or None.

        Returns:
            Optional[str]: The formatted folder ID string (e.g., "folders/12345") if found,
                           otherwise None.
        """
        if parent_folder_id_match:
            # Use regex to find the numerical ID after "folders/".
            match = re.search(r"folders/(\d+)$", parent_folder_id_match)
            if match:
                parent_folder_id = f"folders/{match.group(1)}" # Reconstruct with "folders/" prefix.
                self.log_info(f"Extracted parent folder ID: {parent_folder_id}")
                return parent_folder_id
            else:
                self.log_error(f"Warning: Could not extract folder ID from '{parent_folder_id_match}'. Invalid format.")
                return None
        self.log_info("No parent folder ID match provided.")
        return None

    def extract_dw_environment(self, text: str) -> Optional[str]:
        """
        Extracts the environment string (e.g., "dev", "prod") from a given text
        following the pattern "^dw-" and before the next hyphen.

        Args:
            text (str): The input string to search within (e.g., "dw-dev-myproject").

        Returns:
            Optional[str]: The extracted environment string (lowercase) if the pattern is found
                           at the beginning of the string, otherwise None.
        """
        # Use regex to match the pattern "dw-<environment>-" at the beginning of the string.
        match = re.match(r"^dw-([a-z]+)-", text)
        if match:
            extracted_env = match.group(1)
            self.log_info(f"Extracted Datawave environment: '{extracted_env}' from '{text}'.")
            return extracted_env
        self.log_info(f"No Datawave environment found in '{text}' matching pattern '^dw-([a-z]+)-'.")
        return None

