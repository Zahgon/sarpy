"""
Functionality for reading TerraSAR-X data into a SICD model.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import os
import logging
from xml.etree import ElementTree
from typing import Union, List, Tuple, Optional, BinaryIO
from functools import reduce
import struct

import numpy
import numpy.linalg
from numpy.polynomial import polynomial
from scipy.constants import speed_of_light

from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.sicd_elements.blocks import Poly1DType, Poly2DType
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd_elements.CollectionInfo import CollectionInfoType, RadarModeType
from sarpy.io.complex.sicd_elements.ImageCreation import ImageCreationType
from sarpy.io.complex.sicd_elements.RadarCollection import RadarCollectionType, \
    WaveformParametersType, ChanParametersType, TxStepType
from sarpy.io.complex.sicd_elements.ImageData import ImageDataType
from sarpy.io.complex.sicd_elements.GeoData import GeoDataType, SCPType
from sarpy.io.complex.sicd_elements.Position import PositionType, XYZPolyType
from sarpy.io.complex.sicd_elements.Grid import GridType, DirParamType, WgtTypeType
from sarpy.io.complex.sicd_elements.Timeline import TimelineType, IPPSetType
from sarpy.io.complex.sicd_elements.ImageFormation import ImageFormationType, \
    RcvChanProcType
from sarpy.io.complex.sicd_elements.RMA import RMAType, INCAType
from sarpy.io.complex.sicd_elements.Radiometric import RadiometricType, NoiseLevelType_
from sarpy.io.complex.utils import two_dim_poly_fit, fit_position_xvalidation

from sarpy.io.general.base import SarpyIOError
from sarpy.io.general.data_segment import DataSegment, NumpyMemmapSegment, SubsetSegment
from sarpy.io.general.format_function import ComplexFormatFunction
from sarpy.io.general.utils import get_seconds, parse_timestring, is_file_like


logger = logging.getLogger(__name__)


##########
# helper functions and basic interpreter

def _parse_xml(file_name: str, without_ns: bool = False) -> Union[
        ElementTree.Element, Tuple[dict, ElementTree.Element]]:
    pass


def _is_level1_product(prospective_file: str) -> bool:
    pass


############
# metadata helper class

class TSXDetails(object):
    """
    Parser and interpreter for the TerraSAR-X file package meta-data.
    """

    __slots__ = (
        '_parent_directory', '_main_file', '_georef_file', '_main_root', '_georef_root',
        '_im_format')

    def __init__(self, file_name: str):
        """

        Parameters
        ----------
        file_name : str
            The top-level directory, or the basic package xml file.
        """

        self._parent_directory = None
        self._main_file = None
        self._georef_file = None
        self._main_root = None
        self._georef_root = None
        self._im_format = None
        self._validate_file(file_name)
        self._im_format = self._find_main('./productInfo/imageDataInfo/imageDataFormat').text
        if self._im_format not in ['COSAR', 'GEOTIFF']:
            raise ValueError(
                'The file is determined to be of type TerraSAR-X, but we got '
                'unexpected image format value {}'.format(self.image_format))

    def _validate_file(self, file_name: str) -> None:
        """
        Validate the input file location.

        Parameters
        ----------
        file_name : str

        Returns
        -------
        None
        """
        pass

    @property
    def file_name(self) -> str:
        """
        str: the package directory location
        """
        pass

    @property
    def image_format(self) -> str:
        """
        str: The image file format enum value.
        """
        pass

    def _find_main(self, tag: str) -> ElementTree.Element:
        """
        Pass through to ElementTree.Element.find(tag).

        Parameters
        ----------
        tag : str

        Returns
        -------
        ElementTree.Element
        """
        pass

    def _findall_main(self, tag: str) -> List[ElementTree.Element]:
        """
        Pass through to ElementTree.Element.findall(tag).

        Parameters
        ----------
        tag : str

        Returns
        -------
        List[ElementTree.Element
        """
        pass

    def _find_georef(self, tag: str) -> ElementTree.Element:
        """
        Pass through to ElementTree.Element.find(tag).

        Parameters
        ----------
        tag : str

        Returns
        -------
        ElementTree.Element
        """
        pass

    def _findall_georef(self, tag: str) -> List[ElementTree.Element]:
        """
        Pass through to ElementTree.Element.findall(tag).

        Parameters
        ----------
        tag : str

        Returns
        -------
        List[ElementTree.Element
        """
        pass

    def _get_state_vector_data(self) -> Tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
        """
        Gets the state vector data.

        Returns
        -------
        times: numpy.ndarray
        positions: numpy.ndarray
        velocities: numpy.ndarray
        """
        pass

    @staticmethod
    def _parse_pol_string(str_in: str) -> Tuple[str, str]:
        pass

    def _get_sicd_tx_rcv_pol(self, str_in: str) -> str:
        pass

    def _get_full_pol_list(self) -> Tuple[List[str], List[str], List[str]]:
        """
        Gets the full list of polarization states.

        Returns
        -------
        original_pols : List[str]
        tx_pols : List[str]
        tx_rcv_pols: List[str]
        """
        pass

    def _find_middle_grid_node(self) -> Optional[ElementTree.Element]:
        """
        Find and returns the middle geolocationGrid point, if it exists.
        Otherwise, returns None.

        Returns
        -------
        None|ElementTree.Element
        """
        pass

    def _calculate_dop_polys(self,
                             layer_index: str,
                             azimuth_time_scp: float,
                             range_time_scp: float,
                             collect_start: numpy.datetime64,
                             doppler_rate_reference_node: ElementTree.Element) -> Tuple[numpy.ndarray, numpy.ndarray]:
        """
        Calculate the doppler centroid polynomials. This is apparently extracted
        from the paper "TerraSAR-X Deskew Description" by Michael Stewart dated
        December 11, 2008.

        Parameters
        ----------
        layer_index : str
            The layer index string, required for extracting correct metadata.
        azimuth_time_scp : float
            This is in seconds relative to the collection start.
        range_time_scp : float
            This is in seconds.
        collect_start : numpy.datetime64
            The collection start time.
        doppler_rate_reference_node : ElementTree.Element

        Returns
        -------
        (numpy.ndarray, numpy.ndarray)
        """
        pass

    def _get_basic_sicd_shell(self,
                              center_freq: float,
                              dop_bw: float,
                              ss_zd_s: float) -> SICDType:
        """
        Define the common sicd elements.

        Parameters
        ----------
        center_freq : float
            The center frequency.
        dop_bw : float
            The doppler bandwidth.
        ss_zd_s : float
            The (positive) zero doppler spacing in the time domain.

        Returns
        -------
        SICDType
        """
        pass

    def _populate_basic_image_data(self,
                                   sicd: SICDType,
                                   grid_node: Optional[ElementTree.Element]) -> None:
        """
        Populate the basic ImageData and GeoData. This assumes not ScanSAR mode.
        This modifies the provided sicd in place.

        Parameters
        ----------
        sicd : SICDType
        grid_node : None|ElementTree.Element
            The central geolocationGrid point, if it exists.

        Returns
        -------
        None
        """
        pass

    @staticmethod
    def _populate_initial_radar_collection(
            sicd: SICDType,
            tx_pols: List[str],
            tx_rcv_pols: List[str]) -> None:
        """
        Populate the initial radar collection information. This modifies the
        provided sicd in place.

        Parameters
        ----------
        sicd : SICDType
        tx_pols : List[str]
        tx_rcv_pols : List[str]

        Returns
        -------
        None
        """
        pass

    def _complete_sicd(self,
                       sicd: SICDType,
                       orig_pol: str,
                       layer_index: str,
                       pol_index: int,
                       ss_zd_s: float,
                       side_of_track: str,
                       center_freq: float,
                       arp_times: numpy.ndarray,
                       arp_pos: numpy.ndarray,
                       arp_vel: numpy.ndarray,
                       middle_grid: Optional[ElementTree.Element],
                       doppler_rate_reference_node: ElementTree.Element) -> SICDType:
        """
        Complete the remainder of the sicd information and populate as collection,
        if appropriate. **This assumes that this is not ScanSAR mode.**

        Parameters
        ----------
        sicd : SICDType
        orig_pol : str
            The TSX polarization string.
        layer_index : str
            The layer index entry.
        pol_index : int
            The polarization index (1 based) here.
        ss_zd_s : float
            The zero doppler spacing in the time domain.
        side_of_track : str
            One of ['R', 'S']
        center_freq : float
            The center frequency.
        arp_times : numpy.ndarray
            The array of reference times for the state information.
        arp_pos : numpy.ndarray
        arp_vel : numpy.ndarray
        middle_grid : None|ElementTree.Element
            The central geolocationGrid point, if it exists.
        doppler_rate_reference_node : ElementTree.Element

        Returns
        -------
        SICDType
        """
        pass

    def get_sicd_collection(self) -> Tuple[List[str], List[SICDType]]:
        """
        Gets the sicd metadata collection.

        Returns
        -------
        files: List[str]
        sicds: List[SICDType]
        """
        pass


class COSARDetails(object):
    __slots__ = (
        '_file_name', '_file_size', '_header_offsets', '_data_offsets',
        '_burst_index', '_burst_size', '_data_sizes', '_version')

    def __init__(self, file_name: str):
        """

        Parameters
        ----------
        file_name : str
        """

        self._header_offsets = []
        self._data_offsets = []
        self._burst_index = []
        self._burst_size = []
        self._data_sizes = []
        self._version = None

        if not os.path.isfile(file_name):
            raise SarpyIOError('path {} is not not a file'.format(file_name))
        self._file_name = file_name
        self._file_size = os.path.getsize(file_name)
        self._parse_details()

    @property
    def burst_count(self) -> int:
        """
        int: The discovered burst count
        """
        pass

    @property
    def version(self) -> Optional[int]:
        """
        int: The COSAR version
        """
        pass

    @property
    def pixel_type(self) -> Optional[str]:
        """
        str: The pixel type
        """
        pass

    def _process_burst_header(
            self,
            fi: BinaryIO,
            the_offset: int):
        """

        Parameters
        ----------
        fi : BinaryIO
        the_offset : int

        Returns
        -------
        None
        """
        pass

    def _parse_details(self) -> None:
        pass

    def construct_data_segment(
            self,
            index: int,
            reverse_axes: Optional[Tuple[int, ...]],
            transpose_axes: Optional[Tuple[int, ...]],
            expected_size: Tuple[int, ...]) -> DataSegment:
        """
        Construct a data segment for the given burst index.

        Parameters
        ----------
        index : int
        reverse_axes : None|int|Sequence[int, ...]
        transpose_axes : None|Tuple[int, ...]
        expected_size : Tuple[int, ...]

        Returns
        -------
        DataSegment
        """
        pass


#########
# the reader implementation

class TSXReader(SICDTypeReader):
    """
    The TerraSAR-X SLC reader implementation.

    **Changed in version 1.3.0** for reading changes.
    """

    __slots__ = ('_tsx_details', )

    def __init__(self, tsx_details):
        """

        Parameters
        ----------
        tsx_details : str|TSXDetails
        """

        if isinstance(tsx_details, str):
            tsx_details = TSXDetails(tsx_details)
        if not isinstance(tsx_details, TSXDetails):
            raise TypeError(
                'tsx_details is expected to be the path to the TerraSAR-X package '
                'directory or main xml file, of TSXDetails instance. Got type {}'.format(type(tsx_details)))
        self._tsx_details = tsx_details

        data_segments = []
        image_format = tsx_details.image_format
        the_files, the_sicds = tsx_details.get_sicd_collection()
        for the_file, the_sicd in zip(the_files, the_sicds):
            rows = the_sicd.ImageData.NumRows
            cols = the_sicd.ImageData.NumCols
            reverse_axes = (0, ) if the_sicd.SCPCOA.SideOfTrack == 'L' else None
            transpose_axes = (1, 0, 2)
            if image_format != 'COSAR':
                raise ValueError(
                    'Expected complex data for TerraSAR-X to be in COSAR format. '
                    'Got unhandled format {}'.format(image_format))
            cosar_details = COSARDetails(the_file)
            if cosar_details.burst_count != 1:
                raise ValueError(
                    'Expected one burst in the COSAR file {},\n\t'
                    'but got {} bursts'.format(the_file, cosar_details.burst_count))
            the_sicd.ImageData.PixelType = cosar_details.pixel_type
            data_seg = cosar_details.construct_data_segment(0, reverse_axes, transpose_axes, (cols, rows))
            data_segments.append(data_seg)
        SICDTypeReader.__init__(self, data_segments, the_sicds, close_segments=True)
        self._check_sizes()

    @property
    def file_name(self) -> str:
        pass


########
# base expected functionality for a module with an implemented Reader

def is_a(file_name: str) -> Optional[TSXReader]:
    """
    Tests whether a given file_name corresponds to a TerraSAR-X file SSC package.
    Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str
        the file_name to check

    Returns
    -------
    TSXReader|None
        `TSXReader` instance if TerraSAR-X file file, `None` otherwise
    """
    pass
