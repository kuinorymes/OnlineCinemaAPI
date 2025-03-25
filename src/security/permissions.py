from fastapi import Depends, HTTPException, status

from routes.users import get_current_user


def is_admin(current_user = Depends(get_current_user)):
    if current_user.group.name != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Admins only."
        )
    return current_user