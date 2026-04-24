"""
Module for reading and writing SICD files
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import re
import logging
import datetime
from typing import BinaryIO, Union, Optional, Dict, Tuple, Sequence

import numpy

from sarpy.__about__ import __title__, __version__
from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd_elements.ImageCreation import ImageCreationType

from sarpy.io.general.base import SarpyIOError
from sarpy.io.general.format_function import FormatFunction, ComplexFormatFunction
from sarpy.io.general.nitf import NITFDetails, NITFReader, NITFWriter, \
    interpolate_corner_points_string, default_image_segmentation, \
    ImageSubheaderManager, TextSubheaderManager, DESSubheaderManager, \
    RESSubheaderManager, NITFWritingDetails
from sarpy.io.general.nitf_elements.nitf_head import NITFHeader
from sarpy.io.general.nitf_elements.des import DataExtensionHeader, XMLDESSubheader
from sarpy.io.general.nitf_elements.security import NITFSecurityTags
from sarpy.io.general.nitf_elements.image import ImageSegmentHeader, \
    ImageSegmentHeader0, ImageBands, ImageBand
from sarpy.io.general.utils import is_file_like

from sarpy.io.xml.base import parse_xml_from_string

logger = logging.getLogger(__name__)


#########
# Helper object for initially parses NITF header


class AmpLookupFunction(ComplexFormatFunction):
    __slots__ = ('_magnitude_lookup_table', )
    _allowed_ordering = ('MP', )

    def __init__(
            self,
            raw_dtype: Union[str, numpy.dtype],
            magnitude_lookup_table: numpy.ndarray,
            raw_shape: Optional[Tuple[int, ...]] = None,
            formatted_shape: Optional[Tuple[int, ...]] = None,
            reverse_axes: Optional[Tuple[int, ...]] = None,
            transpose_axes: Optional[Tuple[int, ...]] = None,
            band_dimension: int = -1):
        """

        Parameters
        ----------
        raw_dtype : str|numpy.dtype
            The raw datatype. Must be `uint8` up to endianness.
        magnitude_lookup_table : numpy.ndarray
        raw_shape : None|Tuple[int, ...]
        formatted_shape : None|Tuple[int, ...]
        reverse_axes : None|Tuple[int, ...]
        transpose_axes : None|Tuple[int, ...]
        band_dimension : int
            Which band is the complex dimension, **after** the transpose operation.
        """

        ComplexFormatFunction.__init__(
            self, raw_dtype, 'MP', raw_shape=raw_shape, formatted_shape=formatted_shape,
            reverse_axes=reverse_axes, transpose_axes=transpose_axes, band_dimension=band_dimension)
        self._magnitude_lookup_table = None
        self.set_magnitude_lookup(magnitude_lookup_table)

    @property
    def magnitude_lookup_table(self) -> numpy.ndarray:
        """
        The magnitude lookup table, for SICD usage with `AMP8I_PHS8I` pixel type.

        Returns
        -------
        numpy.ndarray
        """
        pass

    def set_magnitude_lookup(self, lookup_table: numpy.ndarray) -> None:
        pass

    def _forward_magnitude_theta(
            self,
            data: numpy.ndarray,
            out: numpy.ndarray,
            magnitude: numpy.ndarray,
            theta: numpy.ndarray,
            subscript: Tuple[slice, ...]) -> None:
        magnitude = self.magnitude_lookup_table[magnitude]
        ComplexFormatFunction._forward_magnitude_theta(
            self, data, out, magnitude, theta, subscript)

    def _reverse_magnitude_theta(
            self,
            data: numpy.ndarray,
            out: numpy.ndarray,
            magnitude: numpy.ndarray,
            theta: numpy.ndarray,
            slice0: Tuple[slice, ...],
            slice1: Tuple[slice, ...]) -> None:
        magnitude = numpy.digitize(
            numpy.round(magnitude.ravel()), self.magnitude_lookup_table, right=False).reshape(data.shape)

        ComplexFormatFunction._reverse_magnitude_theta(self, data, out, magnitude, theta, slice0, slice1)


class SICDDetails(NITFDetails):
    """
    SICD are stored in NITF 2.1 files.
    """
    __slots__ = (
        '_des_index', '_des_header', '_is_sicd', '_sicd_meta')

    def __init__(self, file_object: Union[str, BinaryIO]):
        """

        Parameters
        ----------
        file_object : str|BinaryIO
            file name or file like object for a NITF 2.1 or 2.0 containing a SICD.
        """

        self._des_index = None
        self._des_header = None
        self._img_headers = None
        self._is_sicd = False
        self._sicd_meta = None
        NITFDetails.__init__(self, file_object)

        if self._nitf_header.ImageSegments.subhead_sizes.size == 0:
            raise SarpyIOError('There are no image segments defined.')
        if self._nitf_header.GraphicsSegments.item_sizes.size > 0:
            raise SarpyIOError('A SICD file does not allow for graphics segments.')
        if self._nitf_header.DataExtensions.subhead_sizes.size == 0:
            raise SarpyIOError(
                'A SICD file requires at least one data extension, containing the '
                'SICD xml structure.')

        # define the sicd metadata
        self._find_sicd()
        if not self.is_sicd:
            raise SarpyIOError('Could not find the SICD XML des.')

    @property
    def is_sicd(self) -> bool:
        """
        bool: whether file name corresponds to a SICD file, or not.
        """
        pass

    @property
    def sicd_meta(self) -> SICDType:
        """
        SICDType: the sicd meta-data structure.
        """
        pass

    @property
    def des_header(self) -> Optional[DataExtensionHeader]:
        """
        The DES subheader object associated with the SICD.

        Returns
        -------
        DataExtensionHeader
        """
        pass

    def _find_sicd(self) -> None:
        pass
        # TODO: account for the reference frequency offset situation


#######
#  The actual reading implementation

class SICDReader(NITFReader, SICDTypeReader):
    """
    A SICD reader implementation - file is NITF container following specified rules.

    **Changed in version 1.3.0** for reading changes.
    """
    _maximum_number_of_images = 1

    def __init__(self, nitf_details):
        """

        Parameters
        ----------
        nitf_details :  : str|BinaryIO|SICDDetails
            filename, file-like object, or SICDDetails object
        """

        if isinstance(nitf_details, str) or is_file_like(nitf_details):
            nitf_details = SICDDetails(nitf_details)
        if not isinstance(nitf_details, SICDDetails):
            raise TypeError(
                'The input argument for SICDReader must be a filename, file-like object, '
                'or SICDDetails object.')

        SICDTypeReader.__init__(self, None, nitf_details.sicd_meta)
        NITFReader.__init__(self, nitf_details, reader_type='SICD')
        self._check_sizes()

    @property
    def nitf_details(self) -> SICDDetails:
        """
        SICDDetails: The SICD NITF details object.
        """
        pass

    def get_nitf_dict(self) -> Dict:
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
        out['ISORCE'] = self.nitf_details.img_headers[0].ISORCE
        out['IID2'] = self.nitf_details.img_headers[0].IID2
        return out

    def populate_nitf_information_into_sicd(self):
        """
        Populate some pertinent NITF header information into the SICD structure.
        This provides more faithful copying or rewriting options.
        """

        self._sicd_meta.NITF = self.get_nitf_dict()

    def depopulate_nitf_information(self):
        """
        Eliminates the NITF information dict from the SICD structure.
        """
        pass

    def get_format_function(
            self,
            raw_dtype: numpy.dtype,
            complex_order: Optional[str] = None,
            lut: Optional[numpy.ndarray] = None,
            band_dimension: int = -1,
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


########
# base expected functionality for a module with an implemented Reader

def is_a(file_name: Union[str, BinaryIO]) -> Optional[SICDReader]:
    """
    Tests whether a given file_name corresponds to a SICD file, and returns
    a reader instance, if so.

    Parameters
    ----------
    file_name : str
        the file_name to check

    Returns
    -------
    SICDReader|None
    """
    pass


#######
#  The actual writing implementation

def validate_sicd_for_writing(sicd_meta: SICDType) -> SICDType:
    """
    Helper method which ensures the provided SICD structure provides enough
    information to support file writing, as well as ensures a few basic items
    are populated as appropriate.

    Parameters
    ----------
    sicd_meta : SICDType

    Returns
    -------
    SICDType
        This returns a deep copy of the provided SICD structure, with any
        necessary modifications.
    """

    if not isinstance(sicd_meta, SICDType):
        raise ValueError('sicd_meta is required to be an instance of SICDType, got {}'.format(type(sicd_meta)))
    if sicd_meta.ImageData is None:
        raise ValueError('The sicd_meta has un-populated ImageData, and nothing useful can be inferred.')
    if sicd_meta.ImageData.NumCols is None or sicd_meta.ImageData.NumRows is None:
        raise ValueError('The sicd_meta has ImageData with unpopulated NumRows or NumCols, '
                         'and nothing useful can be inferred.')
    if sicd_meta.ImageData.PixelType is None:
        logger.warning('The PixelType for sicd_meta is unset, so defaulting to RE32F_IM32F.')
        sicd_meta.ImageData.PixelType = 'RE32F_IM32F'

    sicd_meta = sicd_meta.copy()

    profile = '{} {}'.format(__title__, __version__)
    # use naive datetime because numpy warns about parsing timezone aware
    now = numpy.datetime64(datetime.datetime.now(tz=datetime.timezone.utc).replace(tzinfo=None))
    if sicd_meta.ImageCreation is None:
        sicd_meta.ImageCreation = ImageCreationType(
            Application=profile,
            DateTime=now,
            Profile=profile)
    else:
        sicd_meta.ImageCreation.Profile = profile
        if sicd_meta.ImageCreation.DateTime is None:
            sicd_meta.ImageCreation.DateTime = now
    return sicd_meta


def extract_clas(sicd: SICDType) -> str:
    """
    Extract the classification string from a SICD as appropriate for NITF Security
    tags CLAS attribute.

    Parameters
    ----------
    sicd : SICDType

    Returns
    -------
    str
    """
    if sicd.CollectionInfo is None or sicd.CollectionInfo.Classification is None:
        return 'U'

    c_str = sicd.CollectionInfo.Classification.upper().strip()

    if 'UNCLASS' in c_str or c_str == 'U':
        return 'U'
    elif 'CONFIDENTIAL' in c_str or c_str == 'C' or c_str.startswith('C/'):
        return 'C'
    elif 'TOP SECRET' in c_str or c_str == 'TS' or c_str.startswith('TS/'):
        return 'T'
    elif 'SECRET' in c_str or c_str == 'S' or c_str.startswith('S/'):
        return 'S'
    elif 'FOUO' in c_str.upper() or 'RESTRICTED' in c_str.upper():
        return 'R'
    else:
        logger.error(
            'Unclear how to extract CLAS for classification string {}.\n\t'
            'Should be set appropriately.'.format(c_str))
        return 'U'


def create_security_tags_from_sicd(sicd_meta: SICDType) -> NITFSecurityTags:
    def get_basic_args():
        out = {}
        sec_tags = sicd_meta.NITF.get('Security', {})
        # noinspection PyProtectedMember
        for fld in NITFSecurityTags._ordering:
            if fld in sec_tags:
                out[fld] = sec_tags[fld]
        return out

    def get_clas():
        if 'CLAS' in args:
            return
        args['CLAS'] = extract_clas(sicd_meta)

    def get_code(in_str):
        if 'CODE' in args:
            return

        # TODO: this is pretty terrible...
        code = re.search('(?<=/)[^/].*', in_str)
        if code is not None:
            args['CODE'] = code.group()

    def get_clsy():
        if args.get('CLSY', '').strip() == '':
            args['CLSY'] = 'US'

    args = get_basic_args()
    if sicd_meta.CollectionInfo is not None:
        get_clas()
        get_code(sicd_meta.CollectionInfo.Classification)
        get_clsy()

    return NITFSecurityTags(**args)


class SICDWritingDetails(NITFWritingDetails):
    """
    Manager for all the NITF subheader information associated with the SICD.

    Introduced in version 1.3.0.
    """

    __slots__ = (
        '_sicd_meta', '_security_tags', '_row_limit', '_check_older_version',
        '_required_version')

    def __init__(
            self,
            sicd_meta: SICDType,
            row_limit: Optional[int] = None,
            additional_des: Optional[Sequence[DESSubheaderManager]] = None,
            text_managers: Optional[Tuple[TextSubheaderManager, ...]] = None,
            res_managers: Optional[Tuple[RESSubheaderManager, ...]] = None,
            check_older_version: bool = False):
        """

        Parameters
        ----------
        sicd_meta : SICDType
        row_limit : None|int
            Desired row limit for the sicd image segments. Non-positive values
            or values > 99999 will be ignored.
        additional_des : None|Sequence[DESSubheaderManager]
        text_managers: Optional[Tuple[TextSubheaderManager, ...]]
        res_managers: Optional[Tuple[RESSubheaderManager, ...]]
        check_older_version : bool
            Try to create an older version sicd, for compliance
        """

        self._check_older_version = bool(check_older_version)
        self._security_tags = None
        self._sicd_meta = None
        self._set_sicd_meta(sicd_meta)
        self._required_version = self.sicd_meta.version_required()
        self._create_security_tags()
        self._row_limit = None
        self._set_row_limit(row_limit)

        header = self._create_header()
        image_managers, image_segment_collections, image_segment_coordinates = self._create_image_segments()
        des_managers = self._create_des_segments(additional_des)

        # NB: graphics not permitted in sicd
        NITFWritingDetails.__init__(
            self,
            header,
            image_managers=image_managers,
            image_segment_collections=image_segment_collections,
            image_segment_coordinates=image_segment_coordinates,
            text_managers=text_managers,
            des_managers=des_managers,
            res_managers=res_managers)

    @property
    def sicd_meta(self) -> SICDType:
        """
        SICDType: The sicd metadata
        """
        pass

    def _set_sicd_meta(self, value):
        pass

    @property
    def requires_version(self) -> Tuple[int, int, int]:
        """
        Tuple[int, int, int]: What is the required (at minimum) sicd version?
        """
        pass

    @property
    def row_limit(self) -> int:
        pass

    def _set_row_limit(self, value):
        pass

    @property
    def security_tags(self) -> NITFSecurityTags:
        """
        NITFSecurityTags: The default NITF security tags for use.
        """
        pass

    def _create_security_tags(self) -> None:
        """
        Creates a NITF security tags object with `CLAS` and `CODE` attributes in
        the sicd_meta.NITF property and/or extracted from the
        SICD.CollectionInfo.Classification value.

        Returns
        -------
        None
        """
        pass

    def _get_ftitle(self) -> str:
        pass

    def _get_fdt(self):
        pass

    def _get_idatim(self) -> str:
        pass

    def _get_ostaid(self) -> str:
        pass

    def _get_isorce(self) -> str:
        pass

    def _get_iid2(self) -> str:
        pass

    def _create_header(self) -> NITFHeader:
        """
        Create the main NITF header.

        Returns
        -------
        NITFHeader
        """
        pass

    def _create_image_segments(self) -> Tuple[
            Tuple[ImageSubheaderManager, ...],
            Tuple[Tuple[int, ...], ...],
            Tuple[Tuple[Tuple[int, ...], ...]]]:
        pass

    def _create_sicd_des(self) -> DESSubheaderManager:
        pass

    def _create_des_segments(
            self,
            additional_des: Optional[Sequence[DESSubheaderManager]]) -> Tuple[DESSubheaderManager, ...]:

        pass


class SICDWriter(NITFWriter):
    """
    Writer class for a SICD file - a NITF file containing complex radar data and
    SICD data extension.

    **Changed in version 1.3.0** to reflect NITFWriter changes.
    """

    def __init__(
            self,
            file_object: Union[str, BinaryIO],
            sicd_meta: Optional[SICDType] = None,
            sicd_writing_details: Optional[SICDWritingDetails] = None,
            check_older_version: bool = False,
            check_existence: bool = True,
            in_memory: bool = None):
        """

        Parameters
        ----------
        file_object : str|BinaryIO
        sicd_meta : None|SICDType
        sicd_writing_details : None|SICDWritingDetails
        check_older_version : bool
            Try to create an older version sicd, for compliance with standard
            NGA applications like SOCET or RemoteView
        check_existence : bool
            Should we check if the given file already exists?
        in_memory : bool
            If True force in-memory writing, if False force file writing.
        """

        if sicd_meta is None and sicd_writing_details is None:
            raise ValueError('One of sicd_meta or sicd_writing_details must be provided.')
        if sicd_writing_details is None:
            sicd_writing_details = SICDWritingDetails(sicd_meta, check_older_version=check_older_version)
        NITFWriter.__init__(
            self, file_object, sicd_writing_details, check_existence=check_existence, in_memory=in_memory)

    @property
    def nitf_writing_details(self) -> SICDWritingDetails:
        """
        SICDWritingDetails: The SICD/NITF subheader details.
        """
        pass

    @nitf_writing_details.setter
    def nitf_writing_details(self, value):
        pass

    @property
    def sicd_meta(self) -> SICDType:
        pass

    def get_format_function(
            self,
            raw_dtype: numpy.dtype,
            complex_order: Optional[str] = None,
            lut: Optional[numpy.ndarray] = None,
            band_dimension: int = -1,
            image_segment_index: Optional[int] = None,
            **kwargs) -> Optional[FormatFunction]:
        pass
