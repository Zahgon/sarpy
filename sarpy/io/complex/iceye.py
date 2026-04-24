"""
Functionality for reading ICEYE complex data into a SICD model.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import logging
import os
from typing import Union, Tuple, Sequence, Optional

import numpy
from numpy.polynomial import polynomial
from scipy.constants import speed_of_light

from sarpy.io.complex.nisar import _stringify
from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.sicd_elements.blocks import Poly2DType, Poly1DType
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd_elements.CollectionInfo import CollectionInfoType, \
    RadarModeType
from sarpy.io.complex.sicd_elements.ImageCreation import ImageCreationType
from sarpy.io.complex.sicd_elements.RadarCollection import RadarCollectionType, \
    ChanParametersType, WaveformParametersType
from sarpy.io.complex.sicd_elements.ImageData import ImageDataType
from sarpy.io.complex.sicd_elements.GeoData import GeoDataType, SCPType
from sarpy.io.complex.sicd_elements.Position import PositionType, XYZPolyType
from sarpy.io.complex.sicd_elements.Grid import GridType, DirParamType, WgtTypeType
from sarpy.io.complex.sicd_elements.Timeline import TimelineType, IPPSetType
from sarpy.io.complex.sicd_elements.ImageFormation import ImageFormationType, \
    RcvChanProcType
from sarpy.io.complex.sicd_elements.RMA import RMAType, INCAType
from sarpy.io.complex.sicd_elements.Radiometric import RadiometricType
from sarpy.io.complex.utils import fit_position_xvalidation, two_dim_poly_fit

from sarpy.io.general.base import SarpyIOError
from sarpy.io.general.data_segment import HDF5DatasetSegment, BandAggregateSegment
from sarpy.io.general.format_function import ComplexFormatFunction
from sarpy.io.general.utils import get_seconds, parse_timestring, is_file_like, is_hdf5, h5py

logger = logging.getLogger(__name__)


def _parse_time(input_str: Union[bytes, str]) -> numpy.datetime64:
    """
    Parse the timestring.

    Parameters
    ----------
    input_str : bytes|str

    Returns
    -------
    numpy.datetime64
    """
    pass


class ICEYEDetails(object):
    """
    Parses and converts the ICEYE metadata.
    """
    __slots__ = ('_file_name', )

    def __init__(self, file_name: str):
        """

        Parameters
        ----------
        file_name : str
        """

        if h5py is None:
            raise ImportError("Can't read ICEYE files, because the h5py dependency is missing.")

        if not os.path.isfile(file_name):
            raise SarpyIOError('Path {} is not a file'.format(file_name))

        with h5py.File(file_name, 'r') as hf:
            if 's_q' not in hf or 's_i' not in hf:
                raise SarpyIOError(
                    'The hdf file does not have the real (s_q) or imaginary dataset (s_i).')
            if 'satellite_name' not in hf:
                raise SarpyIOError('The hdf file does not have the satellite_name dataset.')
            if 'product_name' not in hf:
                raise SarpyIOError('The hdf file does not have the product_name dataset.')

        self._file_name = file_name

    @property
    def file_name(self) -> str:
        """
        str: the file name
        """
        pass

    def get_sicd(self) -> (SICDType, Optional[Tuple[int, ...]], Tuple[int, ...]):
        """
        Gets the SICD structure and associated details for constructing the data segment.

        Returns
        -------
        sicd : SICDType
        reverse_axes : None|Tuple[int, ...]
        transpose_axes : Tuple[int, ...]
        """
        pass


def get_iceye_data_segment(
        file_name: str,
        reverse_axes: Union[None, int, Sequence[int]],
        transpose_axes: Union[None, Tuple[int, ...]],
        real_group: str = 's_i',
        imaginary_grop: str = 's_q') -> BandAggregateSegment:
    pass


class ICEYEReader(SICDTypeReader):
    """
    An ICEYE SLC reader implementation.

    **Changed in version 1.3.0** for reading changes.
    """

    __slots__ = ('_iceye_details', )

    def __init__(self, iceye_details):
        """

        Parameters
        ----------
        iceye_details : str|ICEYEDetails
            file name or ICEYEDetails object
        """

        if isinstance(iceye_details, str):
            iceye_details = ICEYEDetails(iceye_details)
        if not isinstance(iceye_details, ICEYEDetails):
            raise TypeError('The input argument for a ICEYEReader must be a '
                            'filename or ICEYEDetails object')
        self._iceye_details = iceye_details
        sicd, reverse_axes, transpose_axes = iceye_details.get_sicd()
        data_segment = get_iceye_data_segment(iceye_details.file_name, reverse_axes, transpose_axes)

        SICDTypeReader.__init__(self, data_segment, sicd, close_segments=True)
        self._check_sizes()

    @property
    def iceye_details(self) -> ICEYEDetails:
        """
        ICEYEDetails: The ICEYE details object.
        """
        pass

    @property
    def file_name(self):
        pass


########
# base expected functionality for a module with an implemented Reader

def is_a(file_name: str) -> Union[None, ICEYEReader]:
    """
    Tests whether a given file_name corresponds to a ICEYE file. Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str|BinaryIO
        the file_name to check

    Returns
    -------
    None|ICEYEReader
        `ICEYEReader` instance if ICEYE file, `None` otherwise
    """
    pass
