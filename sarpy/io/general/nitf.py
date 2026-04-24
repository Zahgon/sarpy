"""
Module laying out basic functionality for reading and writing NITF files.

Updated extensively in version 1.3.0.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import logging
import os

from typing import Union, List, Tuple, BinaryIO, Sequence, Optional
from tempfile import mkstemp
from collections import OrderedDict, namedtuple
import struct
from io import BytesIO

import numpy

from sarpy.io.general.base import SarpyIOError, BaseReader, BaseWriter
from sarpy.io.general.format_function import FormatFunction, ComplexFormatFunction, \
    SingleLUTFormatFunction
from sarpy.io.general.data_segment import DataSegment, BandAggregateSegment, \
    BlockAggregateSegment, SubsetSegment, NumpyArraySegment, NumpyMemmapSegment, \
    FileReadDataSegment

# noinspection PyProtectedMember
from sarpy.io.general.nitf_elements.nitf_head import NITFHeader, NITFHeader0, \
    ImageSegmentsType, GraphicsSegmentsType, TextSegmentsType, \
    DataExtensionsType, ReservedExtensionsType, _ItemArrayHeaders
from sarpy.io.general.nitf_elements.text import TextSegmentHeader, TextSegmentHeader0
from sarpy.io.general.nitf_elements.graphics import GraphicsSegmentHeader
from sarpy.io.general.nitf_elements.symbol import SymbolSegmentHeader
from sarpy.io.general.nitf_elements.label import LabelSegmentHeader
from sarpy.io.general.nitf_elements.res import ReservedExtensionHeader, ReservedExtensionHeader0
from sarpy.io.general.nitf_elements.image import ImageSegmentHeader, ImageSegmentHeader0, MaskSubheader
from sarpy.io.general.nitf_elements.des import DataExtensionHeader, DataExtensionHeader0
from sarpy.io.general.utils import is_file_like, is_nitf, is_real_file

from sarpy.io.complex.sicd_elements.blocks import LatLonType
from sarpy.geometry.geocoords import ecf_to_geodetic, geodetic_to_ecf
from sarpy.geometry.latlon import num as lat_lon_parser

try:
    # noinspection PyPackageRequirements
    import pyproj
except ImportError:
    pyproj = None

try:
    # noinspection PyPackageRequirements
    from PIL import Image as PIL_Image
    PIL_Image.MAX_IMAGE_PIXELS = None  # get rid of decompression bomb checking
    from PIL import ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True
except ImportError:
    PIL_Image = None
    ImageFile = None

import platform
system_os = platform.system()
if system_os == 'Linux':
    try:
        import resource
    except ImportError:
        resource = None

logger = logging.getLogger(__name__)

_unhandled_version_text = 'Unhandled NITF version `{}`'


#####
# helper functions

def extract_image_corners(
        img_header: Union[ImageSegmentHeader, ImageSegmentHeader0]) -> Union[None, numpy.ndarray]:
    """
    Extract the image corner point array for the image segment header.

    Parameters
    ----------
    img_header : ImageSegmentHeader

    Returns
    -------
    numpy.ndarray
    """

    corner_string = img_header.IGEOLO
    # NB: there are 4 corner point string, each of length 15
    corner_strings = [corner_string[start:stop] for start, stop in zip(range(0, 59, 15), range(15, 74, 15))]

    icps = []
    # TODO: handle ICORDS == 'U', which is MGRS
    if img_header.ICORDS in ['N', 'S']:
        if pyproj is None:
            logger.error('ICORDS is {}, which requires pyproj, which was not successfully imported.')
            return None
        for entry in corner_strings:
            the_proj = pyproj.Proj(proj='utm', zone=int(entry[:2]), south=(img_header.ICORDS == 'S'), ellps='WGS84')
            lon, lat = the_proj(float(entry[2:8]), float(entry[8:]), inverse=True)
            icps.append([lon, lat])
    elif img_header.ICORDS == 'D':
        icps = [[float(corner[:7]), float(corner[7:])] for corner in corner_strings]
    elif img_header.ICORDS == 'G':
        icps = [[lat_lon_parser(corner[:7]), lat_lon_parser(corner[7:])] for corner in corner_strings]
    else:
        logger.error('Got unhandled ICORDS {}'.format(img_header.ICORDS))
        return None
    return numpy.array(icps, dtype='float64')


def find_jpeg_delimiters(the_bytes: bytes) -> List[Tuple[int, int]]:
    """
    Finds regular jpeg delimiters from the image segment bytes.

    Parameters
    ----------
    the_bytes : bytes

    Returns
    -------
    List[Tuple[int, int]]

    Raises
    ------
    ValueError
        If the bytes doesn't start with the beginning jpeg delimiter and end with the
        end jpeg delimiter.
    """
    pass


def _get_shape(rows: int, cols: int, bands: int, band_dimension=2) -> Tuple[int, ...]:
    """
    Helper function for turning rows/cols/bands into a shape tuple.

    Parameters
    ----------
    rows: int
    cols: int
    bands: int
    band_dimension : int
        One of `{0, 1, 2}`.

    Returns
    -------
    shape_tuple : Tuple[int, ...]
        The shape tuple with band omitted if `bands=1`
    """
    pass


def _get_subscript_def(
        row_start: int,
        row_end: int,
        col_start: int,
        col_end: int,
        raw_bands: int,
        raw_band_dimension: int) -> Tuple[slice, ...]:
    pass


def _construct_block_bounds(
        image_header: Union[ImageSegmentHeader, ImageSegmentHeader0]) -> List[Tuple[int, int, int, int]]:
    """
    Construct the bounds for the blocking definition in row/column space for
    the image segment.

    Note that this includes potential pad pixels, since NITF requires that
    each block is the same size.

    Parameters
    ----------
    image_header : ImageSegmentHeader|ImageSegmentHeader

    Returns
    -------
    List[Tuple[int, int, int, int]]
        This is a list of the form `(row start, row end, column start, column end)`.
    """
    pass


def _get_dtype(
        image_header: Union[ImageSegmentHeader, ImageSegmentHeader0]
        ) -> Tuple[numpy.dtype, numpy.dtype, int, Optional[str], Optional[numpy.ndarray]]:
    """
    Gets the information necessary for constructing the format function applicable
    to the given image segment.

    Parameters
    ----------
    image_header : ImageSegmentHeader|ImageSegmentHeader

    Returns
    -------
    raw_dtype: numpy.ndtype
        The native data type
    formatted_dtype : numpy.dtype
        The formatted data type. Will be `complex64` if `complex_order` is
        populated, the data type of `lut` if it is populated, or same as
        `raw_dtype`.
    formatted_bands : int
        How many bands in the formatted output. Similarly depends on the
        value of `complex_order` and `lut`.
    complex_order : None|str
        If populated, one of `('IQ', 'QI', 'MP', 'PM')` indicating the
        order of complex bands. This will only be populated if consistent.
    lut : None|numpy.ndarray
        If populated, the lookup table presented in the data.
    """
    pass


def _get_format_function(
        raw_dtype: numpy.dtype,
        complex_order: Optional[str] = None,
        lut: Optional[numpy.ndarray] = None,
        band_dimension: int = -1) -> Optional[FormatFunction]:
    """
    Gets the format function for use in a data segment.

    Parameters
    ----------
    raw_dtype : numpy.dtype
    complex_order : None|str
    lut : None|numpy.ndarray
    band_dimension : int

    Returns
    -------
    None|FormatFunction
    """

    if complex_order is not None:
        return ComplexFormatFunction(raw_dtype, complex_order, band_dimension=band_dimension)
    elif lut is not None:
        return SingleLUTFormatFunction(lut)
    else:
        return None


def _verify_image_segment_compatibility(
        img0: Union[ImageSegmentHeader, ImageSegmentHeader0],
        img1: Union[ImageSegmentHeader, ImageSegmentHeader0]) -> bool:
    """
    Verify that the image segments are compatible from the data formatting
    perspective.

    Parameters
    ----------
    img0 : ImageSegmentHeader
    img1 : ImageSegmentHeader

    Returns
    -------
    bool
    """
    pass


def _get_collection_element_coordinate_limits(
        image_headers: Sequence[Union[ImageSegmentHeader, ImageSegmentHeader0]],
        return_clevel: bool = False) -> Union[numpy.ndarray, Tuple[numpy.ndarray, int]]:
    """
    For the given collection of image segments, get the relative coordinate
    scheme of the form `[[start_row, end_row, start_column, end_column]]`.

    This relies on inspection of `IALVL` and `ILOC` values for this
    collection of image segments.

    Parameters
    ----------
    image_headers : Sequence[ImageSegmentHeader]
    return_clevel : bool
        Also calculate and return the clevel for this?

    Returns
    -------
    block_definition: numpy.ndarray
        of the form `[[start_row, end_row, start_column, end_column]]`.
    clevel: int
        The CLEVEL for this common coordinate system, only returned if
        `return_clevel=True`
    """
    pass


class NITFDetails(object):
    """
    This class allows for somewhat general parsing of the header information in
    a NITF 2.0 or 2.1 file.
    """

    __slots__ = (
        '_file_name', '_file_object', '_close_after',
        '_nitf_version', '_nitf_header', '_img_headers',

        'img_subheader_offsets', 'img_subheader_sizes',
        'img_segment_offsets', 'img_segment_sizes',

        'graphics_subheader_offsets', 'graphics_subheader_sizes',  # only 2.1
        'graphics_segment_offsets', 'graphics_segment_sizes',

        'symbol_subheader_offsets', 'symbol_subheader_sizes',  # only 2.0
        'symbol_segment_offsets', 'symbol_segment_sizes',

        'label_subheader_offsets', 'label_subheader_sizes',  # only 2.0
        'label_segment_offsets', 'label_segment_sizes',

        'text_subheader_offsets', 'text_subheader_sizes',
        'text_segment_offsets', 'text_segment_sizes',

        'des_subheader_offsets', 'des_subheader_sizes',
        'des_segment_offsets', 'des_segment_sizes',

        'res_subheader_offsets', 'res_subheader_sizes',  # only 2.1
        'res_segment_offsets', 'res_segment_sizes')

    def __init__(self, file_object: Union[str, BinaryIO]):
        """

        Parameters
        ----------
        file_object : str|BinaryIO
            file name for a NITF file, or file like object opened in binary mode.
        """

        self._img_headers = None
        self._file_name = None
        self._file_object = None
        self._close_after = False

        if isinstance(file_object, str):
            if not os.path.isfile(file_object):
                raise SarpyIOError('Path {} is not a file'.format(file_object))
            self._file_name = file_object
            self._file_object = open(file_object, 'rb')
            self._close_after = True
        elif is_file_like(file_object):
            self._file_object = file_object
            if hasattr(file_object, 'name') and isinstance(file_object.name, str):
                self._file_name = file_object.name
            else:
                self._file_name = '<file like object>'
        else:
            raise TypeError('file_object is required to be a file like object, or string path to a file.')

        is_nitf_file, vers_string = is_nitf(self._file_object, return_version=True)
        if not is_nitf_file:
            raise SarpyIOError('Not a NITF file')
        self._nitf_version = vers_string

        if self._nitf_version not in ['02.10', '02.00']:
            raise SarpyIOError('Unsupported NITF version {} for file {}'.format(self._nitf_version, self._file_name))

        if self._nitf_version == '02.10':
            self._file_object.seek(354, os.SEEK_SET)  # offset to header length field
            header_length = int(self._file_object.read(6))
            # go back to the beginning of the file, and parse the whole header
            self._file_object.seek(0, os.SEEK_SET)
            header_string = self._file_object.read(header_length)
            self._nitf_header = NITFHeader.from_bytes(header_string, 0)
        elif self._nitf_version == '02.00':
            self._file_object.seek(280, os.SEEK_SET)  # offset to check if DEVT is defined
            # advance past security tags
            DWSG = self._file_object.read(6)
            if DWSG == b'999998':
                self._file_object.seek(40, os.SEEK_CUR)
            # seek to header length field
            self._file_object.seek(68, os.SEEK_CUR)
            header_length = int(self._file_object.read(6))
            self._file_object.seek(0, os.SEEK_SET)
            header_string = self._file_object.read(header_length)
            self._nitf_header = NITFHeader0.from_bytes(header_string, 0)
        else:
            raise ValueError(_unhandled_version_text.format(self._nitf_version))

        if self._nitf_header.get_bytes_length() != header_length:
            logger.critical(
                'Stated header length of file {} is {},\n\t'
                'while the interpreted header length is {}.\n\t'
                'This will likely be accompanied by serious parsing failures,\n\t'
                'and should be reported to the sarpy team for investigation.'.format(
                    self._file_name, header_length, self._nitf_header.get_bytes_length()))
        cur_loc = header_length
        # populate image segment offset information
        cur_loc, self.img_subheader_offsets, self.img_subheader_sizes, \
            self.img_segment_offsets, self.img_segment_sizes = self._element_offsets(
                cur_loc, self._nitf_header.ImageSegments)

        # populate graphics segment offset information - only version 2.1
        cur_loc, self.graphics_subheader_offsets, self.graphics_subheader_sizes, \
            self.graphics_segment_offsets, self.graphics_segment_sizes = self._element_offsets(
                cur_loc, getattr(self._nitf_header, 'GraphicsSegments', None))

        # populate symbol segment offset information - only version 2.0
        cur_loc, self.symbol_subheader_offsets, self.symbol_subheader_sizes, \
            self.symbol_segment_offsets, self.symbol_segment_sizes = self._element_offsets(
                cur_loc, getattr(self._nitf_header, 'SymbolsSegments', None))
        # populate label segment offset information - only version 2.0
        cur_loc, self.label_subheader_offsets, self.label_subheader_sizes, \
            self.label_segment_offsets, self.label_segment_sizes = self._element_offsets(
                cur_loc, getattr(self._nitf_header, 'LabelsSegments', None))

        # populate text segment offset information
        cur_loc, self.text_subheader_offsets, self.text_subheader_sizes, \
            self.text_segment_offsets, self.text_segment_sizes = self._element_offsets(
                cur_loc, self._nitf_header.TextSegments)
        # populate data extension offset information
        cur_loc, self.des_subheader_offsets, self.des_subheader_sizes, \
            self.des_segment_offsets, self.des_segment_sizes = self._element_offsets(
                cur_loc, self._nitf_header.DataExtensions)
        # populate data extension offset information - only version 2.1
        cur_loc, self.res_subheader_offsets, self.res_subheader_sizes, \
            self.res_segment_offsets, self.res_segment_sizes = self._element_offsets(
                cur_loc, getattr(self._nitf_header, 'ReservedExtensions', None))

    @staticmethod
    def _element_offsets(
            cur_loc: int,
            item_array_details: Union[_ItemArrayHeaders, None]
    ) -> Tuple[int, Optional[numpy.ndarray], Optional[numpy.ndarray], Optional[numpy.ndarray], Optional[numpy.ndarray]]:

        pass

    @property
    def file_name(self) -> Optional[str]:
        """
        None|str: the file name, which may not be useful if the input was based
        on a file like object
        """
        pass

    @property
    def file_object(self) -> BinaryIO:
        """
        BinaryIO: The binary file object
        """
        pass

    @property
    def nitf_header(self) -> Union[NITFHeader, NITFHeader0]:
        """
        NITFHeader: the nitf header object
        """
        pass

    @property
    def img_headers(self) -> Union[None, List[ImageSegmentHeader], List[ImageSegmentHeader0]]:
        """
        The image segment headers.

        Returns
        -------
        None|List[ImageSegmentHeader]|List[ImageSegmentHeader0]
            Only `None` in the unlikely event that there are no image segments.
        """
        pass

    @property
    def nitf_version(self) -> str:
        """
        str: The NITF version number.
        """
        pass

    def _parse_img_headers(self) -> None:
        pass

    def _fetch_item(
            self,
            name: str,
            index: int,
            offsets: numpy.ndarray,
            sizes: numpy.ndarray) -> bytes:
        if index >= offsets.size:
            raise IndexError(
                'There are only {0:d} {1:s}, invalid {1:s} position {2:d}'.format(
                    offsets.size, name, index))
        the_offset = offsets[index]
        the_size = sizes[index]
        self._file_object.seek(int(the_offset), os.SEEK_SET)
        the_item = self._file_object.read(int(the_size))
        return the_item

    def get_image_subheader_bytes(self, index: int) -> bytes:
        """
        Fetches the image segment subheader at the given index.

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def parse_image_subheader(self, index: int) -> Union[ImageSegmentHeader, ImageSegmentHeader0]:
        """
        Parse the image segment subheader at the given index.

        Parameters
        ----------
        index : int

        Returns
        -------
        ImageSegmentHeader|ImageSegmentHeader0
        """
        pass

    def get_image_bytes(self, index: int) -> bytes:
        """
        Fetches the image bytes at the given index.

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def get_text_subheader_bytes(self, index: int) -> bytes:
        """
        Fetches the text segment subheader at the given index.

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def get_text_bytes(self, index: int) -> bytes:
        """
        Fetches the text extension segment bytes at the given index.

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def parse_text_subheader(self, index: int) -> Union[TextSegmentHeader, TextSegmentHeader0]:
        """
        Parse the text segment subheader at the given index.

        Parameters
        ----------
        index : int

        Returns
        -------
        TextSegmentHeader|TextSegmentHeader0
        """
        pass

    def get_graphics_subheader_bytes(self, index: int) -> bytes:
        """
        Fetches the graphics segment subheader at the given index (only version 2.1).

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def get_graphics_bytes(self, index: int) -> bytes:
        """
        Fetches the graphics extension segment bytes at the given index (only version 2.1).

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def parse_graphics_subheader(self, index: int) -> GraphicsSegmentHeader:
        """
        Parse the graphics segment subheader at the given index (only version 2.1).

        Parameters
        ----------
        index : int

        Returns
        -------
        GraphicsSegmentHeader
        """
        pass

    def get_symbol_subheader_bytes(self, index: int) -> bytes:
        """
        Fetches the symbol segment subheader at the given index (only version 2.0).

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def get_symbol_bytes(self, index: int) -> bytes:
        """
        Fetches the symbol extension segment bytes at the given index (only version 2.0).

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def parse_symbol_subheader(self, index: int) -> SymbolSegmentHeader:
        """
        Parse the symbol segment subheader at the given index (only version 2.0).

        Parameters
        ----------
        index : int

        Returns
        -------
        SymbolSegmentHeader
        """
        pass

    def get_label_subheader_bytes(self, index: int) -> bytes:
        """
        Fetches the label segment subheader at the given index (only version 2.0).

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def get_label_bytes(self, index: int) -> bytes:
        """
        Fetches the label extension segment bytes at the given index (only version 2.0).

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def parse_label_subheader(self, index: int) -> LabelSegmentHeader:
        """
        Parse the label segment subheader at the given index (only version 2.0).

        Parameters
        ----------
        index : int

        Returns
        -------
        LabelSegmentHeader
        """
        pass

    def get_des_subheader_bytes(self, index: int) -> bytes:
        """
        Fetches the data extension segment subheader bytes at the given index.

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """

        return self._fetch_item(
            'des subheader',
            index,
            self.des_subheader_offsets,
            self._nitf_header.DataExtensions.subhead_sizes)

    def get_des_bytes(self, index: int) -> bytes:
        """
        Fetches the data extension segment bytes at the given index.

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """

        return self._fetch_item(
            'des',
            index,
            self.des_segment_offsets,
            self._nitf_header.DataExtensions.item_sizes)

    def parse_des_subheader(self, index: int) -> Union[DataExtensionHeader, DataExtensionHeader0]:
        """
        Parse the data extension segment subheader at the given index.

        Parameters
        ----------
        index : int

        Returns
        -------
        DataExtensionHeader|DataExtensionHeader0
        """
        pass

    def get_res_subheader_bytes(self, index: int) -> bytes:
        """
        Fetches the reserved extension segment subheader bytes at the given index (only version 2.1).

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def get_res_bytes(self, index: int) -> bytes:
        """
        Fetches the reserved extension segment bytes at the given index (only version 2.1).

        Parameters
        ----------
        index : int

        Returns
        -------
        bytes
        """
        pass

    def parse_res_subheader(self, index: int) -> Union[ReservedExtensionHeader, ReservedExtensionHeader0]:
        """
        Parse the reserved extension subheader at the given index (only version 2.1).

        Parameters
        ----------
        index : int

        Returns
        -------
        ReservedExtensionHeader|ReservedExtensionHeader0
        """
        pass

    def get_headers_json(self) -> dict:
        """
        Get a json (i.e. dict) representation of the NITF header elements.

        Returns
        -------
        dict
        """
        pass

    def close(self):
        if self._close_after:
            self._close_after = False
            # noinspection PyBroadException
            try:
                self._file_object.close()
            except Exception:
                pass

    def __del__(self):
        self.close()


class NITFReader(BaseReader):
    """
    A reader implementation based around array-type image data fetching for
    NITF 2.0 or 2.1 files.

    **Significantly revised in version 1.3.0** to accommodate the new data segment
    paradigm. General NITF support is improved from previous version, but there
    remain unsupported edge cases.
    """

    _maximum_number_of_images = None
    unsupported_compressions = ('I1', 'C1', 'C4', 'C6', 'C7', 'M1', 'M4', 'M6', 'M7')

    __slots__ = (
        '_nitf_details', '_unsupported_segments', '_image_segment_collections',
        '_reverse_axes', '_transpose_axes', '_image_segment_data_segments')

    def __init__(
            self,
            nitf_details: Union[str, BinaryIO, NITFDetails],
            reader_type="OTHER",
            reverse_axes: Union[None, int, Sequence[int]] = None,
            transpose_axes: Union[None, Tuple[int, ...]] = None):
        """

        Parameters
        ----------
        nitf_details : str|BinaryIO|NITFDetails
            The NITFDetails object or path to a nitf file.
        reader_type : str
            What type of reader is this? e.g. "SICD", "SIDD", "OTHER"
        reverse_axes : None|Sequence[int]
            Any entries should be restricted to `{0, 1}`. The presence of
            `0` means to reverse the rows (in the raw sense), and the presence
            of `1` means to reverse the columns (in the raw sense).
        transpose_axes : None|Tuple[int, ...]
            If presented this should be only `(1, 0)`.
        """

        self._image_segment_data_segments = {}
        try:
            _ = self._delete_temp_files
            # something has already defined this, so it's already ready
        except AttributeError:
            self._delete_temp_files = []

        try:
            _ = self._nitf_details
            # something has already defined this, so it's already ready
        except AttributeError:
            if isinstance(nitf_details, str) or is_file_like(nitf_details):
                nitf_details = NITFDetails(nitf_details)
            if not isinstance(nitf_details, NITFDetails):
                raise TypeError('The input argument for NITFReader must be a NITFDetails object.')
            self._nitf_details = nitf_details
        if self._nitf_details.img_headers is None:
            raise SarpyIOError(
                'The input NITF has no image segments,\n\t'
                'so there is no image data to be read.')

        if reverse_axes is not None:
            if isinstance(reverse_axes, int):
                reverse_axes = (reverse_axes, )

            for entry in reverse_axes:
                if not 0 <= entry < 2:
                    raise ValueError('reverse_axes values must be restricted to `{0, 1}`.')
        self._reverse_axes = reverse_axes

        if transpose_axes is not None:
            if transpose_axes != (1, 0):
                raise ValueError('transpose_axes, if not None, must be (1, 0)')
        self._transpose_axes = transpose_axes

        # find image segments which we can not support, for whatever reason
        self._unsupported_segments = self.check_for_compliance()
        if len(self._unsupported_segments) == len(self.nitf_details.img_headers):
            raise SarpyIOError('There are no supported image segments in NITF file {}'.format(self.file_name))

        # our supported images are assembled into collections for joint presentation
        self._image_segment_collections = self.find_image_segment_collections()
        if self._maximum_number_of_images is not None and \
                len(self._image_segment_collections) > self._maximum_number_of_images:
            raise SarpyIOError(
                'Images in this NITF are grouped together in {} collections,\n\t'
                'which exceeds the maximum number of collections permitted ({})\n\t'
                'by class {} implementation'.format(
                    len(self._image_segment_collections), self._maximum_number_of_images, self.__class__))
        self.verify_collection_compliance()

        data_segments = self.get_data_segments()
        BaseReader.__init__(self, data_segments, reader_type=reader_type, close_segments=True)

    @property
    def nitf_details(self) -> NITFDetails:
        """
        NITFDetails: The NITF details object.
        """
        pass

    def get_image_header(self, index: int) -> Union[ImageSegmentHeader, ImageSegmentHeader0]:
        """
        Gets the image subheader at the specified index.

        Parameters
        ----------
        index : int

        Returns
        -------
        ImageSegmentHeader|ImageSegmentHeader0
        """
        pass

    @property
    def file_name(self) -> Optional[str]:
        pass

    @property
    def file_object(self) -> BinaryIO:
        """
        BinaryIO: the binary file like object from which we are reading
        """
        pass

    @property
    def unsupported_segments(self) -> Tuple[int, ...]:
        """
        Tuple[int, ...]: The image segments deemed not supported.
        """
        pass

    @property
    def image_segment_collections(self) -> Tuple[Tuple[int, ...]]:
        """
        The definition for how image segments are grouped together to form the
        output image collection.

        Each entry corresponds to a single output image, and the entry defines
        the image segment indices which are combined to make up the output image.

        Returns
        -------
        Tuple[Tuple[int, ...]]
        """
        pass

    def can_use_memmap(self) -> bool:
        """
        Can a memmap be used? This is only supported and/or sensible in the case
        that the file-like object represents a local file.

        Returns
        -------
        bool
        """
        pass

    def _read_file_data(self, start_bytes: int, byte_length: int) -> bytes:
        pass

    def _check_image_segment_for_compliance(
            self,
            index: int,
            img_header: Union[ImageSegmentHeader, ImageSegmentHeader0]) -> bool:
        """
        Checks whether the image segment can be (or should be) opened.

        Parameters
        ----------
        index : int
            The image segment index (for logging)
        img_header : ImageSegmentHeader|ImageSegmentHeader0
            The image segment header

        Returns
        -------
        bool
        """
        pass

    def check_for_compliance(self) -> Tuple[int, ...]:
        """
        Gets indices of image segments that cannot (or should not) be opened.

        Returns
        -------
        Tuple[int, ...]
        """
        pass

    def _construct_block_bounds(self, image_segment_index: int) -> List[Tuple[int, int, int, int]]:
        pass

    def _get_mask_details(
            self,
            image_segment_index: int) -> Tuple[Optional[numpy.ndarray], int, int]:
        """
        Gets the mask offset details.

        Parameters
        ----------
        image_segment_index : int

        Returns
        -------
        mask_offsets : Optional[numpy.ndarray]
            The mask byte offset from the end of the mask subheader definition.
            If `IMODE = S`, then this is two-dimensional, otherwise it is one
            dimensional
        exclude_value : int
            The offset value for excluded block, should always be `0xFFFFFFFF`.
        additional_offset : int
            The additional offset from the beginning of the image segment data,
            necessary to account for the presence of mask subheader.
        """
        pass

    def _get_dtypes(
            self,
            image_segment_index: int) -> Tuple[numpy.dtype, numpy.dtype, int, Optional[str], Optional[numpy.ndarray]]:
        pass

    def _get_transpose(self, formatted_bands: int) -> Optional[Tuple[int, ...]]:
        pass

    # noinspection PyMethodMayBeStatic, PyUnusedLocal
    def get_format_function(
            self,
            raw_dtype: numpy.dtype,
            complex_order: Optional[str] = None,
            lut: Optional[numpy.ndarray] = None,
            band_dimension: int = -1,
            image_segment_index: Optional[int] = None,
            **kwargs) -> Optional[FormatFunction]:
        pass

    def _verify_image_segment_compatibility(self, index0: int, index1: int) -> bool:
        pass

    def find_image_segment_collections(self) -> Tuple[Tuple[int, ...]]:
        """
        Determines the image segments, other than those specifically excluded in
        `unsupported_segments` property value. It is implicitly assumed that the
        elements of a given entry are ordered so that IALVL values are sensible.

        Note that in the default implementation, every image segment is simply
        considered separately.

        Returns
        -------
        Tuple[Tuple[int]]
        """
        pass

    def verify_collection_compliance(self) -> None:
        """
        Verify that image segments collections are compatible.

        Raises
        -------
        ValueError
        """
        pass

    def _get_collection_element_coordinate_limits(self, collection_index: int) -> numpy.ndarray:
        """
        For the given image segment collection, as defined in the
        `image_segment_collections` property value, get the relative coordinate
        scheme of the form `[[start_row, end_row, start_column, end_column]]`.

        This relies on inspection of `IALVL` and `ILOC` values for this
        collection of image segments.

        Parameters
        ----------
        collection_index : int
            The index into the `image_segment_collection` list.

        Returns
        -------
        block_definition: numpy.ndarray
            of the form `[[start_row, end_row, start_column, end_column]]`.
        """
        pass

    def _handle_jpeg2k_no_mask(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        # NOTE: it appears that the PIL to numpy array conversion will rearrange
        # bands to be in the final dimension, regardless of storage particulars?

        pass

    def _handle_jpeg2k_with_mask(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        # NOTE: it appears that the PIL to numpy array conversion will rearrange
        # bands to be in the final dimension, regardless of storage particulars?

        pass

    def _handle_jpeg(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        # NOTE: it appears that the PIL to numpy array conversion will rearrange
        # bands to be in the final dimension, regardless of storage particulars?

        pass

    def _handle_no_compression(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        # NB: Natural order inside the block is (bands, rows, columns)
        pass

    def _handle_imode_s_jpeg(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        pass

    def _handle_imode_s_no_compression(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        pass

    def _create_data_segment_from_imode_b(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        pass

    def _create_data_segment_from_imode_p(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        pass

    def _create_data_segment_from_imode_r(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        pass

    def _create_data_segment_from_imode_s(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        pass

    def create_data_segment_for_image_segment(
            self,
            image_segment_index: int,
            apply_format: bool) -> DataSegment:
        """
        Creates the data segment for the given image segment.

        For consistency of simple usage, any bands will be presented in the
        final formatted/output dimension, regardless of the value of `apply_format`
        or `IMODE`.

        For compressed image segments, the `IMODE` has been
        abstracted away, and the data segment will be consistent with the raw
        shape having bands in the final dimension (analogous to `IMODE=P`).

        Note that this also stores a reference to the produced data segment in
        the `_image_segment_data_segments` dictionary.

        Parameters
        ----------
        image_segment_index : int
        apply_format : bool
            Leave data raw (False), or apply format function and global
            `reverse_axes` and `transpose_axes` values?

        Returns
        -------
        DataSegment
        """
        pass

    def create_data_segment_for_collection_element(self, collection_index: int) -> DataSegment:
        """
        Creates the data segment overarching the given segment collection.

        Parameters
        ----------
        collection_index : int

        Returns
        -------
        DataSegment
        """
        pass

    def get_data_segments(self) -> List[DataSegment]:
        """
        Gets a data segment for each of these image segment collection.

        Returns
        -------
        List[DataSegment]
        """
        pass

    def close(self) -> None:
        self._nitf_details.close()
        self._image_segment_data_segments = None
        BaseReader.close(self)


########
# base expected functionality for a module with an implemented Reader

def is_a(file_name: Union[str, BinaryIO]) -> Optional[NITFReader]:
    """
    Tests whether a given file_name corresponds to a nitf file. Returns a
    nitf reader instance, if so.

    Parameters
    ----------
    file_name : str|BinaryIO
        the file_name to check

    Returns
    -------
    None|NITFReader
        `NITFReader` instance if nitf file, `None` otherwise
    """
    pass


#####
# NITF writing elements

def interpolate_corner_points_string(
        entry: numpy.ndarray,
        rows: int,
        cols: int,
        icp: numpy.ndarray):
    """
    Interpolate the corner points for the given subsection from
    the given corner points. This supplies entries for the NITF headers.
    Parameters
    ----------
    entry : numpy.ndarray
        The corner pints of the form `(row_start, row_stop, col_start, col_stop)`
    rows : int
        The number of rows in the parent image.
    cols : int
        The number of cols in the parent image.
    icp : numpy.ndarray
        The parent image corner points in geodetic coordinates.

    Returns
    -------
    str
        suitable for IGEOLO entry.
    """

    if icp is None:
        return ''

    if icp.shape[1] == 2:
        icp_new = numpy.zeros((icp.shape[0], 3), dtype=numpy.float64)
        icp_new[:, :2] = icp
        icp = icp_new
    icp_ecf = geodetic_to_ecf(icp)

    const = 1. / (rows * cols)
    pattern = entry[numpy.array([(0, 2), (1, 2), (1, 3), (0, 3)], dtype=numpy.int64)]
    out = []
    for row, col in pattern:
        pt_array = const * numpy.sum(icp_ecf *
                                     (numpy.array([rows - row, row, row, rows - row]) *
                                      numpy.array([cols - col, cols - col, col, col]))[:, numpy.newaxis], axis=0)

        pt = LatLonType.from_array(ecf_to_geodetic(pt_array)[:2])
        dms = pt.dms_format(frac_secs=False)
        out.append('{0:02d}{1:02d}{2:02d}{3:s}'.format(*dms[0]) + '{0:03d}{1:02d}{2:02d}{3:s}'.format(*dms[1]))
    return ''.join(out)


def default_image_segmentation(rows: int, cols: int, row_limit: int) -> Tuple[Tuple[int, ...], ...]:
    """
    Determine the appropriate segmentation for the image. This is driven
    by the SICD/SIDD standard, and not the only generally feasible segmentation
    scheme for other NITF file types.

    Parameters
    ----------
    rows : int
    cols : int
    row_limit : int
        It is assumed that this follows the NITF guidelines

    Returns
    -------
    Tuple[Tuple[int, ...], ...]
        Of the form `((row start, row end, column start, column end))`
    """

    im_segments = []
    row_offset = 0
    while row_offset < rows:
        next_rows = min(rows, row_offset + row_limit)
        im_segments.append((row_offset, next_rows, 0, cols))
        row_offset = next_rows
    return tuple(im_segments)


def _flatten_bytes(value: Union[bytes, Sequence]) -> bytes:
    pass


class SubheaderManager(object):
    """
    Simple manager object for a NITF subheader, and it's associated information
    in the NITF writing process.

    Introduced in version 1.3.0.
    """

    __slots__ = (
        '_subheader',  '_subheader_offset', '_subheader_size',
        '_item_bytes', '_item_offset', '_item_size',
        '_subheader_written', '_item_written')

    item_bytes_required = True
    """
    Are you required to provide the item bytes?
    """

    subheader_type = None
    """
    What is the type for the subheader?
    """

    def __init__(self, subheader, item_bytes: Optional[bytes] = None):
        if not isinstance(subheader, self.subheader_type):
            raise TypeError(
                'subheader must be of type {} for class {}'.format(
                    self.subheader_type, self.__class__))
        self._subheader = subheader
        self._subheader_size = self._subheader.get_bytes_length()
        self._subheader_offset = None
        self._item_offset = None
        self._subheader_written = False
        self._item_written = False
        self._item_size = None

        self._item_bytes = None
        if item_bytes is None:
            if self.item_bytes_required:
                raise ValueError(
                    'item_bytes is required by class {}.'.format(
                        self.__class__))
        else:
            self.item_bytes = item_bytes

    @property
    def subheader(self):
        """
        The subheader.
        """
        pass

    @property
    def subheader_offset(self) -> Optional[int]:
        """
        int: The subheader offset.
        """
        pass

    @subheader_offset.setter
    def subheader_offset(self, value) -> None:
        pass

    @property
    def subheader_size(self) -> int:
        """
        int: The subheader size
        """
        pass

    @property
    def item_offset(self) -> Optional[int]:
        """
        int: The item offset.
        """
        pass

    @property
    def item_size(self) -> Optional[int]:
        """
        int: The item size
        """
        pass

    @item_size.setter
    def item_size(self, value) -> None:
        pass

    @property
    def end_of_item(self) -> Optional[int]:
        """
        int: The position of the end of respective item. This will be the
        offset for the next element.
        """
        pass

    @property
    def subheader_written(self) -> bool:
        """
        bool: Has this subheader been written?
        """
        pass

    @subheader_written.setter
    def subheader_written(self, value) -> None:
        pass

    @property
    def item_bytes(self) -> Optional[bytes]:
        """
        None|bytes: The item bytes.
        """
        pass

    @item_bytes.setter
    def item_bytes(self, value: Union[bytes, Sequence]) -> None:
        pass

    @property
    def item_written(self) -> bool:
        """
        bool: Has the item been written?
        """
        pass

    @item_written.setter
    def item_written(self, value):
        pass

    def write_subheader(self, file_object: BinaryIO) -> None:
        """
        Write the subheader, at its specified offset, to the file. If writing
        occurs, the file location will be advanced to the end of the subheader
        location.

        Parameters
        ----------
        file_object : BinaryIO
        """

        if self.subheader_written:
            return

        if self.subheader_offset is None:
            return  # nothing to be done

        the_bytes = self.subheader.to_bytes()
        if len(the_bytes) != self._subheader_size:
            raise ValueError(
                'mismatch between the size of the subheader {}\n\t'
                'and the anticipated size of the subheader {}'.format(len(the_bytes), self._subheader_size))

        file_object.seek(self.subheader_offset, os.SEEK_SET)
        file_object.write(the_bytes)
        self.subheader_written = True

    def write_item(self, file_object: BinaryIO) -> None:
        """
        Write the item bytes (if populated), at its specified offset, to the
        file. This requires that the subheader has previously be written. If
        writing occurs, the file location will be advanced to the end of the item
        location.

        Parameters
        ----------
        file_object : BinaryIO

        Returns
        -------
        None
        """

        if self.item_written:
            return

        if self.item_offset is None:
            return  # nothing to be done

        if self.item_bytes is None:
            return  # nothing to be done

        if not self.subheader_written:
            return  # nothing to be done

        file_object.seek(self.item_offset, os.SEEK_SET)
        file_object.write(self.item_bytes)
        self.item_written = True


class ImageSubheaderManager(SubheaderManager):
    item_bytes_required = False
    subheader_type = ImageSegmentHeader

    @property
    def subheader(self) -> ImageSegmentHeader:
        """
        ImageSegmentHeader: The image subheader. Any image mask subheader should
        be populated in the `mask_subheader` property. The size of this will be
        handled independently of the image bytes.
        """
        pass

    @property
    def item_size(self) -> Optional[int]:
        """
        int: The item size.
        """
        pass

    @item_size.setter
    def item_size(self, value):
        pass

    def write_subheader(self, file_object: BinaryIO) -> None:
        if self.subheader_written:
            return

        SubheaderManager.write_subheader(self, file_object)
        if self.subheader.mask_subheader is not None:
            file_object.write(self.subheader.mask_subheader.to_bytes())

    def write_item(self, file_object: BinaryIO) -> None:
        if self.item_written:
            return

        if self.item_offset is None:
            return

        if self.item_bytes is None:
            return

        if not self.subheader_written:
            return

        if self.subheader.mask_subheader is None:
            file_object.seek(self.item_offset, os.SEEK_SET)
        else:
            file_object.seek(
                self.item_offset+self.subheader.mask_subheader.get_bytes_length(), os.SEEK_SET)
        file_object.write(self.item_bytes)
        self.item_written = True


class GraphicsSubheaderManager(SubheaderManager):
    item_bytes_required = True
    subheader_type = GraphicsSegmentHeader

    @property
    def subheader(self) -> GraphicsSegmentHeader:
        pass


class TextSubheaderManager(SubheaderManager):
    item_bytes_required = True
    subheader_type = TextSegmentHeader

    @property
    def subheader(self) -> TextSegmentHeader:
        pass


class DESSubheaderManager(SubheaderManager):
    item_bytes_required = True
    subheader_type = DataExtensionHeader

    @property
    def subheader(self) -> DataExtensionHeader:
        pass


class RESSubheaderManager(SubheaderManager):
    item_bytes_required = True
    subheader_type = DataExtensionHeader

    @property
    def subheader(self) -> ReservedExtensionHeader:
        pass


class NITFWritingDetails(object):
    """
    Manager for all the NITF subheader information.

    Note that doing anything which modified the size of the headers after
    initialization (i.e. adding TREs) will not be reflected

    Introduced in version 1.3.0.
    """
    __slots__ = (
        '_header', '_header_size', '_header_written', '_image_managers',
        '_graphics_managers', '_text_managers', '_des_managers', '_res_managers',
        '_image_segment_collections', '_image_segment_coordinates', '_collections_clevel')

    def __init__(
            self,
            header: NITFHeader,
            image_managers: Optional[Tuple[ImageSubheaderManager, ...]] = None,
            image_segment_collections: Optional[Tuple[Tuple[int, ...], ...]] = None,
            image_segment_coordinates: Optional[Tuple[Tuple[Tuple[int, ...], ...], ...]] = None,
            graphics_managers: Optional[Tuple[GraphicsSubheaderManager, ...]] = None,
            text_managers: Optional[Tuple[TextSubheaderManager, ...]] = None,
            des_managers: Optional[Tuple[DESSubheaderManager, ...]] = None,
            res_managers: Optional[Tuple[RESSubheaderManager, ...]] = None):
        """

        Parameters
        ----------
        header : NITFHeader
        image_managers : Optional[Tuple[ImageSubheaderManager, ...]]
            Should be provided, unless the desire is to write NITF without images
        image_segment_collections: Optional[Tuple[Tuple[int, ...], ...]]
            Presence contingent on presence of image_managers
        image_segment_coordinates: Optional[Tuple[Tuple[Tuple[int, ...], ...], ...]]
            Contingent on image_managers. This will be inferred if not provided,
            and validated if provided.
        graphics_managers: Optional[Tuple[GraphicsSubheaderManager, ...]]
        text_managers: Optional[Tuple[TextSubheaderManager, ...]]
        des_managers: Optional[Tuple[DESSubheaderManager, ...]]
        res_managers: Optional[Tuple[RESSubheaderManager, ...]]
        """

        self._collections_clevel = None
        self._header = None
        self._header_written = False
        self._image_managers = None
        self._image_segment_collections = None
        self._image_segment_coordinates = None
        self._graphics_managers = None
        self._text_managers = None
        self._des_managers = None
        self._res_managers = None

        self.header = header
        self.image_managers = image_managers
        self.image_segment_collections = image_segment_collections
        self.image_segment_coordinates = image_segment_coordinates
        self.graphics_managers = graphics_managers
        self.text_managers = text_managers
        self.des_managers = des_managers
        self.res_managers = res_managers

        # set nominal size arrays (for header size purposes), to be corrected later
        self.set_all_sizes(require=False)
        self._header_size = header.get_bytes_length()  # type: int

    @property
    def header(self) -> NITFHeader:
        """
        NITFHeader: The main NITF header. Note that doing anything that changes
        the size of that header (i.e. adding TREs) after initialization will
        result in a broken state.
        """
        pass

    @header.setter
    def header(self, value):
        pass

    @property
    def image_managers(self) -> Optional[Tuple[ImageSubheaderManager, ...]]:
        pass

    @image_managers.setter
    def image_managers(self, value):
        pass

    @property
    def image_segment_collections(self) -> Tuple[Tuple[int, ...]]:
        """
        The definition for how image segments are grouped together to form the
        aggregate images.

        Each entry corresponds to a single aggregate image, and the entry defines
        the image segment indices which are combined to make up the aggregate image.

        This must be an ordered partitioning of the set `(0, ..., len(image_managers)-1)`.

        Returns
        -------
        Tuple[Tuple[int, ...]]
        """
        pass

    @image_segment_collections.setter
    def image_segment_collections(self, value):
        pass

    @property
    def image_segment_coordinates(self) -> Tuple[Tuple[Tuple[int, ...], ...], ...]:
        """
        The image bounds for the segment collection. This is associated with the
        `image_segment_collection` property.

        Entry `image_segment_coordinates[i]` is associated with the ith aggregate
        image. We have `image_segment_coordinates[i]` is a tuple of tuples of the
        form
        `((row_start, row_end, col_start, col_end)_j,
          (row_start, row_end, col_start, col_end)_{j+1}, ...)`.

        This indicates that the first image segment associated with
        ith aggregate image is at index `j` covering the portion of the aggregate
        image determined by bounds `(row_start, row_end, col_start, col_end)_j`,
        the second image segment is at index `j+1` covering the portion of the
        aggregate determined by bounds `(row_start, row_end, col_start, col_end)_{j+1}`,
        and so on.

        Returns
        -------
        Tuple[Tuple[Tuple[int, ...], ...], ...]:
        """
        pass

    @image_segment_coordinates.setter
    def image_segment_coordinates(self, value):
        pass

    @property
    def graphics_managers(self) -> Optional[Tuple[GraphicsSubheaderManager, ...]]:
        pass

    @graphics_managers.setter
    def graphics_managers(self, value):
        pass

    @property
    def text_managers(self) -> Optional[Tuple[TextSubheaderManager, ...]]:
        pass

    @text_managers.setter
    def text_managers(self, value):
        pass

    @property
    def des_managers(self) -> Optional[Tuple[DESSubheaderManager, ...]]:
        pass

    @des_managers.setter
    def des_managers(self, value):
        pass

    @property
    def res_managers(self) -> Optional[Tuple[RESSubheaderManager, ...]]:
        pass

    @res_managers.setter
    def res_managers(self, value):
        pass

    def _get_sizes(
            self,
            managers: Optional[Sequence[SubheaderManager]],
            name: str,
            require: bool = False) -> Tuple[Optional[numpy.ndarray], Optional[numpy.ndarray]]:
        pass

    def _write_items(self, managers: Optional[Sequence[SubheaderManager]], file_object: BinaryIO) -> None:
        if managers is None:
            return
        for index, entry in enumerate(managers):
            entry.write_subheader(file_object)
            entry.write_item(file_object)

    def _verify_item_written(self, managers: Optional[Sequence[SubheaderManager]], name: str) -> None:
        if managers is None:
            return

        for index, entry in enumerate(managers):
            if not entry.subheader_written:
                logger.error('{} subheader at index {} not written'.format(name, index))
            if not entry.item_written:
                logger.error('{} data at index {} not written'.format(name, index))

    def _get_image_sizes(self, require: bool = False) -> ImageSegmentsType:
        """
        Gets the image sizes details for the NITF header.

        Returns
        -------
        ImageSegmentsType
        """
        pass

    def _get_graphics_sizes(self, require: bool = False) -> GraphicsSegmentsType:
        """
        Gets the graphics sizes details for the NITF header.

        Parameters
        ----------
        require : bool
            Require all sizes to be set?

        Returns
        -------
        ImageSegmentsType
        """
        pass

    def _get_text_sizes(self, require: bool = False) -> TextSegmentsType:
        """
        Gets the text sizes details for the NITF header.

        Returns
        -------
        TextSegmentsType
        """
        pass

    def _get_des_sizes(self, require: bool = False) -> DataExtensionsType:
        """
        Gets the image sizes details for the NITF header.

        Returns
        -------
        ImageSegmentsType
        """
        pass

    def _get_res_sizes(self, require: bool = False) -> ReservedExtensionsType:
        """
        Gets the image sizes details for the NITF header.

        Returns
        -------
        ImageSegmentsType
        """
        pass

    def set_first_image_offset(self) -> None:
        """
        Sets the first image offset from the header length.

        Returns
        -------
        None
        """
        pass

    def verify_images_have_no_compression(self) -> bool:
        """
        Verify that there is no compression set for every image manager. That is,
        we are going to directly write a NITF file.

        Returns
        -------
        bool
        """
        pass

    def set_all_sizes(self, require: bool = False) -> None:
        """
        This sets the nominal size information in the nitf header, and optionally
        verifies that all the item_size values are set.

        Parameters
        ----------
        require : bool
            Require all sizes to be set? `0` will be used as a placeholder for
            header information population.

        Returns
        -------
        None
        """
        pass

    def verify_all_offsets(self, require: bool = False) -> bool:
        """
        This sets and/or verifies all offsets.

        Parameters
        ----------
        require : bool
            Require all offsets to be set?

        Returns
        -------
        bool
        """

        last_offset = self._header_size
        if self.image_managers is not None:
            for index, entry in enumerate(self.image_managers):
                if entry.subheader_offset is None:
                    entry.subheader_offset = last_offset
                elif entry.subheader_offset != last_offset:
                    raise ValueError(
                        'image manager at index {} has subheader offset which does not agree\n\t'
                        'with the end of the previous element'.format(index))
                if entry.item_size is None or entry.item_size == 0:
                    if require:
                        raise ValueError(
                            'image manager at index {} has item_size unpopulated or populated as 0'.format(index))
                    else:
                        return False
                last_offset = entry.end_of_item

        if self.graphics_managers is not None:
            for index, entry in enumerate(self.graphics_managers):
                if entry.subheader_offset is None:
                    entry.subheader_offset = last_offset
                elif entry.subheader_offset != last_offset:
                    raise ValueError(
                        'graphics manager at index {} has subheader offset which does not agree\n\t'
                        'with the end of the previous element'.format(index))
                if entry.item_size is None or entry.item_size == 0:
                    if require:
                        raise ValueError(
                            'graphics manager at index {} has item_size unpopulated or populated as 0'.format(index))
                    else:
                        return False
                last_offset = entry.end_of_item

        if self.text_managers is not None:
            for index, entry in enumerate(self.text_managers):
                if entry.subheader_offset is None:
                    entry.subheader_offset = last_offset
                elif entry.subheader_offset != last_offset:
                    raise ValueError(
                        'text manager at index {} has subheader offset which does not agree\n\t'
                        'with the end of the previous element'.format(index))
                if entry.item_size is None or entry.item_size == 0:
                    if require:
                        raise ValueError(
                            'text manager at index {} has item_size unpopulated or populated as 0'.format(index))
                    else:
                        return False
                last_offset = entry.end_of_item

        if self.des_managers is not None:
            for index, entry in enumerate(self.des_managers):
                if entry.subheader_offset is None:
                    entry.subheader_offset = last_offset
                elif entry.subheader_offset != last_offset:
                    raise ValueError(
                        'des manager at index {} has subheader offset which does not agree\n\t'
                        'with the end of the previous element'.format(index))
                if entry.item_size is None or entry.item_size == 0:
                    if require:
                        raise ValueError(
                            'des manager at index {} has item_size unpopulated or populated as 0'.format(index))
                    else:
                        return False
                last_offset = entry.end_of_item

        if self.res_managers is not None:
            for index, entry in enumerate(self.res_managers):
                if entry.subheader_offset is None:
                    entry.subheader_offset = last_offset
                elif entry.subheader_offset != last_offset:
                    raise ValueError(
                        'res manager at index {} has subheader offset which does not agree\n\t'
                        'with the end of the previous element'.format(index))
                if entry.item_size is None or entry.item_size == 0:
                    if require:
                        raise ValueError(
                            'res manager at index {} has item_size unpopulated or populated as 0'.format(index))
                    else:
                        return False
                last_offset = entry.end_of_item
        self.header.FL = last_offset
        return True

    def set_header_clevel(self) -> None:
        """
        Sets the appropriate CLEVEL. This requires that header.FL (file size) has
        been previously populated correctly (using :meth:`verify_all_offsets`).

        Returns
        -------
        None
        """

        file_size = self.header.FL
        if file_size < 50 * (1024 ** 2):
            mem_clevel = 3
        elif file_size < (1024 ** 3):
            mem_clevel = 5
        elif file_size < 2 * (1024 ** 3):
            mem_clevel = 6
        elif file_size < 10 * (1024 ** 3):
            mem_clevel = 7
        else:
            mem_clevel = 9

        self.header.CLEVEL = mem_clevel if self._collections_clevel is None else \
            max(mem_clevel, max(self._collections_clevel))

    def write_header(self, file_object: BinaryIO, overwrite: bool = False) -> None:
        """
        Write the main NITF header.

        Parameters
        ----------
        file_object : BinaryIO
        overwrite : bool
            Overwrite, if previously written?

        Returns
        -------
        None
        """

        if self._header_written and not overwrite:
            return
        the_bytes = self.header.to_bytes()
        if len(the_bytes) != self._header_size:
            raise ValueError(
                'The anticipated header length {}\n\t'
                'does not match the actual header length {}'.format(self._header_size, len(the_bytes)))
        self.set_header_clevel()
        file_object.seek(0, os.SEEK_SET)
        file_object.write(the_bytes)
        self._header_written = True

    def write_all_populated_items(self, file_object: BinaryIO) -> None:
        """
        Write everything populated. This assumes that the header will start at the
        beginning (position 0) of the file-like object.

        Parameters
        ----------
        file_object : BinaryIO

        Returns
        -------
        None
        """

        self.write_header(file_object, overwrite=False)
        self._write_items(self.image_managers, file_object)
        self._write_items(self.graphics_managers, file_object)
        self._write_items(self.text_managers, file_object)
        self._write_items(self.des_managers, file_object)
        self._write_items(self.res_managers, file_object)

    def verify_all_written(self) -> None:
        if not self._header_written:
            logger.error('NITF header not written')

        self._verify_item_written(self.image_managers, 'image')
        self._verify_item_written(self.graphics_managers, 'graphics')
        self._verify_item_written(self.text_managers, 'text')
        self._verify_item_written(self.des_managers, 'DES')
        self._verify_item_written(self.res_managers, 'RES')


#############
# An array based (for only uncompressed images) nitf 2.1 writer

class NITFWriter(BaseWriter):
    __slots__ = (
        '_file_object', '_file_name', '_in_memory',
        '_nitf_writing_details', '_image_segment_data_segments', '_close_after')

    def __init__(
            self,
            file_object: Union[str, BinaryIO],
            writing_details: NITFWritingDetails,
            check_existence: bool = True,
            in_memory: bool = None):
        """

        Parameters
        ----------
        file_object : str|BinaryIO
        writing_details : NITFWritingDetails
        check_existence : bool
            Should we check if the given file already exists?
        in_memory : bool
            If True force in-memory writing, if False force file writing.

        Raises
        ------
        SarpyIOError
            If the given `file_name` already exists
        """

        self._nitf_writing_details = None
        self._image_segment_data_segments = []  # type: List[DataSegment]
        self._close_after = False

        if isinstance(file_object, str):
            if check_existence and os.path.exists(file_object):
                raise SarpyIOError(
                    'Given file {} already exists, and a new NITF file cannot be created here.'.format(file_object))
            file_object = open(file_object, 'wb')
            self._close_after = True

        if not is_file_like(file_object):
            raise ValueError('file_object requires a file path or BinaryIO object')

        self._file_object = file_object

        if is_real_file(file_object):
            self._file_name = file_object.name
            self._in_memory = False
        else:
            self._file_name = None
            self._in_memory = True

        if in_memory is not None:
            self._in_memory = in_memory

        self.nitf_writing_details = writing_details

        if not self.nitf_writing_details.verify_images_have_no_compression():
            raise ValueError(
                'Some image segments indicate compression in the image managers of the nitf_writing_details')

        # set the image offset
        self.nitf_writing_details.set_first_image_offset()

        self._verify_image_segments()
        self.verify_collection_compliance()

        data_segments = self.get_data_segments()

        self.nitf_writing_details.set_all_sizes(require=True)  # NB: while no compression supported...
        if not self._in_memory:
            self.nitf_writing_details.write_all_populated_items(self._file_object)
        BaseWriter.__init__(self, data_segments)

    @property
    def nitf_writing_details(self) -> NITFWritingDetails:
        """
        NITFWritingDetails: The NITF subheader details.
        """
        pass

    @nitf_writing_details.setter
    def nitf_writing_details(self, value):
        pass

    @property
    def image_managers(self) -> Tuple[ImageSubheaderManager, ...]:
        pass

    def _set_image_size(self, image_segment_index: int, item_size: int) -> None:
        """
        Sets the image size information. This should be without consideration
        for the presence of an image mask, which is handled by with the image
        subheader (if present).

        Parameters
        ----------
        image_segment_index : int
        item_size : int
        """
        pass

    @property
    def image_segment_collections(self) -> Tuple[Tuple[int, ...]]:
        """
        The definition for how image segments are grouped together to form the
        aggregate image.

        Each entry corresponds to a single output image, and the entry defines
        the image segment indices which are combined to make up the output image.

        Returns
        -------
        Tuple[Tuple[int, ...]]
        """
        pass

    def get_image_header(self, index: int) -> ImageSegmentHeader:
        """
        Gets the image subheader at the specified index.

        Parameters
        ----------
        index : int

        Returns
        -------
        ImageSegmentHeader
        """
        pass

    # noinspection PyMethodMayBeStatic
    def _check_image_segment_for_compliance(
            self,
            index: int,
            img_header: ImageSegmentHeader) -> None:
        """
        Checks whether the image segment can be (or should be) opened.

        Parameters
        ----------
        index : int
            The image segment index (for logging)
        img_header : ImageSegmentHeader
            The image segment header
        """
        pass

    def _verify_image_segments(self) -> None:
        pass

    def _construct_block_bounds(self, image_segment_index: int) -> List[Tuple[int, int, int, int]]:
        pass

    def _get_mask_details(
            self,
            image_segment_index: int) -> Tuple[Optional[numpy.ndarray], int, int]:
        """
        Gets the mask offset details.

        Parameters
        ----------
        image_segment_index : int

        Returns
        -------
        mask_offsets : Optional[numpy.ndarray]
            The mask byte offset from the end of the mask subheader definition.
            If `IMODE = S`, then this is two-dimensional, otherwise it is one
            dimensional
        exclude_value : int
            The offset value for excluded block, should always be `0xFFFFFFFF`.
        additional_offset : int
            The additional offset from the beginning of the image segment data,
            necessary to account for the presence of mask subheader.
        """
        pass

    def _get_dtypes(
            self,
            image_segment_index: int) -> Tuple[numpy.dtype, numpy.dtype, int, Optional[str], Optional[numpy.ndarray]]:
        pass

    # noinspection PyMethodMayBeStatic, PyUnusedLocal
    def get_format_function(
            self,
            raw_dtype: numpy.dtype,
            complex_order: Optional[str] = None,
            lut: Optional[numpy.ndarray] = None,
            band_dimension: int = -1,
            image_segment_index: Optional[int] = None,
            **kwargs) -> Optional[FormatFunction]:
        pass

    def _verify_image_segment_compatibility(self, index0: int, index1: int) -> bool:
        pass

    def verify_collection_compliance(self) -> None:
        """
        Verify that image segments collections are compatible.

        Raises
        -------
        ValueError
        """
        pass

    def _get_collection_element_coordinate_limits(self, collection_index: int) -> Tuple[Tuple[int, ...], ...]:
        """
        For the given image segment collection, as defined in the
        `image_segment_collections` property value, get the relative coordinate
        scheme of the form `[[start_row, end_row, start_column, end_column]]`.

        This relies on inspection of `IALVL` and `ILOC` values for this
        collection of image segments.

        Parameters
        ----------
        collection_index : int
            The index into the `image_segment_collection` list.

        Returns
        -------
        block_definition: Tuple[Tuple[int, ...], ...]
            of the form `((start_row, end_row, start_column, end_column))`.
        """
        pass

    def _handle_no_compression(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        # NB: this should definitely set the image size in the manager.

        pass

    def _create_data_segment_from_imode_b(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        pass

    def _create_data_segment_from_imode_p(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        pass

    def _create_data_segment_from_imode_r(self, image_segment_index: int, apply_format: bool) -> DataSegment:
        pass

    def create_data_segment_for_image_segment(
            self,
            image_segment_index: int,
            apply_format: bool) -> DataSegment:
        """
        Creates the data segment for the given image segment.

        For consistency of simple usage, any bands will be presented in the
        final formatted/output dimension, regardless of the value of `apply_format`
        or `IMODE`.

        For compressed image segments, the `IMODE` has been
        abstracted away, and the data segment will be consistent with the raw
        shape having bands in the final dimension (analogous to `IMODE=P`).

        Note that this also stores a reference to the produced data segment in
        the `_image_segment_data_segments` list.

        This will raise an exception if not performed in the order presented in
        the writing manager.

        Parameters
        ----------
        image_segment_index : int
        apply_format : bool
            Leave data raw (False), or apply format function and global
            `reverse_axes` and `transpose_axes` values?

        Returns
        -------
        DataSegment
        """
        pass

    def create_data_segment_for_collection_element(self, collection_index: int) -> DataSegment:
        """
        Creates the data segment overarching the given segment collection.

        Parameters
        ----------
        collection_index : int

        Returns
        -------
        DataSegment
        """
        pass

    def get_data_segments(self) -> List[DataSegment]:
        """
        Gets a data segment for each of these image segment collection.

        Returns
        -------
        List[DataSegment]
        """
        pass

    def flush(self, force: bool = False) -> None:
        self._validate_closed()

        BaseWriter.flush(self, force=force)

        try:
            if self._in_memory:
                if self._image_segment_data_segments is not None:
                    for index, entry in enumerate(self._image_segment_data_segments):
                        manager = self.nitf_writing_details.image_managers[index]
                        if manager.item_written:
                            continue
                        if manager.item_bytes is not None:
                            continue
                        if force or entry.check_fully_written(warn=force):
                            manager.item_bytes = entry.get_raw_bytes(warn=False)

            check = self.nitf_writing_details.verify_all_offsets(require=False)
            if check:
                self.nitf_writing_details.write_header(self._file_object, overwrite=True)
            self.nitf_writing_details.write_all_populated_items(self._file_object)
        except AttributeError:
            return

    def close(self) -> None:
        BaseWriter.close(self)  # NB: flush called here
        try:
            if self.nitf_writing_details is not None:
                self.nitf_writing_details.verify_all_written()
        except AttributeError:
            pass

        self._nitf_writing_details = None
        self._image_segment_data_segments = None
        if self._close_after:
            self._close_after = False
            # noinspection PyBroadException
            try:
                self._file_object.close()
            except Exception:
                pass
