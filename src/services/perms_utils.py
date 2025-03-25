from typing import Annotated

from fastapi import Depends, HTTPException

from config.dependencies import get_jwt_auth_manager
from database.models.users import UserGroupEnum
from security.interfaces import JWTAuthManagerInterface

from routes.users import get_current_user, DB, oauth_scheme


async def user_staff(
        db: DB,
        token: Annotated[str, Depends(oauth_scheme)],
        jwt_manager: Annotated[JWTAuthManagerInterface, Depends(get_jwt_auth_manager)],
):
    user = await get_current_user(db, token, jwt_manager)
    await db.refresh(user, ["group"])
    if user.group.name not in [UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN]:
        raise HTTPException(
            status_code=403, detail="You are not authorized to perform this action."
        )
    return user
