"""
Functionality for reading Cosmo Skymed data into a SICD model.
"""

__classification__ = "UNCLASSIFIED"
__author__ = ("Thomas McCullough", "Jarred Barber", "Wade Schwartzkopf")

import logging
from collections import OrderedDict
import os
import re
from typing import Tuple, Dict, BinaryIO, Union, Optional
from datetime import datetime

import numpy
from numpy.polynomial import polynomial
from scipy.constants import speed_of_light

import sarpy._extensions
from sarpy.compliance import bytes_to_string
from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.sicd_elements.blocks import Poly1DType, Poly2DType, RowColType
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd_elements.CollectionInfo import CollectionInfoType, RadarModeType
from sarpy.io.complex.sicd_elements.ImageCreation import ImageCreationType
from sarpy.io.complex.sicd_elements.RadarCollection import RadarCollectionType, \
    WaveformParametersType, ChanParametersType, TxStepType
from sarpy.io.complex.sicd_elements.ImageData import ImageDataType
from sarpy.io.complex.sicd_elements.GeoData import GeoDataType, SCPType
from sarpy.io.complex.sicd_elements.SCPCOA import SCPCOAType
from sarpy.io.complex.sicd_elements.Position import PositionType, XYZPolyType
from sarpy.io.complex.sicd_elements.Grid import GridType, DirParamType, WgtTypeType
from sarpy.io.complex.sicd_elements.Timeline import TimelineType, IPPSetType
from sarpy.io.complex.sicd_elements.ImageFormation import ImageFormationType, \
    RcvChanProcType
from sarpy.io.complex.sicd_elements.RMA import RMAType, INCAType
from sarpy.io.complex.sicd_elements.Radiometric import RadiometricType
from sarpy.io.general.base import SarpyIOError
from sarpy.io.general.data_segment import HDF5DatasetSegment
from sarpy.io.general.format_function import ComplexFormatFunction
from sarpy.io.general.utils import get_seconds, parse_timestring, is_file_like, is_hdf5, h5py
from sarpy.io.complex.utils import fit_time_coa_polynomial, fit_position_xvalidation

logger = logging.getLogger(__name__)

_unhandled_id_text = 'Unhandled mission id `{}`'


##########
# helper functions

def _extract_attrs(h5_element, out=None):
    pass


def load_addin():
    """Check for a CSK addin module"""
    pass


###########
# parser and interpreter for hdf5 attributes

class CSKDetails(object):
    """
    Parses and converts the Cosmo Skymed metadata
    """

    __slots__ = ('_file_name', '_mission_id', '_product_type')

    def __init__(self, file_name: str):
        """

        Parameters
        ----------
        file_name : str
        """

        if h5py is None:
            raise ImportError("Can't read Cosmo Skymed files, because the h5py dependency is missing.")

        if not os.path.isfile(file_name):
            raise SarpyIOError('Path {} is not a file'.format(file_name))

        with h5py.File(file_name, 'r') as hf:
            try:
                self._mission_id = hf.attrs['Mission ID'].decode('utf-8')
            except KeyError:
                raise SarpyIOError('The hdf file does not have the top level attribute "Mission ID"')
            try:
                self._product_type = hf.attrs['Product Type'].decode('utf-8')
            except KeyError:
                raise SarpyIOError('The hdf file does not have the top level attribute "Product Type"')

        if self._mission_id not in ['CSK', 'CSG', 'KMPS']:
            raise ValueError('Expected hdf5 attribute `Mission ID` should be one of "CSK", "CSG", or "KMPS"). '
                             'Got Mission ID = {}.'.format(self._mission_id))
        if 'SCS' not in self._product_type:
            raise ValueError('Expected hdf to contain complex products '
                             '(attribute `Product Type` which contains "SCS"). '
                             'Got Product Type = {}'.format(self._product_type))

        self._file_name = file_name

    @property
    def file_name(self) -> str:
        """
        str: the file name
        """
        pass

    @property
    def mission_id(self) -> str:
        """
        str: the mission id
        """
        pass

    @property
    def product_type(self) -> str:
        """
        str: the product type
        """
        pass

    def _get_hdf_dicts(self) -> (dict, dict, Dict[str, Tuple[int, ...]], Dict[str, numpy.dtype], Dict[str, str]):
        pass

    @staticmethod
    def _parse_pol(str_in: str) -> str:
        pass

    def _get_polarization(self, h5_dict: dict, band_dict: dict, band_name: str) -> str:
        pass

    def _get_base_sicd(self, h5_dict: dict, band_dict: dict) -> SICDType:
        pass

    def _get_dop_poly_details(self,
                              h5_dict: dict,
                              band_dict: dict,
                              band_name: str) -> (float, float, numpy.ndarray, numpy.ndarray, numpy.ndarray):
        pass

    def _get_band_specific_sicds(self,
                                 base_sicd: SICDType,
                                 h5_dict: dict,
                                 band_dict: dict,
                                 shape_dict: dict,
                                 pixeltype_dict: dict) -> Dict[str, SICDType]:
        pass

    @staticmethod
    def _get_symmetry(h5_dict: dict) -> (Optional[Tuple[int, ...]], Tuple[int, ...]):
        pass

    def get_sicd_collection(self) -> (
            Dict[str, SICDType], Dict[str, Tuple[int, ...]], Optional[Tuple[int, ...]], Tuple[int, ...]):
        """
        Get the sicd collection for the bands.

        Returns
        -------
        sicd_dict : Dict[str, SICDType]
            Of the form {band_name: sicd}
        shape_dict : Dict[str, Tuple[int, ...]]
            Of the form {band_name: shape}
        dtype_dict : Dict[str, numpy.dtype]
            Of the form {band_name: data type string}
        reverse_axes : Optional[Tuple[int, ...]]
        transpose_axes : Tuple[int, ...]
        """
        pass


################
# The CSK reader


class CSKReader(SICDTypeReader):
    """
    A Cosmo SkyMed 1st or 2nd generation SLC reader implementation.

    **Changed in version 1.3.0** for reading changes.
    """

    __slots__ = ('_csk_details', )

    def __init__(self, csk_details):
        """

        Parameters
        ----------
        csk_details : str|CSKDetails
            file name or CSKDetails object
        """

        if isinstance(csk_details, str):
            csk_details = CSKDetails(csk_details)
        if not isinstance(csk_details, CSKDetails):
            raise TypeError('The input argument for a CSKReader must be a '
                            'filename or CSKDetails object')
        self._csk_details = csk_details
        sicd_data, shape_dict, dtype_dict, reverse_axes, transpose_axes = csk_details.get_sicd_collection()
        data_segments = []
        sicds = []
        for band_name in sicd_data:
            if self._csk_details.mission_id in ['CSK', 'KMPS']:
                the_band = '{}/SBI'.format(band_name)
            elif self._csk_details.mission_id == 'CSG':
                the_band = '{}/IMG'.format(band_name)
            else:
                raise ValueError(_unhandled_id_text.format(self._csk_details.mission_id))

            sicds.append(sicd_data[band_name])
            basic_shape = shape_dict[band_name]
            data_segments.append(
                HDF5DatasetSegment(
                    csk_details.file_name, the_band,
                    formatted_dtype='complex64', formatted_shape=(basic_shape[1], basic_shape[0]),
                    reverse_axes=reverse_axes, transpose_axes=transpose_axes,
                    format_function=ComplexFormatFunction(raw_dtype=dtype_dict[band_name], order='IQ', band_dimension=2),
                    close_file=True))

        SICDTypeReader.__init__(self, data_segments, sicds, close_segments=True)
        self._check_sizes()

    @property
    def csk_details(self) -> CSKDetails:
        """
        CSKDetails: The details object.
        """
        pass

    @property
    def file_name(self) -> str:
        pass


########
# base expected functionality for a module with an implemented Reader


def is_a(file_name: Union[str, BinaryIO]) -> Union[None, CSKReader]:
    """
    Tests whether a given file_name corresponds to a Cosmo Skymed file. Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str|BinaryIO
        the file_name to check

    Returns
    -------
    CSKReader|None
        `CSKReader` instance if Cosmo Skymed file, `None` otherwise
    """
    pass
