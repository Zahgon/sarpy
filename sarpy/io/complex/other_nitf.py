"""
Work in progress for reading some other kind of complex NITF.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"

import logging
from typing import Union, Tuple, List, Optional, Callable, Sequence
import copy
from datetime import datetime

import numpy
from scipy.constants import foot

from sarpy.geometry.geocoords import geodetic_to_ecf, ned_to_ecf
from sarpy.geometry.latlon import num as lat_lon_parser

from sarpy.io.general.base import SarpyIOError
from sarpy.io.general.data_segment import DataSegment, SubsetSegment
from sarpy.io.general.format_function import FormatFunction, ComplexFormatFunction
from sarpy.io.general.nitf import extract_image_corners, NITFDetails, NITFReader
from sarpy.io.general.nitf_elements.security import NITFSecurityTags
from sarpy.io.general.nitf_elements.image import ImageSegmentHeader, ImageSegmentHeader0
from sarpy.io.general.nitf_elements.nitf_head import NITFHeader, NITFHeader0
from sarpy.io.general.nitf_elements.base import TREList
from sarpy.io.general.nitf_elements.tres.unclass.CMETAA import CMETAA
from sarpy.io.general.utils import is_file_like

from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd_elements.CollectionInfo import CollectionInfoType
from sarpy.io.complex.sicd_elements.ImageData import ImageDataType
from sarpy.io.complex.sicd_elements.GeoData import GeoDataType, SCPType
from sarpy.io.complex.sicd_elements.Grid import GridType, DirParamType, WgtTypeType
from sarpy.io.complex.sicd_elements.Timeline import TimelineType, IPPSetType
from sarpy.io.complex.sicd_elements.RadarCollection import RadarCollectionType, \
    TxFrequencyType, WaveformParametersType, ChanParametersType
from sarpy.io.complex.sicd_elements.SCPCOA import SCPCOAType
from sarpy.io.complex.sicd_elements.ImageFormation import ImageFormationType, TxFrequencyProcType
from sarpy.io.complex.sicd_elements.ImageCreation import ImageCreationType
from sarpy.io.complex.sicd_elements.PFA import PFAType


logger = logging.getLogger(__name__)

_iso_date_format = '{}-{}-{}T{}:{}:{}'

# NB: DO NOT implement is_a() here.
#   This will explicitly happen after other readers


########
# Define sicd structure from image sub-header information

def extract_sicd(
        img_header: Union[ImageSegmentHeader, ImageSegmentHeader0],
        transpose: True,
        nitf_header: Optional[Union[NITFHeader, NITFHeader0]] = None) -> SICDType:
    """
    Extract the best available SICD structure from relevant nitf header structures.

    Parameters
    ----------
    img_header : ImageSegmentHeader|ImageSegmentHeader0
    transpose : bool
    nitf_header : None|NITFHeader|NITFHeader0

    Returns
    -------
    SICDType
    """
    pass


# Helper methods for transforming data

def get_linear_magnitude_scaling(scale_factor: float):
    """
    Get a linear magnitude scaling function, to correct magnitude.

    Parameters
    ----------
    scale_factor : float
        The scale factor, according to the definition given in STDI-0002.

    Returns
    -------
    callable
    """
    pass


def get_linear_power_scaling(scale_factor):
    """
    Get a linear power scaling function, to derive correct magnitude.

    Parameters
    ----------
    scale_factor : float
        The scale factor, according to the definition given in STDI-0002.

    Returns
    -------
    callable
    """
    pass


def get_log_magnitude_scaling(scale_factor, db_per_step):
    """
    Gets the log magnitude scaling function, to derive correct magnitude.

    Parameters
    ----------
    scale_factor : float
        The scale factor, according to the definition given in STDI-0002.
    db_per_step : float
        The db_per_step factor, according to the definiton given in STDI-0002

    Returns
    -------
    callable
    """
    pass


def get_log_power_scaling(scale_factor, db_per_step):
    """
    Gets the log power scaling function, to derive correct magnitude.

    Parameters
    ----------
    scale_factor : float
        The scale factor, according to the definition given in STDI-0002.
    db_per_step : float
        The db_per_step factor, according to the definiton given in STDI-0002

    Returns
    -------
    callable
    """
    pass


def get_linlog_magnitude_scaling(scale_factor, tipping_point):
    """
    Gets the magnitude scaling function for the model which
    is initially linear, and then switches to logarithmic beyond a fixed
    tipping point.

    Parameters
    ----------
    scale_factor : float
        The scale factor, according to the definition given in STDI-0002.
    tipping_point : float
        The tipping point between the two models.

    Returns
    -------
    callable
    """
    pass


class ApplyAmplitudeScalingFunction(ComplexFormatFunction):
    __slots__ = ('_scaling_function', )
    _allowed_ordering = ('MP', 'PM')
    has_inverse = False

    def __init__(
            self,
            raw_dtype: Union[str, numpy.dtype],
            order: str,
            scaling_function: Optional[Callable] = None,
            raw_shape: Optional[Tuple[int, ...]] = None,
            formatted_shape: Optional[Tuple[int, ...]] = None,
            reverse_axes: Optional[Tuple[int, ...]] = None,
            transpose_axes: Optional[Tuple[int, ...]] = None,
            band_dimension: int = -1):
        """

        Parameters
        ----------
        raw_dtype : str|numpy.dtype
            The raw datatype. Valid options dependent on the value of order.
        order : str
            One of `('MP', 'PM')`, with allowable raw_dtype
            `('uint8', 'uint16', 'uint32', 'float32', 'float64')`.
        scaling_function : Optional[Callable]
        raw_shape : None|Tuple[int, ...]
        formatted_shape : None|Tuple[int, ...]
        reverse_axes : None|Tuple[int, ...]
        transpose_axes : None|Tuple[int, ...]
        band_dimension : int
            Which band is the complex dimension, **after** the transpose operation.
        """

        self._scaling_function = None
        ComplexFormatFunction.__init__(
            self, raw_dtype, order, raw_shape=raw_shape, formatted_shape=formatted_shape,
            reverse_axes=reverse_axes, transpose_axes=transpose_axes, band_dimension=band_dimension)
        self._set_scaling_function(scaling_function)

    @property
    def scaling_function(self) -> Optional[Callable]:
        """
        The magnitude scaling function.

        Returns
        -------
        None|Callable
        """
        pass

    def _set_scaling_function(self, value: Optional[Callable]):
        pass

    def _forward_magnitude_theta(
            self,
            data: numpy.ndarray,
            out: numpy.ndarray,
            magnitude: numpy.ndarray,
            theta: numpy.ndarray,
            subscript: Tuple[slice, ...]) -> None:
        if self._scaling_function is not None:
            magnitude = self._scaling_function(magnitude)
        ComplexFormatFunction._forward_magnitude_theta(
            self, data, out, magnitude, theta, subscript)


def _extract_transform_data(
        image_header: Union[ImageSegmentHeader, ImageSegmentHeader0],
        band_dimension: int):
    """
    Helper function for defining necessary transform_data definition for
    interpreting image segment data.

    Parameters
    ----------
    image_header : ImageSegmentHeader|ImageSegmentHeader0

    Returns
    -------
    None|str|callable
    """
    pass


######
# The interpreter and reader objects

class ComplexNITFDetails(NITFDetails):
    """
    Details object for NITF file containing complex data.
    """

    __slots__ = (
        '_segment_status', '_segment_bands', '_sicd_meta', '_reverse_axes', '_transpose_axes')

    def __init__(
            self,
            file_name: str,
            reverse_axes: Union[None, int, Sequence[int]] = None,
            transpose_axes: Optional[Tuple[int, ...]] = None):
        """

        Parameters
        ----------
        file_name : str
            file name for a NITF file containing a complex SICD
        reverse_axes : None|Sequence[int]
            Any entries should be restricted to `{0, 1}`. The presence of
            `0` means to reverse the rows (in the raw sense), and the presence
            of `1` means to reverse the columns (in the raw sense).
        transpose_axes : None|Tuple[int, ...]
            If presented this should be only `(1, 0)`.
        """

        self._reverse_axes = reverse_axes
        self._transpose_axes = transpose_axes
        self._segment_status = None
        self._sicd_meta = None
        self._segment_bands = None
        NITFDetails.__init__(self, file_name)
        self._find_complex_image_segments()
        if len(self.sicd_meta) == 0:
            raise SarpyIOError(
                'No complex valued image segments found in file {}'.format(file_name))

    @property
    def reverse_axes(self) -> Union[None, int, Sequence[int]]:
        pass

    @property
    def transpose_axes(self) -> Optional[Tuple[int, ...]]:
        pass

    @property
    def segment_status(self) -> Tuple[bool, ...]:
        """
        Tuple[bool, ...]: Where each image segment is viable for use.
        """
        pass

    @property
    def sicd_meta(self) -> Tuple[SICDType, ...]:
        """
        Tuple[SICDType, ...]: The best inferred sicd structures.
        """
        pass

    @property
    def segment_bands(self) -> Tuple[Tuple[int, Optional[int]], ...]:
        """
        This describes the structure for the output data segments from the NITF,
        with each entry of the form `(image_segment, output_band)`, where
        `output_band` will be `None` if the image segment has exactly one
        complex band.

        Returns
        -------
        Tuple[Tuple[int, Optional[int]], ...]
            The band details for use.
        """
        pass

    def _check_band_details(
            self,
            index: int,
            sicd_meta: List,
            segment_status: List,
            segment_bands: List):
        pass

    def _find_complex_image_segments(self):
        """
        Find complex image segments.

        Returns
        -------
        None
        """
        pass


class ComplexNITFReader(NITFReader, SICDTypeReader):
    """
    A reader for complex valued NITF elements, this should be explicitly tried AFTER
    the SICDReader.
    """

    def __init__(
            self,
            nitf_details: Union[str, ComplexNITFDetails],
            reverse_axes: Union[None, int, Sequence[int]] = None,
            transpose_axes: Optional[Tuple[int, ...]] = None):
        """

        Parameters
        ----------
        nitf_details : str|ComplexNITFDetails
        reverse_axes : None|Sequence[int]
            Any entries should be restricted to `{0, 1}`. The presence of
            `0` means to reverse the rows (in the raw sense), and the presence
            of `1` means to reverse the columns (in the raw sense).
        transpose_axes : None|Tuple[int, ...]
            If presented this should be only `(1, 0)`.
        """

        if isinstance(nitf_details, str):
            nitf_details = ComplexNITFDetails(
                nitf_details, reverse_axes=reverse_axes, transpose_axes=transpose_axes)
        if not isinstance(nitf_details, ComplexNITFDetails):
            raise TypeError('The input argument for ComplexNITFReader must be a filename or '
                            'ComplexNITFDetails object.')

        SICDTypeReader.__init__(self, None, nitf_details.sicd_meta)
        NITFReader.__init__(
            self,
            nitf_details,
            reader_type="SICD",
            reverse_axes=nitf_details.reverse_axes,
            transpose_axes=nitf_details.transpose_axes)
        self._check_sizes()

    @property
    def nitf_details(self) -> ComplexNITFDetails:
        """
        ComplexNITFDetails: The NITF details object.
        """
        pass

    def get_nitf_dict(self):
        """
        Populate a dictionary with the pertinent NITF header information. This
        is for use in more faithful preservation of NITF header information
        in copying or rewriting sicd files.

        Returns
        -------
        dict
        """

        out = {}
        security = {}
        security_obj = self.nitf_details.nitf_header.Security
        # noinspection PyProtectedMember
        for field in NITFSecurityTags._ordering:
            value = getattr(security_obj, field).strip()
            if value != '':
                security[field] = value
        if len(security) > 0:
            out['Security'] = security

        out['OSTAID'] = self.nitf_details.nitf_header.OSTAID
        out['FTITLE'] = self.nitf_details.nitf_header.FTITLE
        return out

    def populate_nitf_information_into_sicd(self):
        """
        Populate some pertinent NITF header information into the SICD structure.
        This provides more faithful copying or rewriting options.
        """

        nitf_dict = self.get_nitf_dict()
        for sicd_meta in self._sicd_meta:
            sicd_meta.NITF = copy.deepcopy(nitf_dict)

    def depopulate_nitf_information(self):
        """
        Eliminates the NITF information dict from the SICD structure.
        """
        pass

    def get_format_function(
            self,
            raw_dtype: numpy.dtype,
            complex_order: Optional[str],
            lut: Optional[numpy.ndarray],
            band_dimension: int,
            image_segment_index: Optional[int] = None,
            **kwargs) -> Optional[FormatFunction]:
        pass

    def _check_image_segment_for_compliance(
            self,
            index: int,
            img_header: Union[ImageSegmentHeader, ImageSegmentHeader0]) -> bool:
        pass

    def find_image_segment_collections(self) -> Tuple[Tuple[int, ...]]:
        pass

    def create_data_segment_for_collection_element(self, collection_index: int) -> DataSegment:
        pass


def final_attempt(file_name: str) -> Optional[ComplexNITFReader]:
    """
    Contingency check to open for some other complex NITF type file.
    Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str|BinaryIO
        the file_name to check

    Returns
    -------
    ComplexNITFReader|None
    """
    pass
