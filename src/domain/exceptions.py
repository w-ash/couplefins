class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class DuplicateError(DomainError):
    pass


class PeriodFinalizedError(DomainError):
    pass


class AuthenticationError(DomainError):
    pass


class ForbiddenError(DomainError):
    pass


class InvariantViolationError(DomainError):
    pass


class ChatUnavailableError(DomainError):
    pass


class ToolExecutionError(DomainError):
    pass


class MaxRoundsExceededError(DomainError):
    pass


class AnthropicApiError(DomainError):
    pass
