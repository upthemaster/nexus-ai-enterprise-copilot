"""
Domain exceptions and error definitions for NexusAI backend.

Why: Defining custom domain exceptions separates low-level library/system
errors from sanitized client-facing HTTP responses. It ensures that internal
file paths, stack traces, and document contents are never leaked to API clients.
"""

from typing import Optional


class NexusBaseException(Exception):
    """
    Base exception for all NexusAI domain errors.
    
    Attributes:
        message (str): Safe, user-facing error message.
        status_code (int): Corresponding HTTP status code.
        error_type (str): Categorical identifier for programmatic client error handling.
    """
    def __init__(self, message: str, status_code: int = 400, error_type: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type or self.__class__.__name__


class UnsupportedFileTypeError(NexusBaseException):
    """
    Raised when an uploaded document does not match the allowed extension whitelist
    or exhibits an unexpected MIME type.
    """
    def __init__(self, message: str):
        super().__init__(message=message, status_code=415, error_type="UnsupportedMediaType")


class FileTooLargeError(NexusBaseException):
    """
    Raised when a file exceeds MAX_FILE_SIZE_MB during streaming verification.
    """
    def __init__(self, message: str):
        super().__init__(message=message, status_code=413, error_type="PayloadTooLarge")


class InvalidFileSignatureError(NexusBaseException):
    """
    Raised when file header magic bytes do not match the claimed file extension,
    preventing disguised binary or executable uploads.
    """
    def __init__(self, message: str):
        super().__init__(message=message, status_code=400, error_type="InvalidFileSignature")


class PathTraversalError(NexusBaseException):
    """
    Raised when a supplied filename contains directory traversal patterns
    such as '../' or absolute paths.
    """
    def __init__(self, message: str = "Invalid filename format detected."):
        super().__init__(message=message, status_code=400, error_type="PathTraversalDetected")


class CorruptedFileError(NexusBaseException):
    """
    Raised when an uploaded file cannot be parsed or decoded by the format extractor
    due to malformed structure or binary corruption.
    """
    def __init__(self, message: str):
        super().__init__(message=message, status_code=422, error_type="UnprocessableEntity")


class EmptyDocumentError(NexusBaseException):
    """
    Raised when an uploaded file is empty (0 bytes).
    """
    def __init__(self, message: str = "Uploaded document contains zero bytes."):
        super().__init__(message=message, status_code=400, error_type="EmptyDocument")

