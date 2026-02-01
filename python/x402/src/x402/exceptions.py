"""
x402 custom exception hierarchy
"""


class X402Error(Exception):
    """x402 base exception"""
    pass


class SignatureError(X402Error):
    """Signature-related error"""
    pass


class SignatureVerificationError(SignatureError):
    """Signature verification failed"""
    pass


class SignatureCreationError(SignatureError):
    """Signature creation failed"""
    pass


class AllowanceError(X402Error):
    """Allowance-related error"""
    pass


class InsufficientAllowanceError(AllowanceError):
    """Insufficient allowance"""
    pass


class AllowanceCheckError(AllowanceError):
    """Failed to check allowance"""
    pass


class SettlementError(X402Error):
    """Settlement-related error"""
    pass


class TransactionError(X402Error):
    """Transaction-related error"""
    pass


class TransactionTimeoutError(TransactionError):
    """Transaction timeout"""
    pass


class TransactionFailedError(TransactionError):
    """Transaction execution failed"""
    pass


class ValidationError(X402Error):
    """Validation-related error"""
    pass


class PermitValidationError(ValidationError):
    """Permit validation failed"""
    
    def __init__(self, reason: str, message: str | None = None):
        self.reason = reason
        super().__init__(message or reason)


class ConfigurationError(X402Error):
    """Configuration-related error"""
    pass


class UnsupportedNetworkError(ConfigurationError):
    """Unsupported network"""
    pass


class UnknownTokenError(ConfigurationError):
    """Unknown token"""
    pass
