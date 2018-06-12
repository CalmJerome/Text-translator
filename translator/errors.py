# -*- coding: utf-8 -*-

from enum import IntEnum


class ErrorEnum(IntEnum):
    USER_NOT_FOUND = 1001
    WRONG_PASSWORD = 1002
    MISSING_FIELD = 1003
    NOT_FOUND = 404
    NOT_LOGGED_IN = 401
    INVALID_TEXT = 1004
