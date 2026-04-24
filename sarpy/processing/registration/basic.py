"""
Basic image registration tools
"""

__classification__ = "UNCLASSIFIED"
__author__ = 'Thomas McCullough'

import logging
from typing import Sequence, Union, Tuple, Any

import numpy
from scipy.optimize import minimize

from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.product.sidd1_elements.SIDD import SIDDType as SIDDType1
from sarpy.io.product.sidd2_elements.SIDD import SIDDType as SIDDType2
from sarpy.geometry.geocoords import ecf_to_geodetic
from sarpy.geometry.point_projection import ground_to_image


logger = logging.getLogger(__name__)


def best_physical_location_fit(
        structs: Sequence[Union[SICDType, SIDDType1, SIDDType2]],
        locs: Union[numpy.ndarray, list, tuple],
        **minimization_args) -> Tuple[numpy.ndarray, float, Any]:
    """
    Given a collection of SICD and/or SIDDs and a collection of image coordinates, 
    each of which identifies the pixel location of the same feature in the 
    respective image, determine the (best fit) geophysical location of this feature. 

    This assumes that any adjustable parameters used for the SICD/SIDD projection 
    model have already been applied (via :func:`define_coa_projection`).

    Parameters
    ----------
    structs : Sequence[SICDType|SIDDType1|SIDDType2]
        The collection of sicds/sidds, of length `N`
    locs : numpy.ndarray|list|tuple
        The image coordinate collection, of shape `(N, 2)`
    minimization_args
        The keyword arguments (after `args` argument) passed through to
        :func:`scipy.optimize.minimize`. This will default to `'Powell'` 
        optimization, which seems generally much more reliable for this 
        problem than the steepest descent based approaches.

    Returns
    -------
    ecf_location : numpy.ndarray
        The location in question, in ECF coordinates
    residue : float
        The mean square residue of the physical distance between the given
        location and the image locations projected into the surface of
        given HAE value
    result
        The minimization result object
    """
    pass


def _find_best_adjustable_parameters_sicd(
        sicd: SICDType,
        ecf_coords: numpy.ndarray,
        img_coords: numpy.ndarray,
        **minimization_args) -> Tuple[numpy.ndarray, numpy.ndarray, float, float, Any]:
    """
    Find the best projection model adjustable parameters (in `'ECF'` coordinate frame)
    to fit the geophysical coordinate locations to the image coordinate locations.

    Parameters
    ----------
    sicd : SICDType
    ecf_coords : numpy.ndarray
        The geophysical coordinates of shape `(N, 3)` for the identified features
    img_coords : numpy.ndarray
        The image coordinates of shape `(N, 2)` for the identified features
    minimization_args
        The keyword arguments (after `args` argument) passed through to
        :func:`scipy.optimize.minimize`. This will default to `'Powell'`
        optimization, which seems generally much more reliable for this
        problem than the steepest descent based approaches.

    Returns
    -------
    delta_arp : numpy.ndarray
    delta_varp : numpy.ndarray
    delta_range : float
    residue : float
        Average pixel coordinate distance across the features between projected
        and observed pixel locations
    result
        The minimization result
    """
    pass


def _find_best_adjustable_parameters(
        struct: Union[SICDType, SIDDType1, SIDDType2],
        ecf_coords: numpy.ndarray,
        img_coords: numpy.ndarray,
        **minimization_args) -> Tuple[numpy.ndarray, numpy.ndarray, float, float, Any]:
    """
    Find the best projection model adjustable parameters (in `'ECF'` coordinate frame)
    to fit the geophysical coordinate locations to the image coordinate locations.

    Parameters
    ----------
    struct : SICDType|SIDDType1|SIDDType2
    ecf_coords : numpy.ndarray
        The geophysical coordinates of shape `(N, 3)` for the identified features
    img_coords : numpy.ndarray
        The image coordinates of shape `(N, 2)` for the identified features
    minimization_args
        The keyword arguments (after `args` argument) passed through to
        :func:`scipy.optimize.minimize`. This will default to `'Powell'`
        optimization, which seems generally much more reliable for this
        problem than the steepest descent based approaches.

    Returns
    -------
    delta_arp : numpy.ndarray
    delta_varp : numpy.ndarray
    delta_range : float
    residue : float
        Average pixel coordinate distance across the features between projected
        and observed pixel locations
    result
        The minimization result
    """
    pass


def find_best_adjustable_parameters(
        struct: Union[SICDType, SIDDType1, SIDDType2],
        ecf_coords: numpy.ndarray,
        img_coords: numpy.ndarray,
        **minimization_args) -> Tuple[numpy.ndarray, numpy.ndarray, float, float, Any]:
    """
    Find the best projection model adjustable parameters (in `'ECF'` coordinate frame)
    to fit the geophysical coordinate locations to the image coordinate locations.

    Parameters
    ----------
    struct : SICDType|SIDDType1|SIDDType2
    ecf_coords : numpy.ndarray
        The geophysical coordinates of shape `(N, 3)` for the identified features
    img_coords : numpy.ndarray
        The image coordinates of shape `(N, 2)` for the identified features
    minimization_args
        The keyword arguments (after `args` argument) passed through to
        :func:`scipy.optimize.minimize`. This will default to `'Powell'`
        optimization, which seems generally much more reliable for this
        problem than the steepest descent based approaches.

    Returns
    -------
    delta_arp : numpy.ndarray
    delta_varp : numpy.ndarray
    delta_range : float
    residue : float
        Average pixel coordinate distance across the features between projected
        and observed pixel locations
    result
        The minimization result
    """
    pass
