"""
Module for reading and writing SIDD files
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import logging
from functools import reduce
import re
from typing import List, Tuple, Sequence, Union, BinaryIO, Optional

import numpy

from sarpy.io.xml.base import parse_xml_from_string

from sarpy.io.general.utils import is_file_like
from sarpy.io.general.base import SarpyIOError
from sarpy.io.general.nitf import NITFDetails, NITFReader, NITFWriter, \
    interpolate_corner_points_string, ImageSubheaderManager, \
    GraphicsSubheaderManager, TextSubheaderManager, DESSubheaderManager, \
    RESSubheaderManager, NITFWritingDetails, default_image_segmentation
from sarpy.io.general.nitf_elements.nitf_head import NITFHeader
from sarpy.io.general.nitf_elements.des import DataExtensionHeader, XMLDESSubheader
from sarpy.io.general.nitf_elements.security import NITFSecurityTags
from sarpy.io.general.nitf_elements.image import ImageSegmentHeader, \
    ImageSegmentHeader0, ImageBands, ImageBand

from sarpy.io.product.base import SIDDTypeReader
from sarpy.io.product.sidd3_elements.SIDD import SIDDType as SIDDType3
from sarpy.io.product.sidd2_elements.SIDD import SIDDType as SIDDType2
from sarpy.io.product.sidd1_elements.SIDD import SIDDType as SIDDType1
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd import extract_clas as extract_clas_sicd, \
    create_security_tags_from_sicd


logger = logging.getLogger(__name__)

########
# module variables
_class_priority = {'U': 0, 'R': 1, 'C': 2, 'S': 3, 'T': 4}
SIDD_TYPES = (SIDDType1, SIDDType2, SIDDType3)


#########
# Helper object for initially parses NITF header - specifically looking for SICD elements


class SIDDDetails(NITFDetails):
    """
    SIDD are stored in NITF 2.1 files.
    """

    __slots__ = (
        '_is_sidd', '_sidd_meta', '_sicd_meta')

    def __init__(self, file_object: Union[str, BinaryIO]):
        """

        Parameters
        ----------
        file_object : str|BinaryIO
            file name or file like object for a NITF 2.1 or 2.0 containing a SIDD
        """

        self._img_headers = None
        self._is_sidd = False
        self._sidd_meta = None
        self._sicd_meta = None
        NITFDetails.__init__(self, file_object)

        if self._nitf_header.ImageSegments.subhead_sizes.size == 0:
            raise SarpyIOError('There are no image segments defined.')
        if self._nitf_header.GraphicsSegments.item_sizes.size > 0:
            raise SarpyIOError('A SIDD file does not allow for graphics segments.')
        if self._nitf_header.DataExtensions.subhead_sizes.size == 0:
            raise SarpyIOError(
                'A SIDD file requires at least one data extension, containing the '
                'SIDD xml structure.')

        # define the sidd and sicd metadata
        self._find_sidd()
        if not self.is_sidd:
            raise SarpyIOError('Could not find SIDD xml data extensions.')

    @property
    def is_sidd(self) -> bool:
        """
        bool: whether file name corresponds to a SIDD file, or not.
        """
        pass

    @property
    def sidd_meta(self) -> Union[SIDDType3, SIDDType2, SIDDType1, List[SIDDType3], List[SIDDType2], List[SIDDType1]]:
        """
        None|SIDDType3|SIDDType2|SIDDType1|List[SIDDType3]|List[SIDDType2]|List[SIDDType1]: the sidd meta-data structure(s).
        """
        pass

    @property
    def sicd_meta(self) -> Optional[List[SICDType]]:
        """
        None|List[SICDType]: the sicd meta-data structure(s).
        """
        pass

    def _find_sidd(self) -> None:
        pass


#######
#  The actual reading implementation

def _check_iid_format(iid1: str) -> bool:
    pass


class SIDDReader(NITFReader, SIDDTypeReader):
    """
    A reader object for a SIDD file (NITF container with SIDD contents)
    """

    def __init__(self, nitf_details):
        """

        Parameters
        ----------
        nitf_details : str|BinaryIO|SIDDDetails
            filename, file-like object, or SIDDDetails object
        """

        if isinstance(nitf_details, str) or is_file_like(nitf_details):
            nitf_details = SIDDDetails(nitf_details)
        if not isinstance(nitf_details, SIDDDetails):
            raise TypeError('The input argument for SIDDReader must be a filename or '
                            'SIDDDetails object.')

        if not nitf_details.is_sidd:
            raise ValueError(
                'The input file passed in appears to be a NITF 2.1 file that does not contain '
                'valid sidd metadata.')

        self._nitf_details = nitf_details
        SIDDTypeReader.__init__(self, None, self.nitf_details.sidd_meta, self.nitf_details.sicd_meta)
        NITFReader.__init__(self, nitf_details, reader_type="SIDD")
        self._check_sizes()

    @property
    def nitf_details(self) -> SIDDDetails:
        """
        SIDDDetails: The SIDD NITF details object.
        """
        pass

    def _check_image_segment_for_compliance(
            self,
            index: int,
            img_header: Union[ImageSegmentHeader, ImageSegmentHeader0]) -> bool:

        pass

    def find_image_segment_collections(self) -> Tuple[Tuple[int, ...]]:
        pass


########
# base expected functionality for a module with an implemented Reader

def is_a(file_name: Union[str, BinaryIO]) -> Optional[SIDDReader]:
    """
    Tests whether a given file_name corresponds to a SIDD file.
    Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str
        the file_name to check

    Returns
    -------
    SIDDReader|None
        `SIDDReader` instance if SIDD file, `None` otherwise
    """
    pass


#########
# The writer implementation

def validate_sidd_for_writing(
        sidd_meta: Union[SIDDType3, SIDDType2, SIDDType1, List[SIDDType3], List[SIDDType2],
                   List[SIDDType1]]) -> Union[Tuple[SIDDType3, ...], Tuple[SIDDType2, ...], Tuple[SIDDType1, ...]]:
    """
    Helper method which ensures the provided SIDD structure is appropriate.

    Parameters
    ----------
    sidd_meta : SIDDType3|List[SIDDType3]|SIDDType2|List[SIDDType2]|SIDDType1|List[SIDDType1]

    Returns
    -------
    Tuple[SIDDType3, ...]|Tuple[SIDDType2, ...]|Tuple[SIDDType1, ...]
    """
    pass


def validate_sicd_for_writing(sicd_meta: Union[SICDType, Sequence[SICDType]]) -> Optional[Tuple[SICDType, ...]]:
    """
    Helper method which ensures the provided SICD structure is appropriate.

    Parameters
    ----------
    sicd_meta : SICDType|List[SICDType]

    Returns
    -------
    None|Tuple[SICDType]
    """

    if sicd_meta is None:
        return None
    if isinstance(sicd_meta, SICDType):
        # noinspection PyRedundantParentheses
        return (sicd_meta, )
    elif isinstance(sicd_meta, (tuple, list)):
        out = []
        for entry in sicd_meta:
            if not isinstance(entry, SICDType):
                raise TypeError('All entries are required to be an instance of SICDType, '
                                'got type {}'.format(type(entry)))
            out.append(entry)
        return tuple(out)
    else:
        raise TypeError('sicd_meta is required to be an instance of SICDType or a list/tuple '
                        'of such instances, got {}'.format(type(sicd_meta)))


def extract_clas(the_sidd: Union[SIDDType3, SIDDType2, SIDDType1]) -> str:
    """
    Extract the classification string from a SIDD as appropriate for NITF Security
    tags CLAS attribute.

    Parameters
    ----------
    the_sidd : SIDDType3|SIDDType2|SIDDType1

    Returns
    -------
    str
    """

    class_str = the_sidd.ProductCreation.Classification.classification

    if class_str is None or class_str == '':
        return 'U'
    else:
        return class_str[:1]


def extract_clsy(the_sidd: Union[SIDDType3, SIDDType2, SIDDType1]) -> str:
    """
    Extract the ownerProducer string from a SIDD as appropriate for NITF Security
    tags CLSY attribute.

    Parameters
    ----------
    the_sidd : SIDDType3|SIDDType2|SIDDType1

    Returns
    -------
    str
    """

    owner = the_sidd.ProductCreation.Classification.ownerProducer.upper()
    if owner is None:
        return ''
    elif owner in ('USA', 'CAN', 'AUS', 'NZL'):
        return owner[:2]
    elif owner == 'GBR':
        return 'UK'
    elif owner == 'NATO':
        return 'XN'
    else:
        logger.warning(
            'Got owner {}, and the CLSY will be truncated\n\t'
            'to two characters.'.format(owner))
        return owner[:2]


def create_security_tags_from_sidd(sidd_meta: Union[SIDDType3, SIDDType2, SIDDType1]) -> NITFSecurityTags:
    pass


class SIDDWritingDetails(NITFWritingDetails):
    __slots__ = (
        '_sidd_meta', '_sicd_meta', '_security_tags',
        '_sidd_security_tags', '_sicd_security_tags',
        '_row_limit')

    def __init__(
            self,
            sidd_meta: Union[SIDDType3, SIDDType2, SIDDType1, Sequence[SIDDType3], Sequence[SIDDType2], Sequence[SIDDType1]],
            sicd_meta: Optional[Union[SICDType, Sequence[SICDType]]],
            row_limit: Optional[int] = None,
            additional_des: Optional[Sequence[DESSubheaderManager]] = None,
            graphics_managers: Optional[Tuple[GraphicsSubheaderManager, ...]] = None,
            text_managers: Optional[Tuple[TextSubheaderManager, ...]] = None,
            res_managers: Optional[Tuple[RESSubheaderManager, ...]] = None):
        """

        Parameters
        ----------
        sidd_meta : SIDDType3|List[SIDDType3]|SIDDType2|List[SIDDType2]|SIDDType1|List[SIDDType1]
        sicd_meta : SICDType
        row_limit : None|int
            Desired row limit for the sicd image segments. Non-positive values
            or values > 99999 will be ignored.
        additional_des : None|Sequence[DESSubheaderManager]
        graphics_managers: Optional[Tuple[GraphicsSubheaderManager, ...]]
        text_managers: Optional[Tuple[TextSubheaderManager, ...]]
        res_managers: Optional[Tuple[RESSubheaderManager, ...]]
        """

        self._sidd_meta = None
        self._sidd_security_tags = None
        self._set_sidd_meta(sidd_meta)

        self._sicd_meta = None
        self._sicd_security_tags = None
        self._set_sicd_meta(sicd_meta)

        self._security_tags = None
        self._create_security_tags()

        self._row_limit = None
        self._set_row_limit(row_limit)

        header = self._create_header()
        image_managers, image_segment_collection, image_segment_coordinates = self._create_image_segments()
        des_managers = self._create_des_segments(additional_des)
        NITFWritingDetails.__init__(
            self,
            header,
            image_managers=image_managers,
            image_segment_collections=image_segment_collection,
            image_segment_coordinates=image_segment_coordinates,
            graphics_managers=graphics_managers,
            text_managers=text_managers,
            des_managers=des_managers,
            res_managers=res_managers)

    @property
    def sidd_meta(self) -> Union[Tuple[SIDDType3, ...], Tuple[SIDDType2, ...], Tuple[SIDDType1, ...]]:
        """
        Tuple[SIDDType3, ...]: The sidd metadata.
        """
        pass

    def _set_sidd_meta(self, value) -> None:
        pass

    @property
    def sicd_meta(self) -> Tuple[SICDType, ...]:
        """
        Tuple[SICDType, ...]: The sicd metadata
        """
        pass

    def _set_sicd_meta(self, value) -> None:
        pass

    @property
    def row_limit(self) -> Tuple[int, ...]:
        pass

    def _set_row_limit(self, value) -> None:
        pass

    def _create_security_tags(self):
        pass

    def _get_iid2(self, index: int) -> str:
        """
        Get the IID2 for the sidd at `index`.

        Parameters
        ----------
        index : int

        Returns
        -------
        str
        """
        pass

    def _get_ftitle(self, index: int = 0) -> str:
        pass

    # File Creation DateTime
    def _get_fdt(self, index: int) -> Optional[str]:
        pass

    # Image Acquisition (Collection) Datetime
    def _get_collection_datetime(self, index: int) -> Optional[str]:   
        pass

    def _get_ostaid(self, index: int = 0) -> str:
        pass

    def _get_isorce(self, index: int = 0) -> str:
        pass

    def _get_icp(self, sidd_index: int) -> Optional[numpy.ndarray]:
        """
        Get the Image corner point array, if possible.

        Parameters
        ----------
        sidd_index : int

        Returns
        -------
        None|numpy.ndarray
        """
        pass

    def _create_header(self) -> NITFHeader:
        """
        Create the main NITF header.

        Returns
        -------
        NITFHeader
        """
        pass

    def _create_image_segment_for_sidd(
            self,
            sidd_index: int,
            starting_index: int) -> Tuple[List[ImageSubheaderManager], Tuple[int, ...], Tuple[Tuple[int, ...], ...]]:

        pass

    def _create_image_segments(self) -> Tuple[Tuple[ImageSubheaderManager, ...], Tuple[Tuple[int, ...], ...], Tuple[Tuple[Tuple[int, ...], ...]]]:
        pass

    def _create_des_segment_for_sidd(self, sidd_index: int) -> DESSubheaderManager:
        pass

    def _create_sidd_des_segments(self) -> List[DESSubheaderManager]:
        pass

    def _create_des_segment_for_sicd(self, sicd_index: int) -> DESSubheaderManager:
        pass

    def _create_sicd_des_segments(self) -> List[DESSubheaderManager]:
        pass

    def _create_des_segments(
            self,
            additional_des: Optional[Sequence[DESSubheaderManager]]) -> Tuple[DESSubheaderManager, ...]:

        pass


class SIDDWriter(NITFWriter):
    """
    Writer class for a SIDD file - a NITF file following certain rules.

    **Changed in version 1.3.0** to reflect NITFWriter changes.
    """

    def __init__(
            self,
            file_object: Union[str, BinaryIO],
            sidd_meta: Optional[Union[SIDDType3, SIDDType2, SIDDType1, Sequence[SIDDType3],
                                Sequence[SIDDType2], Sequence[SIDDType1]]] = None,
            sicd_meta: Optional[Union[SICDType, Sequence[SICDType]]] = None,
            sidd_writing_details: Optional[SIDDWritingDetails] = None,
            check_existence: bool = True,
            in_memory: bool = None):
        """

        Parameters
        ----------
        file_object : str|BinaryIO
        sidd_meta : None|SIDDType3|SIDDType2|SIDDType1|Sequence[SIDDType3]|Sequence[SIDDType2]|Sequence[SIDDType1]
        sicd_meta : None|SICDType|Sequence[SICDType]
        sidd_writing_details : None|SIDDWritingDetails
        check_existence : bool
            Should we check if the given file already exists?
        in_memory : bool
            If True force in-memory writing, if False force file writing.
        """

        if sidd_meta is None and sidd_writing_details is None:
            raise ValueError('One of sidd_meta or sidd_writing_details must be provided.')
        if sidd_writing_details is None:
            sidd_writing_details = SIDDWritingDetails(sidd_meta, sicd_meta=sicd_meta)
        NITFWriter.__init__(
            self, file_object, sidd_writing_details, check_existence=check_existence, in_memory=in_memory)

    @property
    def nitf_writing_details(self) -> SIDDWritingDetails:
        """
        SIDDWritingDetails: The SIDD/NITF subheader details.
        """
        pass

    @nitf_writing_details.setter
    def nitf_writing_details(self, value):
        pass
