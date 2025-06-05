import os
import traceback
import json 
from google.cloud import logging as cloud_logging
from requests.auth import HTTPBasicAuth
import traceback
import requests
from typing import  Optional
 

# Define the logging name for Google Cloud Logging.
# Read from environment variable LOGGING_NAME, with a default fallback.
logging_name: str = os.getenv('LOGGING_NAME', 'medium-jira-github-automation-func')

# Initialize the Google Cloud Logging client.
logging_client = cloud_logging.Client()

# Jira authentication details.
# These credentials are now read from environment variables for security.
JIRA_USER: str = os.getenv('JIRA_USER', "") # IMPORTANT: Replace with actual USER or ensure env var is set
JIRA_TOKEN: str = os.getenv('JIRA_TOKEN', "") # IMPORTANT: Replace with actual token or ensure env var is set
JIRA_SERVER: str = os.getenv('JIRA_SERVER',  "https://NAME.atlassian.net" ) # IMPORTANT: Replace with actual Jira server URL





class AppLogger():
    """
    AppLogger Class

    This class provides a centralized logging mechanism for the application,
    utilizing Google Cloud Logging. It supports logging messages at INFO,
    ERROR, and WARNING levels.

    It also encapsulates Jira connection details and provides methods
    for interacting with the Jira API, such as adding comments and
    changing issue statuses.

    Attributes:
        logger (google.cloud.logging.Logger): The logger instance for Cloud Logging.
        jira_url (str): The base URL of the Jira instance.
        auth (HTTPBasicAuth): Basic authentication object for Jira API requests.
        headers (dict): HTTP headers for Jira API requests, specifying JSON content.
    """

    def __init__(self):

        """
        Initializes the AppLogger with a Google Cloud Logger instance
        and Jira connection parameters.
        """
        self.logger = logging_client.logger(logging_name)

        # Jira Connection details.
        self.jira_url = JIRA_SERVER
        self.auth =  HTTPBasicAuth(JIRA_USER, JIRA_TOKEN)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def log_info(self, message: str) -> None:
        """
        Log an INFO level message.
        
        Args:
            message (str): The informational message to log.

        """
        self.logger.log_text(f"[INFO] {message}", severity='INFO')

    def log_error(self, message: str) -> None:
        """
        Log an ERROR level message.
        
        Args:
            message (str): The error message to log.

        """
        self.logger.log_text(f"[ERROR] {message}:\n{traceback.format_exc()}", severity='ERROR')

    def log_warning(self, message: str) -> None:
        """
        Log a WARNING level message.
        
        Args:
            message (str): The warning message to log.
        
        Returns:
            None
        """
        self.logger.log_text(f"[WARNING] {message}:\n{traceback.format_exc()}", severity='WARNING')

    def add_comment_to_jira_issue(self, jira_id: str, comment_text: str = "Testing", comment_type="info") -> bool:
        """
        Adds a comment to an existing Jira issue.

        Args:
            comment_text (str): The text of the comment you want to add.

        """
        if comment_type == "error": 
            comment_text = f"❌[ERROR]: {comment_text}"
        elif comment_type == "info": 
            comment_text = f"✅[INFO]: {comment_text}"
        elif comment_type == "manual": 
            comment_text = f"🧑‍🔧[MANUAL APPROVAL]: {comment_text}"

        #  The base URL of Jira instance (e.g., "https://bip-xtech.atlassian.net")
        self.log_info(f"Commenting '{jira_id}' on '{self.jira_url}': {comment_text}")
        url = f"{self.jira_url}/rest/api/2/issue/{jira_id}/comment"
        payload = {"body": comment_text}

        json_payload = json.dumps(payload)

        try:
            response = requests.post(url, auth=self.auth, headers=self.headers, data=json_payload)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            self.log_info(f"Successfully added comment to issue {jira_id}.")

        except requests.exceptions.RequestException as e:
            self.log_error(f"Error adding comment to issue {jira_id}: {e}. Response text: {response.text}")
            raise 
        except Exception as e:
            error_message = f"{traceback.print_exc()}"
            self.log_error(f"An unexpected error occurred while adding comment: {error_message}")
            raise

    def get_transition_id(self, jira_id: str, transition_name: str) -> Optional[str]:
        """
        Retrieves the ID of a specific transition for a given Jira issue.

        This ID is required to change the status of a Jira issue.

        Args:
            jira_id (str): The key of the Jira issue (e.g., "AUTOTEST-123").
            transition_name (str): The name of the desired transition (e.g., "Start Progress", "Done").

        Returns:
            Optional[str]: The ID of the transition if found, otherwise None.
        """

        url = f"{self.jira_url}/rest/api/2/issue/{jira_id}/transitions"
        try:
            response = requests.get(url, auth=self.auth, headers=self.headers)
            response.raise_for_status()
            transitions_data = response.json()


            for transition in transitions_data["transitions"]:
                if transition["name"] == transition_name:
                    self.log_info(f"Found transition ID {transition['id']} for '{transition_name}'")
                    return transition["id"]

            self.log_warning(f"Transition '{transition_name}' not found for issue {jira_id}")
            return None

        except requests.exceptions.RequestException as e:
            self.log_error(f"Error getting transitions for {jira_id}: {e}. Response text: {response.text}")
            return None
        except json.JSONDecodeError as e:
            self.log_error(f"Error decoding JSON response: {e}. Response text: {response.text}")
            return None


    def change_issue_status(self,  transition_name: str, jira_id:str) -> bool:
        """
        Changes the status of a Jira issue.

        Args:
            jira_id (str): The key of the Jira issue to update (e.g., "AUTOTEST-123").
            transition_name (str): The name of the transition to perform (e.g., "In Progress", "Done").

        Returns:
            bool: True if the status was changed successfully, False otherwise.
        """
        transition_id = self.get_transition_id(jira_id, transition_name)
        if transition_id is None:
            self.log_error(f"Failed to get transition ID for '{transition_name}'. Cannot change status of issue {jira_id}")
            return False

        url = f"{self.jira_url}/rest/api/2/issue/{jira_id}/transitions"
        payload = {
            "transition": {
                "id": transition_id,
            }
        }
        json_payload = json.dumps(payload)

        try:
            response = requests.post(url, auth=self.auth, headers=self.headers, data=json_payload)
            response.raise_for_status()
            self.log_info(f"Successfully changed status of issue {jira_id} to '{transition_name}'.")
            return True
        except requests.exceptions.RequestException as e:
            self.log_error(f"Error changing status of issue {jira_id}: {e}. Response text: {response.text}")
            return False
        except Exception as e:
            self.log_error(f"An unexpected error occurred while changing status of issue {jira_id}", exc_info=True)
            return False

