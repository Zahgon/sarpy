"""
The module contains methods for computing a coherent change detection from registered images
"""

from typing import Union, Tuple

import numpy
import scipy.signal

__classification__ = "UNCLASSIFIED"
__author__ = ('Thomas Mccullough',  'Wade Schwartzkopf', 'Mike Dowell')


def mem(
        reference_image: numpy.ndarray,
        match_image: numpy.ndarray,
        corr_window_size: Union[int, Tuple[int, int]]) -> Tuple[numpy.ndarray, numpy.ndarray]:
    """
    Performs coherent change detection, following the equation as described in
    Jakowatz, et al., "Spotlight-mode Synthetic Aperture radar: A Signal
    Processing Approach".

    .. warning: This assumes that the two arrays have already been properly
        registered with respect to one another, and all processing will proceed
        directly in memory.

    Parameters
    ----------
    reference_image : numpy.ndarray
    match_image : numpy.ndarray
    corr_window_size : int|tuple
        The correlation window size. If int, a square correlation window of
        given size will be used. If tuple, it must be a two element tuple of
        ints which describe the correlation window size.

    Returns
    -------
    (numpy.ndarray, numpy.ndarray)
        The ccd and phase arrays
    """
    pass
