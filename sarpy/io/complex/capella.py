"""
Functionality for reading Capella SAR data into a SICD model.

**This functionality is really onl partially complete**
"""

__classification__ = "UNCLASSIFIED"
__author__ = ("Thomas McCullough", "Wade Schwartzkopf")


import logging
import json
from typing import Dict, Any, Tuple, Union, Optional
from collections import OrderedDict

from scipy.constants import speed_of_light
import numpy
from numpy.polynomial import polynomial

from sarpy.io.general.base import SarpyIOError
from sarpy.io.general.tiff import TiffDetails, NativeTiffDataSegment
from sarpy.io.general.utils import parse_timestring, get_seconds, is_file_like
from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.utils import fit_position_xvalidation
from sarpy.io.complex.sicd_elements.blocks import XYZPolyType, Poly2DType
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd_elements.CollectionInfo import CollectionInfoType, RadarModeType
from sarpy.io.complex.sicd_elements.ImageCreation import ImageCreationType
from sarpy.io.complex.sicd_elements.ImageData import ImageDataType
from sarpy.io.complex.sicd_elements.GeoData import GeoDataType, SCPType
from sarpy.io.complex.sicd_elements.Position import PositionType
from sarpy.io.complex.sicd_elements.Grid import GridType, DirParamType, WgtTypeType
from sarpy.io.complex.sicd_elements.RadarCollection import RadarCollectionType, \
    WaveformParametersType, ChanParametersType
from sarpy.io.complex.sicd_elements.Timeline import TimelineType, IPPSetType
from sarpy.io.complex.sicd_elements.ImageFormation import ImageFormationType, \
    RcvChanProcType, ProcessingType
from sarpy.io.complex.sicd_elements.RMA import RMAType, INCAType
from sarpy.io.complex.sicd_elements.Radiometric import RadiometricType, NoiseLevelType_

logger = logging.getLogger(__name__)


#########
# helper functions

def avci_nacaroglu_window(M, alpha=1.25):
    """
    Avci-Nacaroglu Exponential window. See Doerry '17 paper window 4.40 p 154
    Parameters
    ----------
    M : int
    alpha : float
    """
    pass


###########
# parser and interpreter for tiff attributes

class CapellaDetails(object):
    """
    Parses and converts the Cosmo Skymed metadata
    """

    __slots__ = ('_tiff_details', '_img_desc_tags')

    def __init__(self, file_name: str):
        """

        Parameters
        ----------
        file_name : str
        """

        # verify that the file is a tiff file
        self._tiff_details = TiffDetails(file_name)
        # verify that ImageDescription tiff tag exists
        if 'ImageDescription' not in self._tiff_details.tags:
            raise SarpyIOError('No "ImageDescription" tag in the tiff.')

        img_format = self._tiff_details.tags['ImageDescription']
        # verify that ImageDescription has a reasonable format
        try:
            self._img_desc_tags = json.loads(img_format)  # type: Dict[str, Any]
        except Exception as e:
            msg = 'Failed deserializing the ImageDescription tag as json with error {}'.format(e)
            logger.info(msg)
            raise SarpyIOError(msg)

        # verify the file is not compressed
        self._tiff_details.check_compression()
        # verify the file is not tiled
        self._tiff_details.check_tiled()

    @property
    def file_name(self) -> str:
        """
        str: the file name
        """
        pass

    @property
    def tiff_details(self) -> TiffDetails:
        """
        TiffDetails: The tiff details object.
        """
        pass

    def get_symmetry(self) -> (Union[None, Tuple[int, ...]], Tuple[int, ...]):
        """
        Gets the symmetry operations definition.

        Returns
        -------
        reverse_axes : None|Tuple[int, ...]
        transpose_axes : Tuple[int, ...]
        """
        pass

    def get_sicd(self) -> SICDType:
        """
        Get the SICD metadata for the image.

        Returns
        -------
        SICDType
        """
        pass


class CapellaReader(SICDTypeReader):
    """
    The Capella SLC reader implementation. **This is only partially complete.**

    **Changed in version 1.3.0** for reading changes.
    """

    __slots__ = ('_capella_details', )

    def __init__(self, capella_details):
        """

        Parameters
        ----------
        capella_details : str|CapellaDetails
        """

        if isinstance(capella_details, str):
            capella_details = CapellaDetails(capella_details)

        if not isinstance(capella_details, CapellaDetails):
            raise TypeError('The input argument for capella_details must be a '
                            'filename or CapellaDetails object')
        self._capella_details = capella_details
        sicd = self.capella_details.get_sicd()
        reverse_axes, transpose_axes = self.capella_details.get_symmetry()
        data_segment = NativeTiffDataSegment(
            self.capella_details.tiff_details, reverse_axes=reverse_axes, transpose_axes=transpose_axes)

        SICDTypeReader.__init__(self, data_segment, sicd, close_segments=True)
        self._check_sizes()

    @property
    def capella_details(self) -> CapellaDetails:
        """
        CapellaDetails: The capella details object.
        """
        pass

    @property
    def file_name(self) -> str:
        pass


########
# base expected functionality for a module with an implemented Reader

def is_a(file_name: str) -> Optional[CapellaReader]:
    """
    Tests whether a given file_name corresponds to a Capella SAR file.
    Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str
        the file_name to check

    Returns
    -------
    CapellaReader|None
        `CapellaReader` instance if Capella file, `None` otherwise
    """
    pass
