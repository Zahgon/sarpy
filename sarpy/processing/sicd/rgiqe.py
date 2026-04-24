"""
Radar Generalized Image Quality Equation (RGIQE) calculation(s) and tools for
application to SICD structures and files.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import logging
from typing import Union, Tuple, Dict, Optional

import numpy

from sarpy.io.complex.base import SICDTypeReader, FlatSICDReader
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.processing.sicd.windows import get_hamming_broadening_factor
from sarpy.processing.sicd.normalize_sicd import sicd_degrade_reweight, is_uniform_weight
from sarpy.io.complex.converter import open_complex

logger = logging.getLogger(__name__)

RNIIRS_FIT_PARAMETERS = numpy.array([3.4761, 0.4357], dtype='float64')
"""
The RNIIRS calculation parameters determined by empirical data fit, 
parameters updated on 2022-02-01
"""


#####################
# methods for extracting necessary information from the sicd structure

def _verify_sicd_with_noise(sicd: SICDType) -> None:
    """
    Verify that the sicd is appropriately populated with noise.

    Parameters
    ----------
    sicd : SICDType
    """

    if sicd.Radiometric is None:
        raise ValueError(
            'Radiometric is not populated,\n\t'
            'so no noise estimate can be derived.')
    if sicd.Radiometric.SigmaZeroSFPoly is None:
        raise ValueError(
            'Radiometric.SigmaZeroSFPoly is not populated,\n\t'
            'so no sigma0 noise estimate can be derived.')
    if sicd.Radiometric.NoiseLevel is None:
        raise ValueError(
            'Radiometric.NoiseLevel is not populated,\n\t'
            'so no noise estimate can be derived.')
    if sicd.Radiometric.NoiseLevel.NoiseLevelType != 'ABSOLUTE':
        raise ValueError(
            'Radiometric.NoiseLevel.NoiseLevelType is not `ABSOLUTE``,\n\t'
            'so no noise estimate can be derived.')


def get_sigma0_noise(sicd: SICDType) -> float:
    """
    Calculate the absolute noise estimate, in sigma0 power units.

    Parameters
    ----------
    sicd : SICDType

    Returns
    -------
    float
    """

    _verify_sicd_with_noise(sicd)
    noise = sicd.Radiometric.NoiseLevel.NoisePoly[0, 0]  # this is in db
    noise = numpy.exp(numpy.log(10)*0.1*noise)  # this is absolute

    # convert to SigmaZero value
    noise *= sicd.Radiometric.SigmaZeroSFPoly[0, 0]
    return noise


def get_default_signal_estimate(sicd: SICDType) -> float:
    """
    Gets default signal for use in the RNIIRS calculation. This will be
    1.0 for copolar (or unknown) collections, and 0.25 for cross-pole
    collections.

    Parameters
    ----------
    sicd : SICDType

    Returns
    -------
    float
    """

    if sicd.ImageFormation is None or sicd.ImageFormation.TxRcvPolarizationProc is None:
        return 1.0

    # use 1.0 for co-polar collection and 0.25 from cross-polar collection
    pol = sicd.ImageFormation.TxRcvPolarizationProc
    if pol is None or ':' not in pol:
        return 1.0

    pols = pol.split(':')

    return 1.0 if pols[0] == pols[1] else 0.25


def get_bandwidth_area(sicd: SICDType) -> float:
    """
    Calculate the bandwidth area.

    Parameters
    ----------
    sicd : SICDType

    Returns
    -------
    float
    """

    return abs(
        sicd.Grid.Row.ImpRespBW *
        sicd.Grid.Col.ImpRespBW *
        numpy.cos(numpy.deg2rad(sicd.SCPCOA.SlopeAng)))


#########################
# methods for calculating information density and rniirs

def get_information_density(
        bandwidth_area: Union[float, numpy.ndarray],
        signal: Union[float, numpy.ndarray],
        noise: Union[float, numpy.ndarray]) -> Union[float, numpy.ndarray]:
    """
    Calculate the information density from bandwidth area and signal/noise estimates.

    Parameters
    ----------
    bandwidth_area : float|numpy.ndarray
    signal : float|numpy.ndarray
    noise : float|numpy.ndarray

    Returns
    -------
    float|numpy.ndarray
    """

    return bandwidth_area * numpy.log2(1 + signal/noise)


def get_rniirs(
        information_density: Union[float, numpy.ndarray]) -> Union[float, numpy.ndarray]:
    r"""
    Calculate an RNIIRS estimate from the information density or
    Shannon-Hartley channel capacity.

    This mapping has been empirically determined by fitting Shannon-Hartley channel
    capacity to RNIIRS for some sample images.

    The basic model is given by
    :math:`rniirs = a_0 + a_1*\log_2(information\_density)`

    To maintain positivity of the estimated rniirs, this transitions to a linear
    model :math:`rniirs = slope*information\_density` with slope given by
    :math:`slope = a_1/(iim\_transition*\log(2))` below the transition point at
    :math:`transition = \exp(1 - \log(2)*a_0/a_1)`.

    Parameters
    ----------
    information_density : float|numpy.ndarray

    Returns
    -------
    float|numpy.ndarray
    """

    a = RNIIRS_FIT_PARAMETERS
    iim_transition = numpy.exp(1 - numpy.log(2) * a[0] / a[1])
    slope = a[1] / (iim_transition * numpy.log(2))

    if not isinstance(information_density, numpy.ndarray):
        information_density = numpy.array(information_density, dtype='float64')
    orig_ndim = information_density.ndim
    if orig_ndim == 0:
        information_density = numpy.reshape(information_density, (1, ))

    out = numpy.empty(information_density.shape, dtype='float64')
    mask = (information_density > iim_transition)
    mask_other = ~mask
    if numpy.any(mask):
        out[mask] = a[0] + a[1]*numpy.log2(information_density[mask])
    if numpy.any(mask_other):
        out[mask_other] = slope*information_density[mask_other]

    if orig_ndim == 0:
        return float(out[0])
    return out


def get_information_density_for_rniirs(
        rniirs: Union[float, numpy.ndarray]) -> Union[float, numpy.ndarray]:
    """
    The inverse of :func:`get_rniirs`, this determines the information density
    which yields the given RNIIRS.

    *New in version 1.2.35.*

    Parameters
    ----------
    rniirs : float|numpy.ndarray

    Returns
    -------
    float|numpy.ndarray
    """
    pass


def snr_to_rniirs(
        bandwidth_area: Union[float, numpy.ndarray],
        signal: Union[float, numpy.ndarray],
        noise: Union[float, numpy.ndarray]) -> Tuple[Union[float, numpy.ndarray], Union[float, numpy.ndarray]]:
    """
    Calculate the information_density and RNIIRS estimate from bandwidth area and
    signal/noise estimates.

    It is assumed that geometric effects for signal and noise have been accounted for
    (i.e. use SigmaZeroSFPoly), and signal and noise have each been averaged to a
    single pixel value.

    This mapping has been empirically determined by fitting Shannon-Hartley channel
    capacity to RNIIRS for some sample images.

    Parameters
    ----------
    bandwidth_area : float
    signal : float
    noise : float

    Returns
    -------
    information_density : float
    rniirs : float
    """

    information_density = get_information_density(bandwidth_area, signal, noise)
    rniirs = get_rniirs(information_density)
    return information_density, rniirs


def rgiqe(sicd: SICDType) -> Tuple[float, float]:
    """
    Calculate the information_density and (default) estimated RNIIRS for the
    given sicd.

    Parameters
    ----------
    sicd : SICDType

    Returns
    -------
    information_density : float
    rniirs : float
    """
    pass


def populate_rniirs_for_sicd(
        sicd: SICDType,
        signal: Optional[float] = None,
        noise: Optional[float] = None,
        override: bool = False) -> None:
    """
    This populates the value(s) for RNIIRS and information density in the SICD
    structure, according to the RGIQE. **This modifies the sicd structure in place.**

    Parameters
    ----------
    sicd : sarpy.io.complex.sicd_elements.SICD.SICDType
    signal : None|float
        The signal value, in sigma zero.
    noise : None|float
        The noise equivalent sigma zero value.
    override : bool
        Override the value, if present.
    """

    if sicd.CollectionInfo is None:
        logger.error(
            'CollectionInfo must not be None.\n\t'
            'Nothing to be done for calculating RNIIRS.')
        return

    if sicd.CollectionInfo.Parameters is not None and \
            sicd.CollectionInfo.Parameters.get('PREDICTED_RNIIRS', None) is not None:
        if override:
            logger.info('PREDICTED_RNIIRS already populated, and this value will be overridden.')
        else:
            logger.info('PREDICTED_RNIIRS already populated. Nothing to be done.')
            return

    if noise is None:
        try:
            noise = get_sigma0_noise(sicd)
        except Exception as e:
            logger.error(
                'Encountered an error estimating noise for RNIIRS.\n\t{}'.format(e))
            return

    if signal is None:
        signal = get_default_signal_estimate(sicd)

    try:
        bw_area = get_bandwidth_area(sicd)
    except Exception as e:
        logger.error(
            'Encountered an error estimating bandwidth area for RNIIRS\n\t{}'.format(e))
        return

    inf_density, rniirs = snr_to_rniirs(bw_area, signal, noise)
    logger.info(
        'Calculated INFORMATION_DENSITY = {0:0.5G},\n\t'
        'PREDICTED_RNIIRS = {1:0.5G}'.format(inf_density, rniirs))
    if sicd.CollectionInfo.Parameters is None:
        sicd.CollectionInfo.Parameters = {}  # initialize
    sicd.CollectionInfo.Parameters['INFORMATION_DENSITY'] = '{0:0.2G}'.format(inf_density)
    sicd.CollectionInfo.Parameters['PREDICTED_RNIIRS'] = '{0:0.1f}'.format(rniirs)


def get_bandwidth_noise_distribution(
        sicd: SICDType,
        alpha: Union[float, numpy.ndarray],
        desired_information_density: Optional[float] = None,
        desired_rniirs: Optional[float] = None
        ) -> Tuple[Union[Tuple[float, float], numpy.ndarray], Union[float, numpy.ndarray]]:
    r"""
    This function determines SICD degradation parameters (nominally symmetric in
    row/column subaperture degradation) to achieve the desired information density/rniirs.

    There is natural one parameter distribution of reducing bandwidth and adding noise
    to achieve the desired RNIIRS/information density, based on :math:`\alpha \in [0, 1]`.

    The nominal relation is

    .. math::

        desired\_information\_density = bandwidth\_area*(bw\_mult(\alpha))^2)\cdot\log_2\left(
        1 + signal/(noise*noise\_mult(\alpha))\right).

    For :math:`\alpha=0`, we add no additional noise (:math:`bw\_mult(0) = bw\_min,noise\_mult(0)=1`)
    and use purely sub-aperture degradation, achieved at

    .. math::

        desired\_information\_density = bandwidth\_area*(bw\_min)^2)\cdot\log_2(1 + snr).

    On the other end, at :math:`\alpha=1`, we have :math:`bw\_mult(1)=1, noise\_mult(1)=noise\_mult\_max`
    and derive the noise multiplier which fulfills the required information density.
    For intermediate :math:`0 < \alpha < 1`, we find

    .. math::

        bw_mult(\alpha) = bw\_min\cdot (1-\alpha)

    Then, we find :math:`noise\_multiplier(\alpha)` which fulfills the required
    information density.

    .. note::

        Choosing subaperture windows is fundamentally a discrete operation, and
        this carries over to the realities of choosing bandwidth multipliers. See
        :func:`get_bidirectional_bandwidth_multiplier_possibilities` for all
        feasible values for bandwidth multipliers and associated noise adjustment
        details.

    *Refined in version 1.2.35.*

    Parameters
    ----------
    sicd : sarpy.io.complex.sicd_elements.SICD.SICDType
    alpha : float|numpy.ndarray
    desired_information_density : None|float
    desired_rniirs : None|float

    Returns
    -------
    bandwidth_multiplier : (float, float)|numpy.ndarray
        The `(row, column)` bandwidth multiplier including the discrete nature
        of this aperture, so the two may not be precisely equal.
    noise_multiplier : float|numpy.ndarray
        The noise multiplier, indicating how much noise to add before the
        subaperture processing.
    """
    pass


#########################
# helpers for quality degradation function

def _get_uniform_weight_dicts(
        sicd: SICDType) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Gets the dictionaries denoting uniform weighting.

    Parameters
    ----------
    sicd : sarpy.io.complex.sicd_elements.SICD.SICDType

    Returns
    -------
    row_weighting : None|dict
    column_weighting : None|dict
    """
    pass


def _validate_reader(
        reader: Union[str, SICDTypeReader],
        index: int) -> Tuple[SICDTypeReader, int]:
    """
    Validate the method input:

    Parameters
    ----------
    reader : str|SICDTypeReader
    index : int
        The reader index.

    Returns
    -------
    reader: SICDTypeReader
    index: int
    """
    pass


def _map_desired_resolution_to_aperture(
        current_imp_resp_bw: float,
        sample_size: float,
        direction: str,
        direction_size: int,
        desired_resolution: Optional[float] = None,
        desired_bandwidth: Optional[float] = None,
        broadening_factor: Optional[float] = None) -> Tuple[Optional[Tuple[int, int]], float]:
    """
    Determine the appropriate symmetric subaperture range to achieve the desired
    bandwidth or resolution, assuming the given broadening factor.

    Parameters
    ----------
    current_imp_resp_bw : float
    sample_size : float
    direction : str
    direction_size : int
        The size of the array along the given direction.
    desired_resolution : None|float
        The desired ImpRespWid (Row, Col) tuple, which will be mapped to ImpRespBW
        assuming uniform weighting. Exactly one of `desired_resolution` and
        `desired_bandwidth` must be provided.
    desired_bandwidth : None|float
        The desired ImpRespBW. Exactly one of `desired_resolution`
        and `desired_bandwidth` must be provided.
    broadening_factor : None|float
        The only applies if `desired_resolution` is provided. If not provided,
        then UNIFORM weighting will be assumed.

    Returns
    -------
    indices: None|Tuple[int, int]
    bw_factor : float
    """
    pass


def _map_bandwidth_parameters(
        sicd: SICDType,
        desired_resolution: Optional[Tuple[float, float]] = None,
        desired_bandwidth: Optional[Tuple[float, float]] = None
        ) -> Tuple[Tuple[int, int], float, Tuple[int, int], float]:
    """
    Helper function to map desired resolution or bandwidth to the suitable (centered)
    aperture.

    Parameters
    ----------
    sicd : SICDType
    desired_resolution : None|Tuple[float, float]
    desired_bandwidth : None|Tuple[float, float]

    Returns
    -------
    row_aperture : Tuple[int, int]
    row_bw_factor : float
    column_aperture : Tuple[int, int]
    column_bw_factor : float
    """
    pass


def get_dimension_bandwidth_multiplier_possibilities(
        sicd: SICDType,
        dimension: int) -> Tuple[numpy.ndarray, numpy.ndarray]:
    """
    Gets the bandwidth possibilities for all centered subapertures along the given
    dimension.

    *Introduced in 1.2.35*

    Parameters
    ----------
    sicd : SICDType
    dimension : int
        One of `{0, 1}`.

    Returns
    -------
    aperture_size : numpy.ndarray
        Of shape `(N, )`
    bandwidth_multiplier : numpy.ndarray
        Of shape `(N, )`
    """
    pass


def get_bidirectional_bandwidth_multiplier_possibilities(
        sicd: SICDType) -> Tuple[numpy.ndarray, numpy.ndarray]:
    """
    Gets the bandwidth possibilities for all centered subapertures shrinking
    along both dimensions symmetrically.

    *Introduced in 1.2.35*

    Parameters
    ----------
    sicd : SICDType

    Returns
    -------
    aperture_size : numpy.ndarray
        An array of shape `(N, 2)` for row/column separately.
    bandwidth_multiplier : numpy.ndarray
        An array of shape `(N, 2)` for row/column separately.
    """
    pass


#########################
# SICD quality degradation functions

def quality_degrade(
        reader: Union[str, SICDTypeReader],
        index: int = 0,
        output_file: Optional[str] = None,
        desired_resolution: Optional[Tuple[float, float]] = None,
        desired_bandwidth: Optional[Tuple[float, float]] = None,
        desired_nesz: Optional[float] = None,
        **kwargs) -> Optional[FlatSICDReader]:
    r"""
    Create a degraded quality SICD based on the desired resolution (impulse response width)
    or bandwidth (impulse response bandwidth), and the desired Noise Equivalent
    Sigma Zero value. The produced SICD will have **uniform weighting**.

    No more than one of `desired_resolution` and `desired_bandwidth` can be provided.
    If None of `desired_resolution`, `desired_bandwidth`, or `desired_nesz` are provided,
    then the SICD will be re-weighted with uniform weighting - even this will
    change the noise and RNIIRS values slightly.

    .. warning::

        Unless `desired_nesz=None`, this will fail for a SICD which is not fully
        Radiometrically calibrated with `'ABSOLUTE'` noise type.


    Parameters
    ----------
    reader : str|SICDTypeReader
    index : int
        The reader index to be used.
    output_file : None|str
        If `None`, an in-memory SICD reader instance will be returned. Otherwise,
        this is the path for the produced output SICD file.
    desired_resolution : None|tuple
        The desired ImpRespWid (Row, Col) tuple, which will be mapped to ImpRespBW
        assuming uniform weighting. You cannot provide both `desired_resolution`
        and `desired_bandwidth`.
    desired_bandwidth : None|tuple
        The desired ImpRespBW (Row, Col) tuple. You cannot provide both
        `desired_resolution` and `desired_bandwidth`.
    desired_nesz : None|float
        The desired Noise Equivalent Sigma Zero value in power units, this is after
        modifications which change the noise due to sub-aperture degradation and/or
        de-weighting.
    kwargs
        Keyword arguments passed through to :func:`sarpy.processing.sicd.normalize_sicd.sicd_degrade_reweight`

    Returns
    -------
    None|FlatSICDReader
        No return if `output_file` is provided, otherwise the returns the in-memory
        reader object.
    """
    pass


def quality_degrade_resolution(
        reader: Union[str, SICDTypeReader],
        index: int = 0,
        output_file: Optional[str] = None,
        desired_resolution: Optional[Tuple[float, float]] = None,
        desired_bandwidth: Optional[Tuple[float, float]] = None,
        **kwargs) -> Optional[FlatSICDReader]:
    """
    Create a degraded quality SICD based on INCREASING the impulse response width
    to the desired resolution or DECREASING the impulse response bandwidth to the
    desired bandwidth.

    The produced SICD will have uniform weighting.

    Parameters
    ----------
    reader : str|SICDTypeReader
    index : int
        The reader index to be used.
    output_file : None|str
        If `None`, an in-memory SICD reader instance will be returned. Otherwise,
        this is the path for the produced output SICD file.
    desired_resolution : None|tuple
        The desired ImpRespWid (Row, Col) tuple, which will be mapped to ImpRespBW
        assuming uniform weighting. Exactly one of `desired_resolution` and
        `desired_bandwidth` must be provided.
    desired_bandwidth : None|tuple
        The desired ImpRespBW (Row, Col) tuple. Exactly one of `desired_resolution`
        and `desired_bandwidth` must be provided.
    kwargs
        Keyword arguments passed through to :func:`sarpy.processing.sicd.normalize_sicd.sicd_degrade_reweight`

    Returns
    -------
    None|FlatSICDReader
        No return if `output_file` is provided, otherwise the returns the in-memory
        reader object.
    """
    pass


def quality_degrade_noise(
        reader: Union[str, SICDTypeReader],
        index: int = 0,
        output_file: Optional[str] = None,
        desired_nesz: Optional[float] = None,
        **kwargs) -> Optional[FlatSICDReader]:
    """
    Create a degraded quality SICD based on INCREASING the noise to the desired
    Noise Equivalent Sigma Zero value. The produced SICD will have uniform weighting.

    .. warning::

        This will fail for a SICD which is not fully Radiometrically calibrated,
        with ABSOLUTE noise type.

    Parameters
    ----------
    reader : str|SICDTypeReader
    index : int
        The reader index to be used.
    output_file : None|str
        If `None`, an in-memory SICD reader instance will be returned. Otherwise,
        this is the path for the produced output SICD file.
    desired_nesz : None|float
        The desired noise equivalent sigma zero value.
    kwargs
        Keyword arguments passed through to :func:`sarpy.processing.sicd.normalize_sicd.sicd_degrade_reweight`

    Returns
    -------
    None|FlatSICDReader
        No return if `output_file` is provided, otherwise the returns the in-memory
        reader object.
    """
    pass


def quality_degrade_rniirs(
        reader: Union[str, SICDTypeReader],
        index: int = 0,
        output_file: Optional[str] = None,
        desired_rniirs: Optional[float] = None,
        alpha: float = 0,
        **kwargs) -> Optional[FlatSICDReader]:
    r"""
    Create a degraded quality SICD based on the desired estimated RNIIRS value.
    The produced SICD will have uniform weighting.

    The sicd degradation will be performed as follows:

    - The current information density/current rniirs **with respect to uniform weighting**
      will be found.

    - The information density required to produce the desired rniirs will be found.

    - This will be used, along with the :math:`\alpha` value, will be used in
      :func:`get_bandwidth_noise_distribution` to determine the best feasible
      multipliers for bandwidth and noise values.

    - These desired bandwidth and noise values will then be used in conjunction
      with :func:`sicd_degrade_reweight`.

    .. warning::

        This will fail for a SICD which is not fully Radiometrically calibrated,
        with `'ABSOLUTE'` noise type.

    Parameters
    ----------
    reader : str|SICDTypeReader
    index : int
        The reader index to be used.
    output_file : None|str
        If `None`, an in-memory SICD reader instance will be returned. Otherwise,
        this is the path for the produced output SICD file.
    desired_rniirs : None|float
        The desired rniirs value, according to the RGIQE methodology.
    alpha : float
        This must be a number in the interval [0, 1] defining the (geometric)
        distribution of variability between required influence from increasing
        noise and require influence of decreasing bandwidth.
    kwargs
        Keyword arguments passed through to :func:`sarpy.processing.sicd.normalize_sicd.sicd_degrade_reweight`

    Returns
    -------
    None|FlatSICDReader
        No return if `output_file` is provided, otherwise the returns the in-memory
        reader object.
    """
    pass
