"""
Module for reading and writing CRSD version 1.0 files
"""

__classification__ = "UNCLASSIFIED"
__author__ = ("Thomas McCullough", "Michael Stewart, Valyrie")


import logging
import numpy
import os
from collections import OrderedDict
from typing      import Union, Tuple, List, Sequence, Dict, BinaryIO, Optional
from deprecated import deprecated

from sarpy.io.general.base          import BaseReader, SarpyIOError
from sarpy.io.general.data_segment  import DataSegment, NumpyMemmapSegment
from sarpy.io.general.slice_parsing import verify_subscript, verify_slice
from sarpy.io.general.utils         import is_file_like
from sarpy.io.phase_history.cphd    import CPHDWritingDetails, CPHDWriter1, \
    AmpScalingFunction
from sarpy.io.received.crsd1_elements.CRSD import CRSDType, CRSDHeader, \
    CRSD_SECTION_TERMINATOR
from sarpy.io.received.base         import CRSDTypeReader
from sarpy.io.received.crsd_schema  import get_namespace, get_default_tuple

logger = logging.getLogger(__name__)

_unhandled_version_text = 'Got unhandled CRSD version number `{}`'
_missing_channel_identifier_text = 'Cannot find CRSD channel for identifier `{}`'
_index_range_text = 'index must be in the range `[0, {})`'


#########
# Object for parsing CRSD elements
@deprecated("sarpy's CRSD implementation is deprecated. Please use SARKit.")
class CRSDDetails(object):
    """
    The basic CRSD element parser.
    """

    __slots__ = (
        '_file_name', '_file_object', '_close_after', '_crsd_version', '_crsd_header', '_crsd_meta')

    def __init__(self, file_object: Union[str, BinaryIO]):
        """

        Parameters
        ----------
        file_object : str|BinaryIO
            The path to or file like object referencing the CRSD file.
        """

        self._crsd_version = None
        self._crsd_header = None
        self._crsd_meta = None
        self._close_after = False

        if isinstance(file_object, str):
            if not os.path.exists(file_object) or not os.path.isfile(file_object):
                raise SarpyIOError('path {} does not exist or is not a file'.format(file_object))
            self._file_name = file_object
            self._file_object = open(file_object, 'rb')
            self._close_after = True
        elif is_file_like(file_object):
            self._file_object = file_object
            if hasattr(file_object, 'name') and isinstance(file_object.name, str):
                self._file_name = file_object.name
            else:
                self._file_name = '<file like object>'
            self._close_after = False
        else:
            raise TypeError('Got unsupported input type {}'.format(type(file_object)))

        self._file_object.seek(0, os.SEEK_SET)
        head_bytes = self._file_object.read(10)
        if not isinstance(head_bytes, bytes):
            raise ValueError('Input file like object not open in bytes mode.')
        if not head_bytes.startswith(b'CRSD'):
            raise SarpyIOError('File {} does not appear to be a CRSD file.'.format(self.file_name))

        self._extract_version()
        self._extract_header()
        self._extract_crsd()

    @property
    def file_name(self) -> str:
        """
        str: The CRSD filename.
        """
        pass

    @property
    def file_object(self) -> BinaryIO:
        """
        BinaryIO: The binary file object
        """
        pass

    @property
    def crsd_version(self) -> str:
        """
        str: The CRSD version.
        """
        pass

    @property
    def crsd_header(self) -> CRSDHeader:
        """
        CRSDHeader: The CRSD header object
        """
        pass

    @property
    def crsd_meta(self) -> CRSDType:
        """
        CRSDType: The CRSD structure, which is version dependent.
        """
        pass

    def _extract_version(self) -> None:
        """
        Extract the version number from the file. This will advance the file
        object to the end of the initial header line.
        """
        pass

    def _extract_header(self) -> None:
        """
        Extract the header from the file. The file object is assumed to be advanced
        to the header location. This will advance to the file object to the end of
        the header section.
        """
        pass

    def _extract_crsd(self) -> None:
        """
        Extract and interpret the CRSD structure from the file.
        """
        pass

    def get_crsd_bytes(self) -> bytes:
        """
        Extract the (uninterpreted) bytes representation of the CRSD structure.

        Returns
        -------
        bytes
        """
        pass

    def __del__(self):
        if self._close_after:
            self._close_after = False
            # noinspection PyBroadException
            try:
                self._file_object.close()
            except Exception:
                pass

@deprecated("sarpy's CRSD implementation is deprecated. Please use SARKit.")
def _validate_crsd_details(
        crsd_details: Union[str, CRSDDetails],
        version: Union[None, str, Sequence[str]] = None) -> CRSDDetails:
    """
    Validate the input argument.

    Parameters
    ----------
    crsd_details : str|CRSDDetails
    version : None|str|Sequence[str]

    Returns
    -------
    CRSDDetails
    """
    pass

@deprecated("sarpy's CRSD implementation is deprecated. Please use SARKit.")
class CRSDReader(CRSDTypeReader):
    """
    The Abstract CRSD reader instance, which just selects the proper CRSD reader
    class based on the CRSD version. Note that there is no __init__ method for
    this class, and it would be skipped regardless. Ensure that you make a direct
    call to the BaseReader.__init__() method when extending this class.

    **Updated in version 1.3.0** for reading changes.
    """

    __slots__ = ('_crsd_details', )

    def __new__(cls, *args, **kwargs):
        if len(args) == 0:
            raise ValueError(
                'The first argument of the constructor is required to be a file_path '
                'or CRSDDetails instance.')
        if is_file_like(args[0]):
            raise ValueError('File like object input not supported for CRSD reading at this time.')
        crsd_details = _validate_crsd_details(args[0])

        if crsd_details.crsd_version.startswith('1.'):
            return object.__new__(CRSDReader1)
        else:
            raise ValueError('Got unhandled CRSD version {}'.format(crsd_details.crsd_version))

    @property
    def crsd_details(self) -> CRSDDetails:
        """
        CRSDDetails: The crsd details object.
        """
        pass

    @property
    def crsd_version(self) -> str:
        """
        str: The CRSD version.
        """
        pass

    @property
    def crsd_header(self) -> CRSDHeader:
        """
        CRSDHeader: The CRSD header object
        """
        pass

    @property
    def file_name(self) -> str:
        pass

    def read_support_array(self,
                           index: Union[int, str],
                           *ranges: Sequence[Union[None, int, Tuple[int, ...], slice]]) -> numpy.ndarray:
        raise NotImplementedError

    def read_support_block(self) -> Dict[str, numpy.ndarray]:
        raise NotImplementedError

    def read_pvp_variable(
            self,
            variable: str,
            index: Union[int, str],
            the_range: Union[None, int, Tuple[int, ...], slice] = None) -> Optional[numpy.ndarray]:
        raise NotImplementedError

    def read_pvp_array(
            self,
            index: Union[int, str],
            the_range: Union[None, int, Tuple[int, ...], slice] = None) -> numpy.ndarray:
        raise NotImplementedError

    def read_pvp_block(self) -> Dict[str, numpy.ndarray]:
        raise NotImplementedError

    def read_signal_block(self) -> Dict[str, numpy.ndarray]:
        raise NotImplementedError

    def read_signal_block_raw(self) -> Dict[str, numpy.ndarray]:
        raise NotImplementedError

    def close(self):
        CRSDTypeReader.close(self)
        if hasattr(self, '_crsd_details'):
            if hasattr(self._crsd_details, 'close'):
                self._crsd_details.close()
            del self._crsd_details

@deprecated("sarpy's CRSD implementation is deprecated. Please use SARKit.")
class CRSDReader1(CRSDReader):
    """
    The CRSD version 1 reader.

    **Updated in version 1.3.0** for reading changes.
    """
    _allowed_versions = ('1.0', )

    def __new__(cls, *args, **kwargs):
        # we must override here, to avoid recursion with
        # the CRSDReader parent
        return object.__new__(cls)

    def __init__(
            self,
            crsd_details: Union[str, CRSDDetails]):
        """

        Parameters
        ----------
        crsd_details : str|CRSDDetails
        """

        self._channel_map = None  # type: Union[None, Dict[str, int]]
        self._support_array_map = None  # type: Union[None, Dict[str, int]]
        self._pvp_memmap = None  # type: Union[None, Dict[str, numpy.ndarray]]
        self._support_array_memmap = None  # type: Union[None, Dict[str, numpy.ndarray]]
        self._crsd_details = _validate_crsd_details(crsd_details, version=self._allowed_versions)

        CRSDTypeReader.__init__(self, None, self._crsd_details.crsd_meta)
        # set data segments after setting up the pvp information, because
        #   we need the AmpSf to set up the format function for the data segment
        self._create_pvp_memmaps()
        self._create_support_array_memmaps()

        data_segments = self._create_data_segments()
        BaseReader.__init__(self, data_segments, reader_type='CRSD')

    @property
    def crsd_meta(self) -> CRSDType:
        """
        CRSDType: the crsd meta_data.
        """
        pass

    @property
    def crsd_header(self) -> CRSDHeader:
        """
        CRSDHeader: The CRSD header object.
        """
        pass

    def _create_data_segments(self) -> List[DataSegment]:
        """
        Helper method for creating the various signal data segments.

        Returns
        -------
        List[DataSegment]
        """
        pass

    def _create_pvp_memmaps(self) -> None:
        """
        Helper method which creates the pvp mem_maps.

        Returns
        -------
        None
        """
        pass

    def _create_support_array_memmaps(self) -> None:
        """
        Helper method which creates the support array mem_maps.

        Returns
        -------
        None
        """
        pass

    def _validate_index(self, index: Union[int, str]) -> int:
        """
        Get corresponding integer index for CRSD channel.

        Parameters
        ----------
        index : int|str

        Returns
        -------
        int
        """

        crsd_meta = self.crsd_details.crsd_meta

        if isinstance(index, str):
            if index in self._channel_map:
                return self._channel_map[index]
            else:
                raise KeyError(_missing_channel_identifier_text.format(index))
        else:
            int_index = int(index)
            if not (0 <= int_index < crsd_meta.Data.NumCRSDChannels):
                raise ValueError(_index_range_text.format(crsd_meta.Data.NumCRSDChannels))
            return int_index

    def _validate_index_key(self, index: Union[int, str]) -> str:
        """
        Gets the corresponding identifier for the CPHD channel.

        Parameters
        ----------
        index : int|str

        Returns
        -------
        str
        """

        crsd_meta = self.crsd_details.crsd_meta

        if isinstance(index, str):
            if index in self._channel_map:
                return index
            else:
                raise KeyError(_missing_channel_identifier_text.format(index))
        else:
            int_index = int(index)
            if not (0 <= int_index < crsd_meta.Data.NumCRSDChannels):
                raise ValueError(_index_range_text.format(crsd_meta.Data.NumCRSDChannels))
            return crsd_meta.Data.Channels[int_index].Identifier

    def read_support_array(
            self,
            index: Union[int, str],
            *ranges) -> numpy.ndarray:
        # find the support array identifier
        pass

    def read_support_block(self) -> Dict:
        pass

    def read_pvp_variable(self, variable, index, the_range=None):
        pass

    def read_pvp_array(self, index, the_range=None):
        index_key = self._validate_index_key(index)
        the_memmap = self._pvp_memmap[index_key]
        the_slice = verify_slice(the_range, the_memmap.shape[0])
        return numpy.copy(the_memmap[the_slice])

    def read_pvp_block(self) -> Dict[str, numpy.ndarray]:
        pass

    def read_signal_block(self) -> Dict[str, numpy.ndarray]:
        pass

    def read_signal_block_raw(self) -> Dict[str, numpy.ndarray]:
        pass

    def read_chip(self,
             *ranges: Sequence[Union[None, int, Tuple[int, ...], slice]],
             index: Union[int, str] = 0,
             squeeze: bool = True) -> numpy.ndarray:
        """
        This is identical to :meth:`read`, and presented for backwards compatibility.

        Parameters
        ----------
        ranges : Sequence[Union[None, int, Tuple[int, ...], slice]]
        index : int|str
        squeeze : bool

        Returns
        -------
        numpy.ndarray

        See Also
        --------
        :meth:`read`.
        """
        pass

    def read(self,
             *ranges: Sequence[Union[None, int, Tuple[int, ...], slice]],
             index: Union[int, str] = 0,
             squeeze: bool = True) -> numpy.ndarray:
        """
        Read formatted data from the given data segment. Note this is an alias to the
        :meth:`__call__` called as
        :code:`reader(*ranges, index=index, raw=False, squeeze=squeeze)`.

        Parameters
        ----------
        ranges : Sequence[Union[None, int, Tuple[int, ...], slice]]
            The slice definition appropriate for `data_segment[index].read()` usage.
        index : int|str
            The data_segment index or channel identifier.
        squeeze : bool
            Squeeze length 1 dimensions out of the shape of the return array?

        Returns
        -------
        numpy.ndarray

        See Also
        --------
        See :meth:`sarpy.io.general.data_segment.DataSegment.read`.
        """

        return self.__call__(*ranges, index=index, raw=False, squeeze=squeeze)

    def read_raw(self,
                 *ranges: Sequence[Union[None, int, Tuple[int, ...], slice]],
                 index: Union[int, str] = 0,
                 squeeze: bool = True) -> numpy.ndarray:
        """
        Read raw data from the given data segment. Note this is an alias to the
        :meth:`__call__` called as
        :code:`reader(*ranges, index=index, raw=True, squeeze=squeeze)`.

        Parameters
        ----------
        ranges : Sequence[Union[None, int, Tuple[int, ...], slice]]
            The slice definition appropriate for `data_segment[index].read()` usage.
        index : int|str
            The data_segment index or crsd channel identifier.
        squeeze : bool
            Squeeze length 1 dimensions out of the shape of the return array?

        Returns
        -------
        numpy.ndarray

        See Also
        --------
        See :meth:`sarpy.io.general.data_segment.DataSegment.read_raw`.
        """

        return self.__call__(*ranges, index=index, raw=True, squeeze=squeeze)

    def __call__(self,
                 *ranges: Sequence[Union[None, int, slice]],
                 index: int = 0,
                 raw: bool = False,
                 squeeze: bool = True) -> numpy.ndarray:
        index = self._validate_index(index)
        return BaseReader.__call__(self, *ranges, index=index, raw=raw, squeeze=squeeze)

@deprecated("sarpy's CRSD implementation is deprecated. Please use SARKit.")
def is_a(file_name: str) -> Optional[CRSDReader]:
    """
    Tests whether a given file_name corresponds to a CRSD file. Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str
        the file_name to check

    Returns
    -------
    CRSDReader1|None
        Appropriate `CRSDReader` instance if CRSD file, `None` otherwise
    """
    pass


###########
# writer
@deprecated("sarpy's CRSD implementation is deprecated. Please use SARKit.")
class CRSDWritingDetails(CPHDWritingDetails):

    @property
    def header(self) -> CRSDHeader:
        pass

    def _set_header(self, check_older_version: bool):
        pass

    @property
    def meta(self) -> CRSDType:
        """
        CPSDType: The metadata
        """
        pass

    @meta.setter
    def meta(self, value: CRSDType):
        pass

    def write_header(
            self,
            file_object: BinaryIO,
            overwrite: bool = False) -> None:
        """
        Write the header.The file object will be advanced to the end of the
        block, if writing occurs.

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

        file_object.write(self.header.to_string().encode())
        file_object.write(CRSD_SECTION_TERMINATOR)
        # write xml
        file_object.seek(self.header.XML_BLOCK_BYTE_OFFSET, os.SEEK_SET)
        file_object.write(self.meta.to_xml_bytes(urn=get_namespace(self.use_version)))
        file_object.write(CRSD_SECTION_TERMINATOR)
        self._header_written = True

@deprecated("sarpy's CRSD implementation is deprecated. Please use SARKit.")
class CRSDWriter1(CPHDWriter1):
    """
    The CRSD version 1 writer.

    **Updated in version 1.3.0** for writing changes.
    """
    _writing_details_type = CRSDWritingDetails

    def __init__(
            self,
            file_object: Union[str, BinaryIO],
            meta: Optional[CRSDType] = None,
            writing_details: Optional[CRSDWritingDetails] = None,
            check_existence: bool = True):
        """

        Parameters
        ----------
        file_object : str|BinaryIO
        meta : None|CRSDType
        writing_details : None|CRSDWritingDetails
        check_existence : bool
            Should we check if the given file already exists, and raises an exception if so?
        """

        CPHDWriter1.__init__(
            self, file_object, meta=meta, writing_details=writing_details,
            check_existence=check_existence)

    @property
    def writing_details(self) -> CRSDWritingDetails:
        pass

    @writing_details.setter
    def writing_details(self, value: CRSDWritingDetails):
        pass

    @property
    def file_name(self) -> Optional[str]:
        pass

    @property
    def meta(self) -> CRSDType:
        """
        CRSDType: The metadata
        """
        pass

