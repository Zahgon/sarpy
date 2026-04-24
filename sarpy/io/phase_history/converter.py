"""
This module provide utilities for reading essentially Compensated Phase History Data.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"

import os
from typing import BinaryIO, Callable, Union

from sarpy.io.general.base import SarpyIOError, check_for_openers
from sarpy.io.general.utils import is_file_like
from sarpy.io.phase_history.base import CPHDTypeReader


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
        This function should return a sarpy.io.phase_history.base.CPHDTypeReader instance
        if the referenced file is viable for the underlying type, and None otherwise.

    Returns
    -------
    None
    """
    pass


def parse_openers() -> None:
    """
    Automatically find the viable openers (i.e. :func:`is_a`) in the various modules.
    """

    global _parsed_openers
    if _parsed_openers:
        return
    _parsed_openers = True

    check_for_openers('sarpy.io.phase_history', register_opener)


def open_phase_history(file_name: Union[str, BinaryIO]) -> CPHDTypeReader:
    """
    Given a file, try to find and return the appropriate reader object.

    Parameters
    ----------
    file_name : str|BinaryIO

    Returns
    -------
    CPHDTypeReader

    Raises
    ------
    SarpyIOError
    """
    pass
