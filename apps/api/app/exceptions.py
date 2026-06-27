from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

class BaseAppException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class AuthException(BaseAppException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__("AUTH_FAILED", message, status.HTTP_401_UNAUTHORIZED)

class PermissionException(BaseAppException):
    def __init__(self, message: str = "Access denied"):
        super().__init__("PERMISSION_DENIED", message, status.HTTP_403_FORBIDDEN)

class NotFoundException(BaseAppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__("NOT_FOUND", message, status.HTTP_404_NOT_FOUND)

class ConflictException(BaseAppException):
    def __init__(self, message: str = "Conflict occurred"):
        super().__init__("CONFLICT", message, status.HTTP_409_CONFLICT)

def register_exception_handlers(app):
    from fastapi.exceptions import HTTPException as FastAPIHTTPException

    @app.exception_handler(FastAPIHTTPException)
    async def fastapi_http_exception_handler(request: Request, exc: FastAPIHTTPException):
        # Determine code based on status code
        code = "AUTH_FAILED" if exc.status_code in [401, 403] else "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": code,
                    "message": exc.detail
                }
            }
        )

    @app.exception_handler(BaseAppException)
    async def app_exception_handler(request: Request, exc: BaseAppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": exc.code,
                    "message": exc.message
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Format Pydantic validation errors nicely
        errors = exc.errors()
        error_msg = "; ".join([f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in errors])
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"Request validation failed: {error_msg}"
                }
            }
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_exception_handler(request: Request, exc: SQLAlchemyError):
        import traceback
        traceback.print_exc()
        # Prevent database implementation details from leaking, return generic envelope
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": f"An internal database error occurred: {str(exc)}"
                }
            }
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": f"A generic server error occurred: {str(exc)}"
                }
            }
        )

