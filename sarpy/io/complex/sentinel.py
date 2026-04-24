"""
Functionality for reading Sentinel-1 data into a SICD model.
"""

__classification__ = "UNCLASSIFIED"
__author__ = ("Thomas McCullough", "Daniel Haverporth")


import os
import logging
from datetime import datetime
from xml.etree import ElementTree
from typing import List, Tuple, Union, Optional

import numpy
from numpy.polynomial import polynomial
from scipy.constants import speed_of_light
from scipy.interpolate import griddata

from sarpy.geometry.geocoords import geodetic_to_ecf

from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.sicd_elements.blocks import Poly1DType, Poly2DType
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd_elements.CollectionInfo import CollectionInfoType, RadarModeType
from sarpy.io.complex.sicd_elements.ImageCreation import ImageCreationType
from sarpy.io.complex.sicd_elements.RadarCollection import RadarCollectionType, \
    WaveformParametersType, ChanParametersType
from sarpy.io.complex.sicd_elements.ImageData import ImageDataType
from sarpy.io.complex.sicd_elements.GeoData import GeoDataType, SCPType
from sarpy.io.complex.sicd_elements.Position import PositionType, XYZPolyType
from sarpy.io.complex.sicd_elements.Grid import GridType, DirParamType, WgtTypeType
from sarpy.io.complex.sicd_elements.Timeline import TimelineType, IPPSetType
from sarpy.io.complex.sicd_elements.ImageFormation import ImageFormationType, RcvChanProcType
from sarpy.io.complex.sicd_elements.RMA import RMAType, INCAType
from sarpy.io.complex.sicd_elements.Radiometric import RadiometricType, NoiseLevelType_
from sarpy.io.complex.utils import two_dim_poly_fit, get_im_physical_coords

from sarpy.io.general.base import BaseReader, SarpyIOError
from sarpy.io.general.data_segment import SubsetSegment
from sarpy.io.general.tiff import TiffDetails, NativeTiffDataSegment
from sarpy.io.general.utils import get_seconds, parse_timestring, is_file_like

logger = logging.getLogger(__name__)


##########
# helper functions

def _parse_xml(file_name: str,
               without_ns: bool = False) -> Union[ElementTree.Element, Tuple[dict, ElementTree.Element]]:
    pass


###########
# parser and interpreter for sentinel-1 manifest.safe file

class SentinelDetails(object):
    __slots__ = ('_file_name', '_directory_name', '_root_node', '_ns', '_satellite', '_product_type', '_base_sicd')

    def __init__(self, file_name: str):
        """

        Parameters
        ----------
        file_name : str
        """

        if os.path.isdir(file_name):  # its directory - point it at the manifest.safe file
            t_file_name = os.path.join(file_name, 'manifest.safe')
            if os.path.exists(t_file_name):
                file_name = t_file_name
        if not os.path.exists(file_name) or not os.path.isfile(file_name):
            raise SarpyIOError('path {} does not exist or is not a file'.format(file_name))
        if os.path.split(file_name)[1] != 'manifest.safe':
            raise SarpyIOError('The sentinel file is expected to be named manifest.safe, got path {}'.format(file_name))
        self._file_name = file_name
        absolute_path = os.path.abspath(file_name)
        self._directory_name, _ = os.path.split(absolute_path)

        self._ns, self._root_node = _parse_xml(file_name)
        # note that the manifest.safe apparently does not have a default namespace,
        # so we have to explicitly enter no prefix in the namespace dictionary
        self._ns[''] = ''
        self._satellite = self._find('./metadataSection'
                                     '/metadataObject[@ID="platform"]'
                                     '/metadataWrap'
                                     '/xmlData'
                                     '/safe:platform'
                                     '/safe:familyName').text
        if self._satellite != 'SENTINEL-1':
            raise ValueError('The platform in the manifest.safe file is required '
                             'to be SENTINEL-1, got {}'.format(self._satellite))
        self._product_type = self._find('./metadataSection'
                                        '/metadataObject[@ID="generalProductInformation"]'
                                        '/metadataWrap'
                                        '/xmlData'
                                        '/s1sarl1:standAloneProductInformation'
                                        '/s1sarl1:productType').text
        if self._product_type != 'SLC':
            raise ValueError('The product type in the manifest.safe file is required '
                             'to be "SLC", got {}'.format(self._product_type))
        self._base_sicd = self._get_base_sicd()

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
        str: the satellite
        """
        pass

    @property
    def product_type(self) -> str:
        """
        str: the product type
        """
        pass

    def _find(self, tag: str) -> ElementTree.Element:
        """
        Pass through to ElementTree.Element.find(tag, ns).

        Parameters
        ----------
        tag : str

        Returns
        -------
        ElementTree.Element
        """
        pass

    def _findall(self, tag: str) -> List[ElementTree.Element]:
        """
        Pass through to ElementTree.Element.findall(tag, ns).

        Parameters
        ----------
        tag : str

        Returns
        -------
        List[ElementTree.Element
        """
        pass

    @staticmethod
    def _parse_pol(str_in: str) -> str:
        pass

    def _get_file_sets(self) -> List[dict]:
        """
        Extracts paths for measurement and metadata files from a Sentinel manifest.safe file.
        These files will be grouped according to "measurement data unit" implicit in the
        Sentinel structure.

        Returns
        -------
        List[dict]
        """
        pass

    def _get_base_sicd(self) -> SICDType:
        """
        Gets the base SICD element.

        Returns
        -------
        SICDType
        """
        pass

    def _parse_product_sicd(self, product_file_name: str) -> Union[SICDType, List[SICDType]]:
        """

        Parameters
        ----------
        product_file_name : str

        Returns
        -------
        SICDType|List[SICDType]
        """
        pass

    def _refine_using_calibration(self, cal_file_name: str, sicds: Union[SICDType, List[SICDType]]) -> None:
        """

        Parameters
        ----------
        cal_file_name : str
        sicds : SICDType|List[SICDType]

        Returns
        -------
        None
        """
        pass

    def _refine_using_noise(self, noise_file_name: str, sicds: Union[SICDType, List[SICDType]]) -> None:
        """

        Parameters
        ----------
        noise_file_name : str
        sicds : SICDType|List[SICDType]

        Returns
        -------
        None
        """
        pass

    @staticmethod
    def _derive(sicds: Union[SICDType, List[SICDType]]) -> None:
        pass

    def get_sicd_collection(self) -> List[Tuple[str, Union[SICDType, List[SICDType]]]]:
        """
        Get the data file location(s) and corresponding sicd collection for each file.

        Returns
        -------
        List[Tuple[str, SICDType|List[SICDType]]]
            list of the form `(file, sicds)`. Here `file` is the data filename (tiff).
            `sicds` is either a single `SICDType` (STRIPMAP collect),
            or a list of `SICDType` (TOPSAR with multiple bursts).
        """
        pass


class SentinelReader(SICDTypeReader):
    """
    A Sentinel-1 SLC file package reader implementation.

    **Changed in version 1.3.0** for reading changes.
    """

    __slots__ = ('_sentinel_details', '_parent_segments')

    def __init__(self, sentinel_details: Union[str, SentinelDetails]):
        """

        Parameters
        ----------
        sentinel_details : str|SentinelDetails
        """

        if isinstance(sentinel_details, str):
            sentinel_details = SentinelDetails(sentinel_details)
        if not isinstance(sentinel_details, SentinelDetails):
            raise TypeError('Input argument for SentinelReader must be a file name or SentinelReader object.')

        self._sentinel_details = sentinel_details  # type: SentinelDetails

        reverse_axes = None
        transpose_axes = (1, 0, 2)  # True for all Sentinel-1 data

        parent_segments = []
        segments = []
        sicd_collection = self._sentinel_details.get_sicd_collection()
        sicd_collection_out = []
        for data_file, sicds in sicd_collection:
            tiff_details = TiffDetails(data_file)
            if isinstance(sicds, SICDType):
                segments.append(
                    NativeTiffDataSegment(
                        tiff_details, reverse_axes=reverse_axes, transpose_axes=transpose_axes))
                sicd_collection_out.append(sicds)
            elif len(sicds) == 1:
                segments.append(
                    NativeTiffDataSegment(
                        tiff_details, reverse_axes=reverse_axes, transpose_axes=transpose_axes))
                sicd_collection_out.append(sicds[0])
            else:
                p_segment = NativeTiffDataSegment(
                    tiff_details, reverse_axes=reverse_axes, transpose_axes=transpose_axes)
                parent_segments.append(p_segment)
                begin_col = 0
                for sicd in sicds:
                    end_col = begin_col + sicd.ImageData.NumCols
                    subet_def = (slice(0, tiff_details.tags['ImageWidth'], 1), slice(begin_col, end_col, 1))
                    segments.append(SubsetSegment(p_segment, subet_def, 'formatted', close_parent=False))
                    begin_col = end_col
                    sicd_collection_out.append(sicd)

        self._parent_segments = parent_segments  # type: List[NativeTiffDataSegment]
        SICDTypeReader.__init__(self, segments, sicd_collection_out, close_segments=True)
        self._check_sizes()

    @property
    def sentinel_details(self) -> SentinelDetails:
        """
        SentinelDetails: The sentinel details object.
        """
        pass

    @property
    def file_name(self) -> str:
        pass

    def close(self):
        BaseReader.close(self)
        if hasattr(self, '_parent_segments') and self._parent_segments is not None:
            # noinspection PyBroadException
            try:
                while len(self._parent_segments) > 0:
                    segment = self._parent_segments.pop()
                    segment.close()
            except Exception:
                pass
            self._parent_segments = None


########
# base expected functionality for a module with an implemented Reader

def is_a(file_name: str) -> Optional[SentinelReader]:
    """
    Tests whether a given file_name corresponds to a Sentinel file. Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str
        the file_name to check

    Returns
    -------
    SentinelReader|None
        `SentinelReader` instance if Sentinel-1 file, `None` otherwise
    """
    pass
