from typing import List, Dict, Set
from fastapi import Depends, HTTPException, status
from app.dependencies import get_current_user
from app.schemas.token import TokenData

# Role to Permissions matrix definition
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "developer": {
        "projects:create",
        "projects:read",
        "projects:write",
        "projects:delete"
    },
    "auditor": {
        "projects:read",
        "audit:read"
    },
    "admin": {
        "*"  # Admin wildcard permission matches everything
    }
}

class PermissionRequired:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(self, current_user: TokenData = Depends(get_current_user)) -> TokenData:
        user_role = current_user.role
        user_permissions = ROLE_PERMISSIONS.get(user_role, set())

        # Validate permission match (explicitly allow admin *)
        if "*" not in user_permissions and self.required_permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have the required permissions to perform this operation"
            )
        return current_user
