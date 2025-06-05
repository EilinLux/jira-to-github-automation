from __future__ import annotations

import json
import requests
from typing import Optional
import traceback

from app.logger import AppLogger

      

class JiraCommenterAndStatusUpdater(AppLogger):
    """
    JiraCommenterAndStatusUpdater Class

    This class extends the functionality of AppLogger to specifically handle
    the preparation of detailed descriptions for Jira comments. It is designed
    to format project creation details into a readable comment string, which
    can then be added to a Jira issue.

    It inherits Jira connection and logging capabilities from the AppLogger base class.

    Attributes:
        config_data (dict): A dictionary containing configuration data,
                            such as issue key, folder name, project type, etc.
                            This is expected to be passed during initialization
                            or set as an instance variable.
        dw_env_project_name_list (list): A list of project names for different
                                         Datawave environments.
    """

    def prepare_ticket_description_for_commenting(self, comment_type: str = 'project') -> str:
        """
        Generates a schematic description of project creation details, formatted
        for inclusion as a comment in a Jira ticket.

        The content of the description varies based on the `comment_type`.
        Currently supports 'project' type, which includes environment and budget details.

        Args:
            comment_type (str): The type of comment to prepare. Defaults to 'project'.
                                 This determines the specific details included in the description.

        Returns:
            str: A multi-line string containing the formatted description,
                 ready to be added as a Jira comment.
        """
        issue_key = self.config_data.get('ISSUE_KEY', 'N/A')
        folder_name = self.config_data.get('FOLDER_NAME', 'N/A')
        project_type = self.config_data.get('PROJECT_TYPE', 'N/A')
        project_type_folder = self.config_data.get('PROJECT_TYPE_FOLDER', 'N/A')
        data_security = self.config_data.get('DATASECURITY', 'N/A')

        description_parts = [
            f"*Jira Issue:* 🔑 {issue_key}",
            f"*Target Folder:* 📂 {folder_name}",
            f"*Project Type:* 🏷️ {project_type}",
            f"*Project Type Folder:* 🗂️ {project_type_folder}"]

        if comment_type=='project':
            description_parts.extend([
                f"*Data Security Level:* {data_security} 🛡️",
                "*Target Environments:* 🌐",
            ])

            environment_details = []
            for dw_env_project_name in self.dw_env_project_name_list:
                env = ResourceValidator.extract_dw_environment(dw_env_project_name) 
                budget_key = f"BUDGET_{env.upper()}"
                budget = self.config_data.get(budget_key, 'N/A')
                environment_details.append(f"- *{env.upper()}*: Name: `{dw_env_project_name}`, Budget (euros): `{budget}`")


            description_parts.extend(environment_details)

        return "\n".join(description_parts)


