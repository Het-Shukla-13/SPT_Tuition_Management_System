from apps.common.exceptions import AppException, ConflictError


class InvalidAmount(AppException):
    default_detail = "The amount must be more than zero."
    default_code = "INVALID_AMOUNT"


class FutureDate(AppException):
    default_detail = "The date can't be in the future."
    default_code = "FUTURE_DATE"


class NoteRequired(AppException):
    default_detail = "A reason / note is required."
    default_code = "NOTE_REQUIRED"


class NotAPayment(AppException):
    default_detail = "Only payments can be reversed."
    default_code = "NOT_A_PAYMENT"


class AlreadyReversed(ConflictError):
    default_detail = "This payment has already been reversed."
    default_code = "ALREADY_REVERSED"


class RefundTooLarge(AppException):
    default_detail = "The refund is more than what was paid."
    default_code = "REFUND_TOO_LARGE"


class IdempotencyConflict(ConflictError):
    default_detail = "This Idempotency-Key was already used for a different request."
    default_code = "IDEMPOTENCY_CONFLICT"


class FeeRequired(AppException):
    default_detail = (
        "Enter the agreed fee (no fee structure exists for this standard and year)."
    )
    default_code = "FEE_REQUIRED"


class AlreadyRolledOver(ConflictError):
    default_detail = "This student already has an account for that academic year."
    default_code = "ALREADY_ROLLED_OVER"
