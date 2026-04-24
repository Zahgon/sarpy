"""
Basic image registration, generally best suited most suited for coherent image
collection. This is based pretty directly on an approach developed at Sandia and
generally referred to by the name "regi".

The relevant matlab code appears to be authored by Terry M. Calloway,
Sandia National Laboratories, and modified by Wade Schwartzkopf, NGA.
"""

__classification__ = 'UNCLASSIFIED'
__author__ = ["Thomas McCullough", "Terry M. Calloway", "Wade Schwartzkopf"]


import logging
from typing import List, Tuple, Dict, Union, Optional

import numpy
from scipy.signal import correlate2d
from scipy.interpolate import LinearNDInterpolator

from sarpy.io.general.base import BaseReader


logger = logging.getLogger(__name__)


def _validate_match_parameters(
        reference_size: Tuple[int, int],
        moving_size: Tuple[int, int],
        match_box_size: Tuple[int, int],
        moving_deviation: Tuple[int, int],
        decimation: Tuple[int, int]) -> None:
    """
    Validate the match paramaters based the size of the images.

    Parameters
    ----------
    reference_size : Tuple[int, int]
    moving_size : Tuple[int, int]
    match_box_size : Tuple[int, int]
    moving_deviation : Tuple[int, int]
    decimation : Tuple[int, int]
    """
    pass


def _populate_difference_structure(
        mapping_values: List[List[Dict]]) -> None:
    """
    Helper function for populating derivative estimates into our structure.

    Parameters
    ----------
    mapping_values: List[List[dict]]
    """
    pass


def _subpixel_shift(values: numpy.ndarray) -> float:
    """
    This is simplified port of the SAR toolbox matlab function fin_minms. This
    uses data from an empirical fit derived from unknown origins to estimate where
    the "real" minimum occurred.

    Parameters
    ----------
    values : numpy.ndarray
        Must have length 3, with either `values[1] <= min(values[0], values[2])`
        (a minimization problem), or `values[1] >= max(values[0], values[2])`
        (a maximization problem). Maximization problems will be re-cast as
        minimization through inversion.

    Returns
    -------
    shift : float
        This values will be (-1, 1), with -1 corresponding to the first location,
        0 corresponding to the center location, and 1 corresponding to the final
        location.
    """
    pass


def _max_correlation_step(
        reference_array: numpy.ndarray,
        moving_array: numpy.ndarray,
        do_subpixel: bool = False) -> Tuple[Optional[numpy.ndarray], Optional[float]]:
    """
    Find the best match location of the moving array inside the reference array.

    Parameters
    ----------
    reference_array : numpy.ndarray
    moving_array : numpy.ndarray
    do_subpixel : bool
        Include a subpixel registration effort?

    Returns
    -------
    best_location : None|numpy.ndarray
        Will return `None` if there is no information, i.e. the reference patch
        or moving patch is all 0. Otherwise, this will be a numpy array
        `[row, column]` of the location of highest correlation, determined via
        :func:`numpy.argmax`.
    maximum_correlation : None|float
    """
    pass


def _single_step_location(
        reference_data: Union[BaseReader, numpy.ndarray],
        reference_index: Optional[int],
        reference_size: Tuple[int, int],
        moving_data: Union[BaseReader, numpy.ndarray],
        moving_index: Optional[int],
        moving_size: Tuple[int, int],
        reference_location: Tuple[int, int],
        moving_location: Tuple[int, int],
        match_box_size: Tuple[int, int] = (25, 25),
        moving_deviation: Tuple[int, int] = (15, 15),
        decimation: Tuple[int, int] = (1, 1)) -> Tuple[Optional[Tuple[int, int]], Optional[float]]:
    """
    Perform a single step of the reference search by finding the best matching
    location at given size and scale.

    Parameters
    ----------
    reference_data : BaseReader|numpy.ndarray
    reference_index : None|int
    reference_size : Tuple[int, int]
    moving_data : BaseReader|numpy.ndarray
    moving_index : None|int
    moving_size : Tuple[int, int]
    reference_location : Tuple[int, int]
    moving_location : Tuple[int, int]
    match_box_size : Tuple[int, int]
    moving_deviation : Tuple[int, int]
    decimation : Tuple[int, int]

    Returns
    -------
    best_location : None|Tuple[int, int]
        Will return `None` if there is no information, i.e. the reference patch
        or moving patch is all 0.
    maximum_correlation : None|float
    """
    pass


def _single_step_grid(
        reference_data: Union[BaseReader, numpy.ndarray],
        reference_index: Optional[int],
        reference_size: Tuple[int, int],
        moving_data: Union[BaseReader, numpy.ndarray],
        moving_index: Optional[int],
        moving_size: Tuple[int, int],
        reference_box_rough: Tuple[int, int],
        moving_box_rough: Tuple[int, int],
        match_box_size: Tuple[int, int] = (25, 25),
        moving_deviation: Tuple[int, int] = (15, 15),
        decimation: Tuple[int, int] = (1, 1),
        previous_values: Optional[List[List[Dict]]] = None):
    """
    We will determine a series of best matching (small size) patch locations
    between the pixel area of `reference_data` laid out in `reference_box_rough`
    and the pixel area of `moving_data` laid out in `moving_box_rough` - which
    should be very close to the same size.

    Parameters
    ----------
    reference_data : BaseReader|numpy.ndarray
    reference_index : None|int
    reference_size : Tuple[int, int]
    moving_data : BaseReader|numpy.ndarray
    moving_index : None|int
    moving_size : Tuple[int, int]
    reference_box_rough : Tuple[int, int, int, int]
    moving_box_rough : Tuple[int, int, int, int]
    match_box_size : Tuple[int, int]
    moving_deviation : Tuple[int, int]
    decimation : Tuple[int, int]
    previous_values : None|List[List[dict]]

    Returns
    -------
    result_values : List[List[dict]]
        entry `[i][j]` tell the mapping of the reference location in nominal
        reference grid to moving grid location
        :code:`{'reference_location': (row, column),
        'moving_location': (matched_row, matched_column),
        'max_correlation': <value>}`
    """
    pass


def register_arrays(
        reference_data: numpy.ndarray,
        moving_data: numpy.ndarray) -> List[List[Dict]]:
    """
    Register the moving_data array to the reference_data array using the regi algorithm.

    Parameters
    ----------
    reference_data : numpy.ndarray
    moving_data : numpy.ndarray

    Returns
    -------
    result_values : List[List[dict]]
        entry `[i][j]` tell the mapping of the reference location in nominal
        reference grid to moving grid location
        :code:`{'reference_location': (row, column),
        'moving_location': (matched_row, matched_column),
        'max_correlation': <value>}`
    """
    pass
