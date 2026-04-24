"""
This module provides utilities for attempting to open other image files not
opened by the sicd, sidd, cphd, or crsd reader collections.
"""

import os
from typing import Callable
from sarpy.io.general.base import SarpyIOError, BaseReader, check_for_openers

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


###########
# Module variables
_openers = []
_parsed_openers = False


def register_opener(open_func: Callable) -> None:
    """
    Provide a new opener.

    Parameters
    ----------
    open_func : Callable
        This is required to be a function which takes a single argument (file name).
        This function should return a sarpy.io.general.base.BaseReader instance
        if the referenced file is viable for the underlying type, and None otherwise.

    Returns
    -------
    None
    """
    pass


def parse_openers() -> None:
    """
    Automatically find the viable openers (i.e. :func:`is_a`) in the various modules.

    Returns
    -------

    """

    global _parsed_openers
    if _parsed_openers:
        return
    _parsed_openers = True

    check_for_openers('sarpy.io.general', register_opener)


def open_general(file_name: str) -> BaseReader:
    """
    Given a file, try to find and return the appropriate reader object.

    Parameters
    ----------
    file_name : str

    Returns
    -------
    BaseReader

    Raises
    ------
    SarpyIOError
    """
    pass
