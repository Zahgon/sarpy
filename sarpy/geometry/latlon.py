"""
Module for converting between various latitude/longitude representations.
"""

import re

import numpy


__classification__ = "UNCLASSIFIED"
__author__ = "Wade Schwartzkopf"


def string(value, latlon, num_units=3, precision=None, delimiter='',
           include_symbols=True, signed=False, padded=True):
    """
    Convert latitude/longitude numeric values to customizable string format.

    Supports ISO 6709:2008 formatted geographic coordinates:

    * Annex D (human interface)
        delimiter = ''; include_symbols = true; padded = true; signed = false
    * Annex H (string representation)
        delimiter = ''; include_symbols = false; padded = true; signed = true

    Parameters
    ----------
    value : float|numpy.ndarray|list|tuple
        Value of latitude or longitude in decimal degrees or dms vector.
    latlon : str
        One of {'lat', 'lon'}, required for formatting string.
    num_units : int
        1 - decimal degrees; 2 - degrees/minutes; 3 - degrees/minutes/seconds.
        Default is 3.
    delimiter : str|list|tuple
        Separators between degrees/minutes/seconds/hemisphere.  Default is '' (empty).
    include_symbols : bool
        Whether to include degree, minute, second symbols.  Default is true.
    signed : bool
        Whether to use +/- or N/S/E/W to represent hemisphere.
        Default is false (N/S/E/W).
    precision : int
        Number of decimal points shown in finest unit.  Default is 5 if
        num_units==1, otherwise 0.
    padded : bool
        Whether to use zeros to pad out to consistent string length (3 digits for
        longitude degrees, 2 digits for all other elements).  Default is true.
    """
    pass


def dms(degrees):
    """
    Calculate degrees, minutes, seconds representation from decimal degrees.

    Parameters
    ----------
    degrees : float

    Returns
    -------
    (int, int, float)
    """
    pass


def num(latlon_input):
    """
    Convert a variety of lat/long formats into decimal degree value.

    This should handle any string compliant with the ISO 6709:2008 standard
    or any of a number of variants for describing lat/long coordinates.
    Also handles degree/minutes/seconds passed in as a tuple/list/array.

    Parameters
    ----------
    latlon_input : numpy.ndarray|list|tuple|str

    Returns
    -------
    float
    """
    pass
