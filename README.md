

# Jira to GitHub Automation for GCP Provisioning

This application automates the provisioning of Google Cloud Platform (GCP) resources (Folders and Projects) by integrating Jira webhooks with a GitHub repository. When a specific Jira issue (e.g., "New GCP Project Provisioning" or "New GCP Folder Provisioning") is created or updated, this application processes the request, generates the necessary Terraform configuration files, commits them to a new branch in a designated GitHub repository, and creates a Pull Request (PR). It also handles auto-merging for certain conditions and updates the Jira issue with progress and status.

---

## 🚀 Features

* **Jira Webhook Listener**: Listens for incoming Jira webhook payloads for specific issue types.
* **Payload Parsing & Validation**: Extracts and validates required data from Jira issue fields, ensuring data integrity and adherence to predefined rules (e.g., folder existence, project name uniqueness, budget checks).
* **Dynamic Provisioner Selection**: Automatically selects the appropriate GCP provisioner (e.g., `GcpProjectProvisioner`, `GcpFolderProvisioner`) based on the Jira issue type.
* **Terraform YAML Generation**: Dynamically generates Terraform configuration files in YAML format for GCP Folders and Projects, including associated billing budgets and labels.
* **GitHub Integration**:
    * Creates new Git branches for each provisioning request.
    * Commits the generated Terraform YAML files to the new branch.
    * Creates Pull Requests (PRs) in the target GitHub repository.
    * **Conditional Auto-Merge**: Automatically merges PRs for specific conditions (e.g., l0 data security projects in the dev environment with budgets below a defined limit).
    * Sets branches for automatic deletion after merge.
* **Jira Commenting & Status Updates**: Provides real-time feedback on the Jira issue by adding comments for various stages (start, validation success, errors, PR creation, auto-approval status) and updating the issue's workflow status (e.g., "Set as blocked", "Set as done", "Set as to be reviewed").
* **Google Cloud Asset Inventory Integration**: Leverages the Cloud Asset Inventory API to check for the existence and uniqueness of GCP resources (folders, projects) before provisioning.
* **Robust Error Handling**: Implements comprehensive error logging and graceful handling for various failures (invalid payload, missing data, GCP provisioning errors, GitHub operation errors), ensuring Jira is updated with appropriate error messages.

---

## ⚙️ How It Works

1.  **Jira Webhook Trigger**: A Jira webhook is configured to send a payload to this application's endpoint whenever a relevant issue is created or updated.
2.  **Request Reception & Validation**: The `AppManager` receives the POST request, validates its method, and parses the JSON payload.
3.  **Issue Extraction**: The Jira issue type and ID are extracted from the payload.
4.  **Configuration Parsing**: Based on the issue type, the `AppManager` uses a `PayloadParser` to extract specific field values from the Jira payload according to predefined configurations (`project_creation_ticket_fields`, `folder_creation_ticket_fields`).
5.  **Provisioner Selection**: An appropriate `BaseProvisioner` subclass (`GcpProjectProvisioner` or `GcpFolderProvisioner`) is instantiated.
6.  **Data Validation**: The selected provisioner performs detailed validation checks (e.g., uniqueness of resource names, existence of parent folders, budget constraints). If validation fails, the Jira issue is updated with an error comment, and its status is changed to "Set as blocked".
7.  **Terraform YAML Generation**: If validation passes, the provisioner generates the necessary Terraform YAML files for the GCP resource(s) and their associated budgets.
8.  **GitHub Operations**:
    * A `GitHubHandler` is initialized with repository credentials.
    * A new Git branch is created.
    * The generated Terraform YAML files are committed to this new branch.
    * A Pull Request is created from the new branch to the main branch.
    * Based on predefined rules (e.g., l0 data security, dev environment, budget limits), the PR might be automatically merged.
    * The Jira issue is updated with the PR URL, and its status reflects whether manual review is needed or if it's "done".
9.  **Jira Updates**: Throughout the process, the application communicates its status back to Jira via comments and status transitions.

---

## 📂 Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── exceptions.py           # Custom exception classes
│   ├── github.py               # GitHubRepoManager and GitHubHandler for GitHub API interactions
│   ├── logger.py               # AppLogger for centralized logging
│   ├── parsers.py              # PayloadParser for extracting data from Jira webhooks
│   └── provisioners/
│       ├── __init__.py
│       ├── base.py             # BaseProvisioner and HierarchyrProvisioner abstract classes
│       ├── folders.py          # GcpFolderProvisioner (concrete implementation for folders)
│       └── projects.py         # GcpProjectProvisioner (concrete implementation for projects)
├── configs/
│   ├── __init__.py
│   ├── github/
│   │   ├── __init__.py
│   │   └── credentials.py      # GitHub repository credentials mapping (sensitive, use env vars!)
│   └── jira/
│       ├── __init__.py
│       └── configurations.py   # Jira field mappings and other configurations (e.g., env_mapping)
├── main.py                     # Main entry point (e.g., for a Cloud Function)
└── README.md                   # This file
```

---

## 🛠️ Setup and Configuration

### Prerequisites

* **Python 3.8+**
* **Google Cloud Project**: With Cloud Asset Inventory API enabled and appropriate service account permissions.
* **Jira Instance**: With admin access to configure webhooks and custom fields.
* **GitHub Repository**: A dedicated repository for storing Terraform configurations, with a GitHub Personal Access Token (PAT) that has sufficient permissions (`repo` scope: `repo`, `workflow`).
* **Terraform**: While this application generates Terraform files, Terraform itself is expected to run in a separate CI/CD pipeline that consumes these files.

### Environment Variables

It is crucial to configure the following environment variables in your deployment environment (e.g., Google Cloud Functions, Kubernetes, Docker). **Never hardcode sensitive values directly in the code.**

* `LOGGING_NAME`: (Optional) Name for Google Cloud Logging. Defaults to `medium-jira-github-automation-func`.
* `JIRA_USER`: Your Jira API user email.
* `JIRA_TOKEN`: Your Jira API token.
* `JIRA_SERVER`: The base URL of your Jira instance (e.g., `https://your-domain.atlassian.net`).
* `GITHUB_TOKEN`: Your GitHub Personal Access Token (PAT) with `repo` scope.
* `REPO_OWNER`: The owner (username or organization) of the GitHub repository where Terraform configurations will be pushed.
* `REPO_NAME`: The name of the GitHub repository (e.g., `gcp-terraform-configs`).
* `ORG_ID`: Your Google Cloud Organization ID (e.g., `123456789012`). This is used for listing assets.
* `BUDGET_LIMIT`: (Optional) An integer representing the budget limit (in euros) for auto-approving l0 data security projects in the dev environment. Defaults to `150`.
* `BRANCH_NAME`: (Optional) The default base branch name for GitHub operations (e.g., `main`, `master`). Defaults to `main`.
* `DEBUG`: Set to `True` or `False` (as a string, e.g., "True" or "False"). If set to "True", enables verbose debug logging. Defaults to `False`.
* `DEBUG_PAYLOAD`: Set to `True` or `False` (as a string). If set to "True", the full incoming Jira webhook payload will be logged. Defaults to `False`.

### Jira Configuration

* **Custom Fields**: Ensure your Jira project has the necessary custom fields configured as expected by `configs/jira/configurations.py` (e.g., fields for Project Name, Folder, Environment, Data Security, Budget, etc.). The exact field IDs/names used in the code must match your Jira setup.
* **Webhooks**: Configure a Jira webhook to point to the endpoint of your deployed application.
    * **URL**: Your deployed application's URL (e.g., a Cloud Function URL).
    * **Events**: Configure the webhook to trigger on "Issue Created" and "Issue Updated" events for the relevant issue types (e.g., "New GCP Project Provisioning", "New GCP Folder Provisioning").
    * **Secret**: (Optional but recommended) Configure a secret for webhook verification.

### GitHub Configuration

* **Repository**: Create a GitHub repository (e.g., `gcp-terraform-configs`) where the generated Terraform YAML files will be stored.
* **Personal Access Token (PAT)**: Generate a GitHub PAT with `repo` scope permissions. This token should be provided via the `GITHUB_TOKEN` environment variable.
* `configs/github/credentials.py`: This file now defines the names of the environment variables that hold your GitHub credentials, allowing for dynamic assignment based on Jira issue types. Ensure these environment variables are set in your deployment environment.

### GCP Permissions

The service account running this application (e.g., a Cloud Function service account) needs the following IAM roles:

* `Cloud Asset Viewer` (`roles/cloudasset.viewer`): To list existing projects and folders.
* `Folder Admin` (`roles/resourcemanager.folderAdmin`): To create and manage folders (if folder provisioning is enabled).
* `Project Creator` (`roles/resourcemanager.projectCreator`): To create new projects (if project provisioning is enabled).
* `Project Billing Manager` (`roles/billing.projectBillingManager`): To link projects to billing accounts.
* `Cloud Logging Log Writer` (`roles/logging.logWriter`): To write logs to Google Cloud Logging.
* `Service Account User` (`roles/iam.serviceAccountUser`): If the application needs to impersonate other service accounts for specific operations.

---

## 🚀 Deployment

This application is designed to be deployed as a serverless function, such as a Google Cloud Function or AWS Lambda.

### Example Deployment (Google Cloud Function):

1.  **Clone the repository**:

    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```

2.  **Install dependencies**:
    Install  `requirements.txt` file:

    ```bash
    pip install -r requirements.txt
    ```

3.  **Deploy the Cloud Function**:

    ```bash
    gcloud functions deploy jira-github-automation \
      --runtime python39 \
      --trigger-http \
      --allow-unauthenticated \
      --entry-point main_handler \
      --set-env-vars \
      JIRA_USER="your-jira-user@example.com",\
      JIRA_TOKEN="your_jira_api_token",\
      JIRA_SERVER="https://your-jira-instance.atlassian.net",\
      GITHUB_TOKEN="your_github_pat",\
      REPO_OWNER="your-github-org-or-user",\
      REPO_NAME="your-gcp-configs-repo",\
      ORG_ID="your-gcp-organization-id",\
      ORG_ID_DEBUG="your-gcp-organization-id-debug",\
      BUDGET_LIMIT=150,\
      BRANCH_NAME="main",\
      DEBUG="False",\
      DEBUG_PAYLOAD="False" \
      --region your-gcp-region # e.g., us-central1
    ```

    **Note**: `--allow-unauthenticated` is for quick testing. For production, secure your endpoint using IAM or other methods. Replace all placeholder values (`your-jira-user@example.com`, `your_jira_api_token`, etc.) with your actual environment variables. Consider using Google Secret Manager for sensitive values.

---

## 🤝 Contributing

Contributions are welcome! Please follow standard GitHub flow:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature-name`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'feat: Add new feature'`).
5.  Push to the branch (`git push origin feature/your-feature-name`).
6.  Create a new Pull Request.

---

## 📄 License

This project is licensed under the GNU Affero General Public License 3.0 or later – you can distribute modified versions if you track the changes and the date when you made them. Like with other GNU licenses, derivatives need to be licensed under AGPL.