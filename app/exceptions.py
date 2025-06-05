from typing import Any

class JiraWebhookError(Exception):
    """Base exception for errors related to Jira webhook processing."""
    def __init__(self, message="An error occurred during Jira webhook processing.", details: Any = None):
        super().__init__(message)
        self.details = details



class InvalidJiraConfigurationParser(JiraWebhookError):
    """Raised when the name of the issue type has no configuration dictionary in the application."""
    pass 
    
class InvalidMethodError(JiraWebhookError):
    """Raised when the raw Jira webhook payload is not a the expected method."""
    pass

class InvalidPayloadError(JiraWebhookError):
    """Raised when the raw Jira webhook payload is malformed, empty, or invalid JSON."""
    pass

class MissingRequiredDataError(JiraWebhookError):
    """Raised when essential data (e.g., 'issue', 'issuetype', critical custom fields)
    is missing from a *validly structured* Jira payload."""
    pass

class UnhandledIssueTypeError(JiraWebhookError):
    """Raised when a valid issue type is received but not explicitly handled by the application logic."""
    pass

class ExternalServiceError(JiraWebhookError):
    """Base exception for errors when interacting with external services (e.g., GCP APIs, GitHub)."""
    pass

class GcpProvisioningError(ExternalServiceError):
    """Raised when a GCP provisioning operation fails."""
    pass

class PermissionDeniedError(ExternalServiceError):
    """Raised when an operation fails due to insufficient permissions."""
    pass

class GitHubOperationError(ExternalServiceError):
    """Raised when a GitHub operation (e.g., PR creation) fails."""
    pass

class ErrorAddingCommentToJira(JiraWebhookError):
    """Raised when there is an error while adding a commet to the Jira Issue"""
    pass