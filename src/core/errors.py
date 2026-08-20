class ApiError(Exception):
    status_code = 500


class ResourceNotFoundError(ApiError):
    status_code = 404


class InvalidPayloadError(ApiError):
    status_code = 400


class ConflictError(ApiError):
    status_code = 409