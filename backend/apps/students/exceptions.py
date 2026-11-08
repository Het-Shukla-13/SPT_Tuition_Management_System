from apps.common.exceptions import AppException, ConflictError


class NoCurrentAcademicYear(AppException):
    default_detail = "Set a current academic year first (Academics → academic years)."
    default_code = "NO_CURRENT_ACADEMIC_YEAR"


class PossibleDuplicateStudent(ConflictError):
    default_detail = (
        "A similar student already exists. Check the list in `errors`; send "
        "confirm_duplicate: true to admit anyway."
    )
    default_code = "POSSIBLE_DUPLICATE_STUDENT"


class InactiveReference(AppException):
    default_detail = "One of the selected items is deactivated."
    default_code = "INACTIVE_REFERENCE"


class NotAPortalLogin(AppException):
    default_detail = "Only parent/student (PORTAL) logins can be linked to students."
    default_code = "NOT_A_PORTAL_LOGIN"


class AccessAlreadyGranted(ConflictError):
    default_detail = "This login can already see this student."
    default_code = "ACCESS_ALREADY_GRANTED"


class AccessNotFound(AppException):
    status_code = 404
    default_detail = "This login doesn't have access to this student."
    default_code = "NOT_FOUND"


class NothingChanged(AppException):
    default_detail = "Nothing to change: the student already has these details."
    default_code = "NOTHING_CHANGED"


class InvalidPhoto(AppException):
    default_detail = "The photo must be a JPEG, PNG or WebP image."
    default_code = "INVALID_PHOTO"


class PhotoTooLarge(AppException):
    default_detail = "The photo is too large."
    default_code = "PHOTO_TOO_LARGE"


class NoPhoto(AppException):
    status_code = 404
    default_detail = "This student has no photo."
    default_code = "NOT_FOUND"
