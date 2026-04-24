"""
Functionality for reading NISAR data into a SICD model.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import logging
import os
from collections import OrderedDict
from typing import Tuple, Dict, Union, List, Sequence, Optional

import numpy
from numpy.polynomial import polynomial
from scipy.constants import speed_of_light

from sarpy.compliance import bytes_to_string
from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.sicd_elements.blocks import Poly2DType
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd_elements.CollectionInfo import CollectionInfoType, RadarModeType
from sarpy.io.complex.sicd_elements.ImageCreation import ImageCreationType
from sarpy.io.complex.sicd_elements.RadarCollection import RadarCollectionType, \
    ChanParametersType, TxStepType
from sarpy.io.complex.sicd_elements.ImageData import ImageDataType
from sarpy.io.complex.sicd_elements.GeoData import GeoDataType, SCPType
from sarpy.io.complex.sicd_elements.SCPCOA import SCPCOAType
from sarpy.io.complex.sicd_elements.Position import PositionType, XYZPolyType
from sarpy.io.complex.sicd_elements.Grid import GridType, DirParamType, WgtTypeType
from sarpy.io.complex.sicd_elements.Timeline import TimelineType, IPPSetType
from sarpy.io.complex.sicd_elements.ImageFormation import ImageFormationType, \
    RcvChanProcType
from sarpy.io.complex.sicd_elements.RMA import RMAType, INCAType
from sarpy.io.complex.sicd_elements.Radiometric import RadiometricType, NoiseLevelType_
from sarpy.geometry import point_projection
from sarpy.io.complex.utils import fit_position_xvalidation, two_dim_poly_fit

from sarpy.io.general.base import SarpyIOError
from sarpy.io.general.data_segment import HDF5DatasetSegment
from sarpy.io.general.format_function import ComplexFormatFunction
from sarpy.io.general.utils import get_seconds, parse_timestring, is_file_like, is_hdf5, h5py

if h5py is None:
    h5pyFile = None
    h5pyGroup = None
    h5pyDataset = None
else:
    from h5py import File as h5pyFile, Group as h5pyGroup, Dataset as h5pyDataset

logger = logging.getLogger(__name__)


###########
# parser and interpreter for hdf5 attributes

def _stringify(val: Union[str, bytes]) -> str:
    """
    Decode the value as necessary, for hdf5 string support issues.

    Parameters
    ----------
    val : str|bytes

    Returns
    -------
    str
    """

    return bytes_to_string(val).strip()


def _get_ref_time(str_in: Union[str, bytes]) -> numpy.datetime64:
    """
    Extract the given reference time.

    Parameters
    ----------
    str_in : str|bytes

    Returns
    -------
    numpy.datetime64
    """
    pass


def _get_string_list(array: Sequence[bytes]) -> List[str]:
    pass


class NISARDetails(object):
    """
    Parses and converts the Cosmo Skymed metadata
    """

    __slots__ = ('_file_name', )

    def __init__(self, file_name: str):
        """

        Parameters
        ----------
        file_name : str
        """

        if h5py is None:
            raise ImportError("Can't read NISAR files, because the h5py dependency is missing.")

        if not os.path.isfile(file_name):
            raise SarpyIOError('Path {} is not a file'.format(file_name))

        with h5py.File(file_name, 'r') as hf:
            # noinspection PyBroadException
            try:
                # noinspection PyUnusedLocal
                gp = hf['/science/LSAR/SLC']
            except Exception as e:
                raise SarpyIOError('Got an error when reading required path /science/LSAR/SLC\n\t{}'.format(e))

        self._file_name = file_name

    @property
    def file_name(self) -> str:
        """
        str: the file name
        """
        pass

    @staticmethod
    def _get_frequency_list(hf: h5pyFile) -> List[str]:
        """
        Gets the list of frequencies.

        Parameters
        ----------
        hf : h5py.File

        Returns
        -------
        numpy.ndarray
        """
        pass

    @staticmethod
    def _get_collection_times(hf: h5pyFile) -> Tuple[numpy.datetime64, numpy.datetime64, float]:
        """
        Gets the collection start and end times, and inferred duration.

        Parameters
        ----------
        hf : h5py.File
            The h5py File object.

        Returns
        -------
        start_time : numpy.datetime64
        end_time : numpy.datetime64
        duration : float
        """
        pass

    @staticmethod
    def _get_zero_doppler_data(
            hf: h5pyFile,
            base_sicd: SICDType) -> Tuple[numpy.ndarray, float, numpy.ndarray, numpy.ndarray]:
        """
        Gets zero-doppler parameters.

        Parameters
        ----------
        hf : h5py.File
        base_sicd : SICDType

        Returns
        -------
        azimuth_zero_doppler_times : numpy.ndarray
        azimuth_zero_doppler_spacing : float
        grid_range_array : numpy.ndarray
        range_zero_doppler_times : numpy.ndarray
        """
        pass

    def _get_base_sicd(self, hf: h5pyFile) -> SICDType:
        """
        Defines the base SICD object, to be refined with further details.

        Returns
        -------
        SICDType
        """
        pass

    @staticmethod
    def _get_freq_specific_sicd(
            gp: h5pyGroup,
            base_sicd: SICDType) -> Tuple[SICDType, List[str], List[str], float]:
        """
        Gets the frequency specific sicd.

        Parameters
        ----------
        gp : h5py.Group
        base_sicd : SICDType

        Returns
        -------
        sicd: SICDType
        pol_names : numpy.ndarray
        pols : List[str]
        center_frequency : float
        """
        pass

    @staticmethod
    def _get_pol_specific_sicd(
            hf: h5pyFile,
            ds: h5pyDataset,
            base_sicd: SICDType,
            pol_name: str,
            freq_name: str,
            j: int,
            pol: str,
            r_ca_sampled: numpy.ndarray,
            zd_time: numpy.ndarray,
            grid_zd_time: numpy.ndarray,
            grid_r: numpy.ndarray,
            doprate_sampled: numpy.ndarray,
            dopcentroid_sampled: numpy.ndarray,
            center_freq: float,
            ss_az_s: float,
            dop_bw: float,
            beta0,
            gamma0,
            sigma0) -> Tuple[SICDType, Tuple[int, ...], numpy.dtype]:
        """
        Gets the frequency/polarization specific sicd.

        Parameters
        ----------
        hf : h5py.File
        ds : h5py.Dataset
        base_sicd : SICDType
        pol_name : str
        freq_name : str
        j : int
        pol : str
        r_ca_sampled : numpy.ndarray
        zd_time : numpy.ndarray
        grid_zd_time : numpy.ndarray
        grid_r : numpy.ndarray
        doprate_sampled : numpy.ndarray
        dopcentroid_sampled : numpy.ndarray
        center_freq : float
        ss_az_s : float
        dop_bw : float

        Returns
        -------
        sicd: SICDType
        shape : Tuple[int, ...]
        numpy.dtype
        """
        pass

    def get_sicd_collection(self) -> Tuple[
            Dict[str, SICDType],
            Dict[str, Tuple[Tuple[int, ...], numpy.dtype]],
            Optional[Tuple[int, ...]],
            Optional[Tuple[int, ...]]]:
        """
        Get the sicd collection for the bands.

        Returns
        -------
        sicd_dict : Dict[str, SICDType]
        shape_dict : Dict[str, Tuple[Tuple[int, ...], numpy.dtype]]
        reverse_axes : None|Tuple[int, ...]
        transpose_axes : None|Tuple[int, ...]
        """
        pass


################
# The NISAR reader

class NISARReader(SICDTypeReader):
    """
    An NISAR SLC reader implementation.

    **Changed in version 1.3.0** for reading changes.
    """

    __slots__ = ('_nisar_details', )

    def __init__(self, nisar_details: Union[str, NISARDetails]):
        """

        Parameters
        ----------
        nisar_details : str|NISARDetails
            file name or NISARDetails object
        """

        if isinstance(nisar_details, str):
            nisar_details = NISARDetails(nisar_details)
        if not isinstance(nisar_details, NISARDetails):
            raise TypeError('The input argument for NISARReader must be a '
                            'filename or NISARDetails object')
        self._nisar_details = nisar_details
        sicd_data, shape_dict, reverse_axes, transpose_axes = nisar_details.get_sicd_collection()
        data_segments = []
        sicds = []
        for band_name in sicd_data:
            sicds.append(sicd_data[band_name])
            raw_shape, raw_dtype = shape_dict[band_name]
            formatted_shape = (raw_shape[1], raw_shape[0]) if transpose_axes is not None \
                else raw_shape[:2]
            if raw_dtype.name == 'complex64':
                formatted_dtype = raw_dtype
                format_function = None
            else:
                formatted_dtype = 'complex64'
                format_function = ComplexFormatFunction(raw_dtype=raw_dtype, order='IQ', band_dimension=-1)

            data_segments.append(
                HDF5DatasetSegment(
                    nisar_details.file_name, band_name,
                    formatted_dtype=formatted_dtype, formatted_shape=formatted_shape,
                    reverse_axes=reverse_axes, transpose_axes=transpose_axes,
                    format_function=format_function, close_file=True))

        SICDTypeReader.__init__(self, data_segments, sicds, close_segments=True)
        self._check_sizes()

    @property
    def nisar_details(self) -> NISARDetails:
        """
        NISARDetails: The nisar details object.
        """
        pass

    @property
    def file_name(self) -> str:
        pass


########
# base expected functionality for a module with an implemented Reader


def is_a(file_name: str) -> Optional[NISARReader]:
    """
    Tests whether a given file_name corresponds to a NISAR file. Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str|BinaryIO
        the file_name to check

    Returns
    -------
    NISARReader|None
        `NISARReader` instance if NISAR file, `None` otherwise
    """
    pass
