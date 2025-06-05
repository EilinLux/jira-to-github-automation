


import requests
from typing import Optional
import os
import requests
import base64
import yaml
from app.logger import AppLogger


# Define the default branch name for GitHub operations.
BRANCH_NAME: str = os.getenv('BRANCH_NAME', 'main')

class GitHubRepoManager(AppLogger):
    """
    GitHubRepoManager Class

    This class provides a set of methods for interacting with the GitHub API
    to manage a repository. It includes functionalities for creating branches,
    checking pull requests, creating pull requests, enabling auto-merge,
    setting branches for deletion after merge, committing files, and
    retrieving the latest SHA of a branch.

    It inherits logging capabilities from the AppLogger base class.

    Attributes:
        repo_owner (str): The owner of the GitHub repository (e.g., 'octocat').
        repo_name (str): The name of the GitHub repository (e.g., 'Spoon-Knife').
        headers (Dict[str, str]): HTTP headers required for GitHub API authentication
                                   and content type negotiation.
    """
    def create_branch(self, new_branch_name, sha):
        """
        Creates a new branch in the GitHub repository from a specified SHA.

        Args:
            new_branch_name (str): The name of the new branch to create.
            sha (str): The SHA of the commit from which the new branch will be created.

        Returns:
            Dict[str, Any]: The JSON response from the GitHub API,
                            containing details of the newly created reference.
        """
        url = f'https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/git/refs'
        data = {
            'ref': f'refs/heads/{new_branch_name}',
            'sha': sha
        }
        response = requests.post(url, json=data, headers=self.headers)
        return response.json()


    def check_open_pr(self, base_branch_name):
        """
        Checks for open pull requests targeting a specific base branch.

        Args:
            base_branch_name (str): The name of the base branch to check for open PRs against.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing an open pull request.
        """
        url = f'https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls?state=open&base={base_branch_name}'
        response = requests.get(url, headers=self.headers)
        return response.json()

    def create_pull_request(self, title, head_branch_name, base_branch_name, body='This PR updates the file content.', auto_merge=True, delete_branch_after_merge=True):

        """
        Creates a new pull request in the GitHub repository.

        Optionally enables auto-merge and sets the head branch to be deleted after merge.

        Args:
            title (str): The title of the pull request.
            head_branch_name (str): The name of the branch containing the changes to be merged.
            base_branch_name (str): The name of the branch into which the changes will be merged.
            body (str): The description of the pull request. Defaults to a generic message.
            auto_merge (bool): If True, attempts to enable auto-merge for the PR. Defaults to True.
            delete_branch_after_merge (bool): If True, attempts to set the head branch
                                              to be deleted after the PR is merged. Defaults to True.

        Returns:
            Optional[Dict[str, Any]]: The JSON response from the GitHub API for the created PR,
                                      or None if an error occurs.
        """

        url = f'https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls'
        data = {
            'title': title,
            'head': head_branch_name,
            'base': base_branch_name,
            'body': body
        }
        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            pull_request_data = response.json()
            self.log_info(f"Pull request created successfully: {pull_request_data['html_url']}")

            if auto_merge:
                self.enable_auto_merge(pull_request_data['number'])
                if delete_branch_after_merge:
                    self.log_info(f"Will attempt to delete branch '{head_branch_name}' after merge.")
                    self._set_delete_branch_on_merge(pull_request_data['number'])

            return pull_request_data

        except requests.exceptions.RequestException as e:
            self.log_error(f"Error creating pull request: {e}")
            if response is not None:
                self.log_error(f"Response status code: {response.status_code}")
                self.log_error(f"Response body: {response.text}")
            return None

    def enable_auto_merge(self, pull_request_number):
        """
        Enables auto-merge for a given pull request.

        Args:
            pull_request_number (int): The number of the pull request.
        """
        url = f'https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls/{pull_request_number}/merge'
        params = {'auto_merge': True}
        try:
            response = requests.put(url, headers=self.headers, params=params)
            if response.status_code == 200:
                self.log_info(f"Auto-merge enabled for pull request #{pull_request_number}")
            elif response.status_code == 405:
                self.log_error(f"Could not auto-merge pull request #{pull_request_number}. Merge method not allowed or pull request not mergeable.")
            elif response.status_code == 403:
                self.log_error(f"Could not auto-merge pull request #{pull_request_number}. Insufficient permissions.")
            elif response.status_code == 409:
                self.log_error(f"Could not auto-merge pull request #{pull_request_number}. Merge conflict exists.")
            else:
                self.log_error(f"Error enabling auto-merge for pull request #{pull_request_number}. Status code: {response.status_code}, Response: {response.text}")
            response.raise_for_status()  # Raise for other unexpected errors

        except requests.exceptions.RequestException as e:
            self.log_error(f"Error enabling auto-merge for pull request #{pull_request_number}: {e}")
            if response is not None:
                self.log_error(f"Response status code: {response.status_code}")
                self.log_error(f"Response body: {response.text}")


    def _set_delete_branch_on_merge(self, pull_request_number):
        """
        Sets the head branch of a pull request to be deleted automatically after it is merged.
        This uses a GitHub API preview feature.

        Args:
            pull_request_number (int): The number of the pull request.

        Returns:
            Optional[Dict[str, Any]]: The JSON response from the GitHub API, or None if an error occurs.
        """
        url = f'https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls/{pull_request_number}/update_branch'
        headers = self.headers.copy()
        headers['Accept'] = 'application/vnd.github.loki-preview+json'  # Preview header for delete branch on merge
        data = {
            'expected_head_sha': None  # GitHub will determine the latest SHA
        }
        response = None
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            self.log_info(f"Set branch to be deleted after merge for pull request #{pull_request_number}.")
            return response.json()
        except requests.exceptions.RequestException as e:
            self.log_error(f"Error setting delete branch after merge for pull request #{pull_request_number}: {e}")
            if response is not None:
                self.log_error(f"Response status code: {response.status_code}")
                self.log_error(f"Response body: {response.text}")
            return None

    def commit_file_in_branch(self, file_path, commit_message, yaml_content_encoded, new_branch_name):

        """
        Commits a file (creates or updates) in a specified branch of the repository.

        Handles cases where the file already exists with the same content (no error)
        or different content (raises FileExistsError).

        Args:
            file_path (str): The path to the file in the repository (e.g., 'path/to/file.yaml').
            commit_message (str): The commit message for the file operation.
            yaml_content_encoded (str): The base64 encoded content of the file.
            new_branch_name (str): The name of the branch where the file will be committed.

        Raises:
            requests.exceptions.RequestException: For general GitHub API request errors.
            FileExistsError: If the file exists with different content.
            BaseException: For unexpected errors during file creation.
        """
        try:
            url = f'https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/contents/{file_path}'
            data = {
                'message': commit_message,
                'content': yaml_content_encoded,
                'branch': new_branch_name
            }
            response = requests.put(url, json=data, headers=self.headers)
            response.raise_for_status()
            self.log_info(f"File '{file_path}' created in branch '{new_branch_name}'.")

        except requests.exceptions.RequestException as e:
            self.log_info(e.response)
            if e.response is not None and e.response.status_code == 422:
                self.compare_existing_file(url,new_branch_name, yaml_content_encoded, file_path, e)

            else:
                raise requests.exceptions.RequestException(f"Error during GitHub API request: {e}") from e
        except Exception as e:
            raise BaseException(f"An unexpected error occurred while creating the file: {e}") from e


    def compare_existing_file(self, url,new_branch_name, yaml_content_encoded, file_path, e):
        """
        Compares the content of an existing file in a branch with new content.

        If the content is identical, it logs an info message and does not raise an error.
        If the content is different, it raises a FileExistsError.

        Args:
            url (str): The base URL for the file content API (e.g., '.../contents/file_path').
            new_branch_name (str): The name of the branch where the file exists.
            yaml_content_encoded (str): The base64 encoded new content to compare.
            file_path (str): The path to the file in the repository.
            original_exception (requests.exceptions.RequestException): The original exception
                                                                        that triggered this comparison.

        Returns:
            Optional[Dict[str, Any]]: The existing file's metadata if content is identical, else None.

        Raises:
            FileExistsError: If the file exists with different content.
        """
        try:
            existing_content_response = requests.get(
                f'{url}?ref={new_branch_name}',
                headers=self.headers
            )
            existing_content_response.raise_for_status()
            existing_content_data = existing_content_response.json()
            existing_content_decoded = base64.b64decode(existing_content_data['content']).decode('utf-8')

            if existing_content_decoded.strip() == base64.b64decode(yaml_content_encoded).decode('utf-8').strip():
                self.log_info(f"File '{file_path}' already exists with the same content in branch '{new_branch_name}'. No error raised.")
                return existing_content_data  # Return existing file info
            else:
                raise FileExistsError(f"File '{file_path}' already exists in branch '{new_branch_name}' with different content.") 
        except requests.exceptions.RequestException as get_error:
            self.log_info(f"Warning: Could not retrieve existing file content to compare: {get_error}")
            # raise FileExistsError(f"File '{file_path}' already exists in branch '{new_branch_name}'. Could not verify if content is the same.") from e
            return yaml_content_encoded

    def _commit_new_file(self, file_path: str, commit_message: str, yaml_content_encoded: str, new_branch_name: str):
        """
        Orchestrates the process of committing a new file:
        1. Gets the latest SHA of the base branch.
        2. Creates a new branch from the base branch.
        3. Commits the file to the newly created branch.

        Args:
            file_path (str): The path where the file will be created/updated.
            commit_message (str): The commit message.
            yaml_content_encoded (str): The base64 encoded content of the file.
            new_branch_name (str): The name of the new branch to create and commit to.

        Raises:
            requests.exceptions.RequestException: For GitHub API errors.
            yaml.YAMLError: For errors during YAML serialization (though YAML is already encoded here).
            KeyError: For issues accessing JSON data.
            Exception: For any other unexpected errors.
        """        
        try:
            self.log_info("Getting the SHA of the base branch...")
            base_sha = self.get_latest_sha_from_branch(self.branch_name)
            self.log_info(f"Base branch SHA: {base_sha[:7]}...")

            self.log_info(f"Creating a new branch '{new_branch_name}' from '{self.branch_name}'...")
            self.create_branch(new_branch_name, base_sha)
            self.log_info(f"Branch '{new_branch_name}' created successfully.")

            self.log_info(f"Committing the new file to branch '{new_branch_name}'...")
            self.commit_file_in_branch(file_path, commit_message, yaml_content_encoded, new_branch_name)
            self.log_info(f"File '{file_path}' committed successfully to '{new_branch_name}'.")

        except requests.exceptions.RequestException as e:
            error_message = f"Error during GitHub API request (file commit): {e}"
            self.log_info(error_message)
            raise requests.exceptions.RequestException(error_message) from e
        except yaml.YAMLError as e:
            error_message = f"Error serializing YAML data: {e}"
            self.log_info(error_message)
            raise yaml.YAMLError(error_message) from e
        except KeyError as e:
            error_message = f"Error accessing JSON data (file commit): {e}"
            self.log_info(error_message)
            raise KeyError(error_message) from e
        except Exception as e:
            error_message = f"An unexpected error occurred during file commit: {e}"
            self.log_info(error_message)
            raise Exception(error_message) from e

    
    def get_latest_sha_from_branch(self,branch_name):
        """
        Retrieves the SHA of the latest commit on a specified branch.

        Args:
            branch_name (str): The name of the branch (e.g., 'main', 'develop').

        Returns:
            str: The SHA of the latest commit on the branch.

        Raises:
            BaseException: If there's an error retrieving the SHA, potentially indicating
                           the branch does not exist or an API issue.
        """
        try:
            url = f'https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/git/refs/heads/{branch_name}'
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            base_branch_data = response.json()
            return base_branch_data['object']['sha']

        except Exception as e: 
            raise BaseException(f"Check if file exist")







class GitHubHandler(GitHubRepoManager):

    """
    GitHubHandler Class

    This class extends GitHubRepoManager to provide a higher-level interface
    for common GitHub operations, specifically focusing on the pull request
    creation logic. It leverages the methods provided by GitHubRepoManager.
    """

    def __init__(self, token, repo_owner, repo_name):

        """
        Initializes the GitHubHandler, setting up GitHub authentication
        and repository details.

        Args:
            token (str): The GitHub Personal Access Token.
            repo_owner (str): The owner of the GitHub repository.
            repo_name (str): The name of the GitHub repository.
        """
        # Call the constructor of the base class (GitHubRepoManager)
        # which also initializes AppLogger.
        super().__init__() 
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.branch_name = BRANCH_NAME
        self.pr_list = []
        

    def _create_pull_request_logic(self, pr_title: str, body: str, auto_merge: bool, new_branch_name: str) -> Optional[str]:
        """
        Orchestrates the creation of a pull request.

        This method calls the `create_pull_request` method from the parent class
        and handles its response, logging success or failure and returning the PR URL.

        Args:
            pr_title (str): The title for the new pull request.
            body (str): The body/description for the pull request.
            auto_merge (bool): Flag to indicate if auto-merge should be enabled.
            new_branch_name (str): The name of the head branch for the pull request.

        Returns:
            Optional[str]: The URL of the created pull request if successful, otherwise None.

        Raises:
            Exception: If the pull request creation fails or returns an unexpected response.
        """
        try:
            self.log_info(f"Creating a new pull request with title: '{pr_title}'...")
            pr_response = self.create_pull_request(
                title=pr_title,
                head_branch_name=new_branch_name,
                base_branch_name=self.branch_name,
                body=body,
                auto_merge=auto_merge,
                delete_branch_after_merge=True
            )

            if pr_response and 'html_url' in pr_response:
                pr_url = pr_response['html_url']
                self.log_info(f"Pull request created: {pr_url}")
                self.pr_list.append(pr_url)
                return pr_url
            else:
                error_message = "Failed to create pull request or received an empty response."
                self.log_info(error_message)
                raise Exception(error_message)

        except requests.exceptions.RequestException as e:
            error_message = f"Error during GitHub API request (pull request creation): {e}"
            self.log_info(error_message)
            # raise requests.exceptions.RequestException(error_message) from e

        except KeyError as e:
            error_message = f"Error accessing JSON data (pull request creation): {e}"
            self.log_info(error_message)
            # raise KeyError(error_message) from e
            
        except Exception as e:
            error_message = f"An unexpected error occurred during pull request creation: {e}"
            self.log_info(error_message)
            # raise Exception(error_message) from e
