class PhotoScanError(Exception):
    """Base exception for all PhotoScan-related errors."""
    def __init__(self, message: str, diagnostic_id: str = "ERR_GENERIC"):
        super().__init__(message)
        self.message = message
        self.diagnostic_id = diagnostic_id

class UnsupportedInputError(PhotoScanError):
    def __init__(self, message: str):
        super().__init__(message, "ERR_UNSUPPORTED_INPUT")

class DecodeFailureError(PhotoScanError):
    def __init__(self, message: str):
        super().__init__(message, "ERR_DECODE_FAILURE")

class InvalidImageError(PhotoScanError):
    def __init__(self, message: str):
        super().__init__(message, "ERR_INVALID_IMAGE")

class DetectionFailureError(PhotoScanError):
    def __init__(self, message: str):
        super().__init__(message, "ERR_DETECTION_FAILURE")

class InvalidGeometryError(PhotoScanError):
    def __init__(self, message: str):
        super().__init__(message, "ERR_INVALID_GEOMETRY")

class ProcessingFailureError(PhotoScanError):
    def __init__(self, message: str):
        super().__init__(message, "ERR_PROCESSING_FAILURE")

class InsufficientMemoryError(PhotoScanError):
    def __init__(self, message: str):
        super().__init__(message, "ERR_INSUFFICIENT_MEMORY")

class ExportFailureError(PhotoScanError):
    def __init__(self, message: str):
        super().__init__(message, "ERR_EXPORT_FAILURE")

class PermissionFailureError(PhotoScanError):
    def __init__(self, message: str):
        super().__init__(message, "ERR_PERMISSION_FAILURE")

class ConfigurationError(PhotoScanError):
    def __init__(self, message: str):
        super().__init__(message, "ERR_CONFIGURATION")

class PluginError(PhotoScanError):
    def __init__(self, message: str):
        super().__init__(message, "ERR_PLUGIN_FAILURE")

class UserCancellationError(PhotoScanError):
    def __init__(self, message: str = "Operation was cancelled by user."):
        super().__init__(message, "ERR_USER_CANCELLATION")
