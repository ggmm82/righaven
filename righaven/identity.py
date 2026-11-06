"""Shared session identity for RigHaven extensions."""
from fastapi import HTTPException, Request


def current_user(request: Request):
    user = getattr(request.state, 'user', None)
    if user is None or not getattr(user, 'id', None):
        raise HTTPException(401, 'Sign in to RigHaven')
    return user


def current_user_id(request: Request):
    return str(current_user(request).id)
