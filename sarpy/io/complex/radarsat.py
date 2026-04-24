"""
Functionality for reading Radarsat (RS2 and RCM) data into a SICD model.
"""

__classification__ = "UNCLASSIFIED"
__author__ = ("Thomas McCullough", "Khanh Ho", "Wade Schwartzkopf", "Nathan Bombaci")


import logging
import re
import os
from datetime import datetime
from xml.etree import ElementTree
from typing import Tuple, List, Sequence, Union, Optional

import numpy
from scipy.interpolate import RectBivariateSpline
from numpy.polynomial import polynomial
from scipy.constants import speed_of_light

from sarpy.geometry.geocoords import geodetic_to_ecf

import sarpy._extensions
from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.other_nitf import ComplexNITFReader
from sarpy.io.complex.sicd_elements.blocks import Poly1DType, Poly2DType
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd_elements.CollectionInfo import CollectionInfoType, \
    RadarModeType
from sarpy.io.complex.sicd_elements.ImageCreation import ImageCreationType
from sarpy.io.complex.sicd_elements.ImageData import ImageDataType
from sarpy.io.complex.sicd_elements.GeoData import GeoDataType, SCPType
from sarpy.io.complex.sicd_elements.Position import PositionType, XYZPolyType
from sarpy.io.complex.sicd_elements.Grid import GridType, DirParamType, WgtTypeType
from sarpy.io.complex.sicd_elements.RadarCollection import RadarCollectionType, \
    WaveformParametersType, ChanParametersType, TxStepType
from sarpy.io.complex.sicd_elements.Timeline import TimelineType, IPPSetType
from sarpy.io.complex.sicd_elements.ImageFormation import ImageFormationType, RcvChanProcType
from sarpy.io.complex.sicd_elements.RMA import RMAType, INCAType
from sarpy.io.complex.sicd_elements.SCPCOA import SCPCOAType
from sarpy.io.complex.sicd_elements.Radiometric import RadiometricType, NoiseLevelType_
from sarpy.io.complex.utils import fit_time_coa_polynomial, fit_position_xvalidation

from sarpy.io.general.base import SarpyIOError
from sarpy.io.general.data_segment import DataSegment
from sarpy.io.general.tiff import NativeTiffDataSegment
from sarpy.io.general.utils import get_seconds, parse_timestring, is_file_like

logger = logging.getLogger(__name__)

_unhandled_generation_text = 'Unhandled generation `{}`'


############
# Helper functions

def _parse_xml(file_name: str, without_ns: bool = False) -> ElementTree.Element:
    pass


def _format_class_str(class_str: str) -> str:
    pass


def load_addin():
    """Check for a Radarsat addin module"""
    pass


def _validate_segment_and_sicd(
        the_sicd: SICDType,
        data_segment: DataSegment,
        name: str,
        the_file: str):
    """
    Check that chipper and sicd are compatible.

    Parameters
    ----------
    the_sicd : SICDType
    data_segment : DataSegment
    name : str
    the_file : str

    Returns
    -------
    None
    """
    pass


def _construct_tiff_segment(
        the_sicd: SICDType,
        the_file: str,
        reverse_axes: Union[None, int, Sequence[int]] = None,
        transpose_axes: Union[None, Tuple[int, ...]] = None):
    """

    Parameters
    ----------
    the_sicd : SICDType
    the_file : str
    reverse_axes : None|Tuple[int, ...]
    transpose_axes : None|Tuple[int, ...]

    Returns
    -------
    NativeTiffDataSegment
    """
    pass


def _construct_single_nitf_segment(
        the_sicd: SICDType,
        the_file: str,
        reverse_axes: Optional[Sequence[int]],
        transpose_axes: Optional[Tuple[int, ...]]) -> Tuple[ComplexNITFReader, DataSegment]:
    """

    Parameters
    ----------
    the_sicd : SICDType
    the_file : str
    reverse_axes : None|Sequence[int]
    transpose_axes : None|Tuple[int, ...]

    Returns
    -------
    reader: ComplexNITFReader
    data_segment: DataSegment
    """
    pass


def _construct_multiple_nitf_segment(
        the_sicds: List[SICDType],
        the_file: str,
        reverse_axes: Optional[Sequence[int]],
        transpose_axes: Optional[Tuple[int, ...]]) -> Tuple[ComplexNITFReader, Tuple[DataSegment, ...]]:
    """

    Parameters
    ----------
    the_sicds : List[SICDType]
    the_file : str
    reverse_axes : None|Sequence[int]
    transpose_axes : None|Tuple[int, ...]

    Returns
    -------
    reader: ComplexNITFReader
    data_segment: Tuple[DataSegment, ...]
    """
    pass


##############
# Class for meta-data interpretation

class RadarSatDetails(object):
    """
    Class for interpreting RadarSat-2 and RadarSat Constellation Mission (RCM)
    metadata files, and creating the corresponding sicd structure(s).
    """

    __slots__ = (
        '_file_name', '_directory_name', '_satellite', '_root_node', '_beams', '_bursts',
        '_num_lines_processed', '_polarizations',
        '_x_spline', '_y_spline', '_z_spline',
        '_state_time', '_state_position', '_state_velocity')

    def __init__(self, file_name: str):
        """

        Parameters
        ----------
        file_name : str
        """

        self._beams = None
        self._bursts = None
        self._num_lines_processed = None
        self._polarizations = None
        self._x_spline = None
        self._y_spline = None
        self._z_spline = None
        self._state_time = None
        self._state_position = None
        self._state_velocity = None

        if os.path.isdir(file_name):  # it is the directory - point it at the product.xml file
            for t_file_name in [
                    os.path.join(file_name, 'product.xml'),
                    os.path.join(file_name, 'metadata', 'product.xml')]:
                if os.path.exists(t_file_name):
                    file_name = t_file_name
                    break
        if not os.path.isfile(file_name):
            raise SarpyIOError('path {} does not exist or is not a file'.format(file_name))
        if os.path.split(file_name)[1] != 'product.xml':
            raise SarpyIOError(
                'The radarsat or rcm file is expected to be named product.xml,\n\t'
                'got path {}'.format(file_name))

        self._file_name = file_name
        root_node = _parse_xml(file_name, without_ns=True)

        sat_node = root_node.find('./sourceAttributes/satellite')
        satellite = 'None' if sat_node is None else sat_node.text.upper()
        product_node = root_node.find(
            './imageGenerationParameters/generalProcessingInformation/productType')
        product_type = 'None' if product_node is None else product_node.text.upper()
        if not ((satellite == 'RADARSAT-2' or satellite.startswith('RCM')) and product_type == 'SLC'):
            raise SarpyIOError(
                'File {} does not appear to be an SLC product\n\t'
                'for a RADARSAT-2 or RCM mission.'.format(file_name))

        self._root_node = root_node
        self._satellite = satellite
        absolute_path = os.path.abspath(self._file_name)
        parent_dir, _ = os.path.split(absolute_path)
        if self.generation == 'RS2':
            self._directory_name = parent_dir
        else:
            self._directory_name, _ = os.path.split(parent_dir)

        self._build_location_spline()
        self._parse_state_vectors()
        self._extract_beams_and_bursts()

    @property
    def file_name(self) -> str:
        """
        str: the file name
        """
        pass

    @property
    def directory_name(self) -> str:
        """
        str: the package directory name
        """
        pass

    @property
    def satellite(self) -> str:
        """
        str: the satellite name
        """
        pass

    @property
    def generation(self) -> str:
        """
        str: RS2 or RCM
        """
        pass

    @property
    def pass_direction(self) -> str:
        """
        str: The pass direction
        """
        pass

    def get_symmetry(self) -> Tuple[Optional[Tuple[int, ...]], Optional[Tuple[int, ...]]]:
        """
        Get the symmetry transform information.

        Returns
        -------
        reverse_axes : None|Tuple[int, ...]
        transpose_axes : None|Tuple[int, ...]
        """
        pass

    def _find(self, tag: str) -> ElementTree.Element:
        pass

    def _findall(self, tag: str) -> List[ElementTree.Element]:
        pass

    def _get_tiepoint_nodes(self) -> List[ElementTree.Element]:
        """
        Fetch the tie point nodes.

        Returns
        -------
        List[ElementTree.Element]
        """
        pass

    def _build_location_spline(self) -> None:
        """
        Populates the three (line, sample) -> location coordinate splines. This
        should be done once for all images.

        Returns
        -------
        None
        """
        pass

    def _get_image_location(self, line: Union[int, float], sample: Union[int, float]) -> numpy.ndarray:
        """
        Fetch the image location estimate based on the previously constructed splines.

        Parameters
        ----------
        line : int|float
            The RadarSat line number.
        sample : int|float
            The RadarSat sample number.

        Returns
        -------
        numpy.ndarray
        """
        pass

    def _parse_state_vectors(self) -> None:
        """
        Parses the state vectors.

        Returns
        -------
        None
        """
        pass

    def _extract_beams_and_bursts(self) -> None:
        """
        Extract the beam and burst and polarization information.

        Returns
        -------
        None
        """
        pass

    def _get_sicd_radar_mode(self) -> RadarModeType:
        """
        Gets the RadarMode information.

        Returns
        -------
        RadarModeType
        """
        pass

    def _get_sicd_collection_info(self, start_time: numpy.datetime64) -> Tuple[dict, CollectionInfoType]:
        """
        Gets the sicd CollectionInfo information.

        Parameters
        ----------
        start_time : numpy.datetime64

        Returns
        -------
        nitf : dict
            The NITF element dictionary
        collection_info : CollectionInfoType
        """
        pass

    def _get_sicd_image_creation(self) -> ImageCreationType:
        """
        Gets the ImageCreation metadata.

        Returns
        -------
        ImageCreationType
        """
        pass

    def _get_sicd_position(self, start_time: numpy.datetime64) -> PositionType:
        """
        Gets the SICD Position definition, based on the given start time.

        Parameters
        ----------
        start_time : numpy.datetime64

        Returns
        -------
        PositionType
        """
        pass

    @staticmethod
    def _parse_polarization(str_in: str) -> Tuple[str, str]:
        """
        Parses the Radarsat polarization string into it's two SICD components.

        Parameters
        ----------
        str_in : str

        Returns
        -------
        (str, str)
        """
        pass

    def _get_sicd_polarizations(self) -> Tuple[List[str], List[str]]:
        pass

    def _get_side_of_track(self) -> str:
        """
        Gets the sicd side of track.

        Returns
        -------
        str
        """
        pass

    def _get_regular_sicd(self) -> Tuple[List[SICDType], List[str]]:
        """
        Gets the SICD collection. This will return one SICD per polarimetric
        collection. It will also return the data file(s). This is only applicable
        for non-ScanSAR collects.

        Returns
        -------
        sicds: List[SICDType]
        files: List[str]
        """
        pass

    def _get_scansar_sicd(self, beam: str, burst: str) -> Tuple[List[SICDType], List[str]]:
        """
        Gets the SICD collection for the given burst. This is only applicable
        to ScanSAR collects. This will return one SICD per polarimetric collection.
        It will also return the data file(s) for the given beam/burst.

        Parameters
        ----------
        beam : str
        burst : str

        Returns
        -------
        sicds: List[SICDType]
        files: List[str]
        """
        pass

    def get_sicd_collection(self) -> Tuple[List[List[SICDType]], List[List[str]]]:
        """
        Gets the collection of sicd objects.

        Returns
        -------
        sicds: List[List[SICDType]]
        files: List[List[str]]
        """
        pass


##############
# reader implementation - really just borrows from tiff or NITF reader

class RadarSatReader(SICDTypeReader):
    """
    A RadarSat-2 and RadarSat Constellation Mission (RCM) SLC file package
    reader implementation.

    **Changed in version 1.3.0** for reading changes.
    """

    __slots__ = ('_radar_sat_details', '_other_reader')

    def __init__(self, radar_sat_details):
        """

        Parameters
        ----------
        radar_sat_details : str|RadarSatDetails
            file name or RadarSatDetails object
        """

        self._other_reader = None
        if isinstance(radar_sat_details, str):
            radar_sat_details = RadarSatDetails(radar_sat_details)
        if not isinstance(radar_sat_details, RadarSatDetails):
            raise TypeError('The input argument for RadarSatReader must be a '
                            'filename or RadarSatDetails object')
        self._radar_sat_details = radar_sat_details
        # determine symmetry
        reverse_axes, transpose_axes = self._radar_sat_details.get_symmetry()
        # get the sicd collection and data file names
        the_sicds, the_files = self.radarsat_details.get_sicd_collection()
        use_sicds = []
        the_segments = []
        for sicd_entry, file_entry in zip(the_sicds, the_files):
            the_segments.extend(self._construct_segments(sicd_entry, file_entry, reverse_axes, transpose_axes))
            use_sicds.extend(sicd_entry)

        SICDTypeReader.__init__(self, the_segments, use_sicds, close_segments=True)
        self._check_sizes()

    def _construct_segments(
            self,
            sicds: List[SICDType],
            data_files: List[str],
            reverse_axes: Optional[Tuple[int, ...]],
            transpose_axes: Optional[Tuple[int, ...]]) -> List[DataSegment]:
        """
        Construct the data segments.

        Parameters
        ----------
        sicds : List[SICDType]
        data_files : List[str]
        reverse_axes : None|Tuple[int, ...]
        transpose_axes : None|Tuple[int, ...]

        Returns
        -------
        List[BaseChipper]
        """
        pass

    @property
    def radarsat_details(self) -> RadarSatDetails:
        """
        RadarSarDetails: The RadarSat/RCM details object.
        """
        pass

    @property
    def file_name(self) -> str:
        pass

    def close(self) -> None:
        SICDTypeReader.close(self)
        self._other_reader = None


########
# base expected functionality for a module with an implemented Reader

def is_a(file_name: str) -> Optional[RadarSatReader]:
    """
    Tests whether a given file_name corresponds to a RadarSat file. Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str
        the file_name to check

    Returns
    -------
    RadarSatReader|None
        `RadarSatReader` instance if RadarSat file, `None` otherwise
    """
    pass
