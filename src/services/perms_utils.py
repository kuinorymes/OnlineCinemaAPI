from typing import Annotated

from fastapi import Depends, HTTPException

from config.dependencies import get_jwt_auth_manager
from database.models.users import UserGroupEnum
from security.interfaces import JWTAuthManagerInterface

from routes.users import get_current_user, DB, oauth_scheme


async def user_moderator_or_admin(
    db: DB,
    token: Annotated[str, Depends(oauth_scheme)],
    jwt_manager: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
):
    try:
        user = await get_current_user(db, token, jwt_manager)
        await db.refresh(user, ["group"])
        if user.group.name in [UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN]:
            return user
        return None
    except Exception:
        return None
