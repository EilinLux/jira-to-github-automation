import functions_framework
from flask import Request
import os
from typing import Dict, Any


# Import your custom exceptions and AppManager from your app package
from app.exceptions import (
    InvalidPayloadError, InvalidJiraConfigurationParser,  MissingRequiredDataError, UnhandledIssueTypeError,
    GcpProvisioningError, PermissionDeniedError, GitHubOperationError, JiraWebhookError, 
    InvalidMethodError
)
from app.app_manager import AppManager



@functions_framework.http
def handle_jira_webhook(request: Request):
    """
    Processes a Jira webhook payload and calls different functions based on the issue type.

    Args:
        request (flask.Request): The Flask request object containing the webhook data.
    """
  

    try:
        am = AppManager()
        am.check_if_post_request(request)
        am.transform_into_json(request)
        am.extract_issue()

        am.parse_jira_request()
        am.select_provisioner()
        am.validate_jira_request()

        am.initialize_github_manager()
        
        
        am.built_terraform_yaml()

        am.push_to_github()

        am.change_issue_status("Set as done", jira_id= am.jira_id)    
        return "Webhook processed successfully", 200



    except InvalidMethodError as e:
        return 'Method Not Allowed', 405

    except InvalidJiraConfigurationParser as e:
        return e, 404 
        
    except InvalidPayloadError as e:
        am.log_error(f"Invalid Jira payload for issue {am.jira_id}: {e}. Raw data sample: {str(webhook_data)[:200]}...")
        return f"Bad Request: Invalid payload format or content. {e}", 400
    

    except MissingRequiredDataError as e:
        am.log_error(f"Missing required data in Jira payload for issue {am.jira_id}: {e}. Raw data sample: {str(webhook_data)[:200]}...")
        return f"Bad Request: Essential data missing from payload. {e}", 400

    except GcpProvisioningError as e:
        am.log_error(f"GCP provisioning failed for issue {am.jira_id}: {e}")
        return f"Internal Server Error: GCP provisioning operation failed. {e}", 500

    except PermissionDeniedError as e:
        am.log_error(f"Permission denied during operation for issue {am.jira_id}: {e}")
        return f"Internal Server Error: Insufficient permissions for operation. {e}", 500

    except GitHubOperationError as e:
        am.log_error(f"GitHub operation failed for issue {am.jira_id}: {e}")
        am.add_comment_to_jira_issue(comment_text=e, jira_id= am.jira_id, comment_type = "error")
        am.change_issue_status(jira_id= am.jira_id, transition_name = "Set as blocked")
        return f"Internal Server Error: GitHub operation failed. {e}", 500

    except JiraWebhookError as e:
        am.log_error(f"A general Jira webhook processing error occurred for issue {am.jira_id}: {e}")
        return f"Internal Server Error: A processing error occurred. {e}", 500

    # --- Catch-all for any unexpected system-level exceptions ---
    except Exception as e:
        am.log_error(f"An unexpected and unhandled critical error occurred processing Jira webhook for issue {am.jira_id}: {e}")
        am.add_comment_to_jira_issue(comment_text=e, jira_id= am.jira_id, comment_type = "error")
        am.change_issue_status(jira_id= am.jira_id, transition_name = "Set as blocked")
        return "Internal Server Error: An unexpected error occurred. Please check function logs.", 500
