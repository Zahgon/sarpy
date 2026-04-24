"""
Module for reading and writing CPHD files. Support reading CPHD version 0.3 and 1
and writing version 1.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import logging
import os
from typing import Union, List, Tuple, Dict, BinaryIO, Optional, Sequence
from collections import OrderedDict
import numbers

import numpy

from sarpy.io.general.utils import is_file_like, is_real_file
from sarpy.io.general.base import BaseReader, BaseWriter, SarpyIOError
from sarpy.io.general.data_segment import DataSegment, NumpyArraySegment, \
    NumpyMemmapSegment
from sarpy.io.general.format_function import ComplexFormatFunction
from sarpy.io.general.slice_parsing import verify_subscript, verify_slice

from sarpy.io.phase_history.base import CPHDTypeReader
from sarpy.io.phase_history.cphd1_elements.CPHD import CPHDType as CPHDType1, \
    CPHDHeader as CPHDHeader1, CPHD_SECTION_TERMINATOR
from sarpy.io.phase_history.cphd0_3_elements.CPHD import CPHDType as CPHDType0_3, \
    CPHDHeader as CPHDHeader0_3
from sarpy.io.phase_history.cphd_schema import get_namespace, get_default_tuple

logger = logging.getLogger(__name__)

_unhandled_version_text = 'Got unhandled CPHD version number `{}`'
_missing_channel_identifier_text = 'Cannot find CPHD channel for identifier `{}`'
_index_range_text = 'index must be in the range `[0, {})`'


class AmpScalingFunction(ComplexFormatFunction):
    __slots__ = (
        '_amplitude_scaling', )
    _allowed_ordering = ('IQ', )

    def __init__(
            self,
            raw_dtype: Union[str, numpy.dtype],
            raw_shape: Optional[Tuple[int, ...]] = None,
            formatted_shape: Optional[Tuple[int, ...]] = None,
            reverse_axes: Optional[Tuple[int, ...]] = None,
            transpose_axes: Optional[Tuple[int, ...]] = None,
            band_dimension: int = -1,
            amplitude_scaling: Optional[numpy.ndarray] = None):
        """

        Parameters
        ----------
        raw_dtype : str|numpy.dtype
            The raw datatype. Valid options dependent on the value of order.
        raw_shape : None|Tuple[int, ...]
        formatted_shape : None|Tuple[int, ...]
        reverse_axes : None|Tuple[int, ...]
        transpose_axes : None|Tuple[int, ...]
        band_dimension : int
            Which band is the complex dimension, **after** the transpose operation.
        amplitude_scaling : None|numpy.ndarray
            This is here to support the presence of a scaling in CPHD or CRSD usage.
            This requires that `band_dimension` is the final dimension and neither
            `reverse_axes` nor `transpose_axes` is populated.
        """

        ComplexFormatFunction.__init__(
            self, raw_dtype, 'IQ', raw_shape=raw_shape, formatted_shape=formatted_shape,
            reverse_axes=reverse_axes, transpose_axes=transpose_axes, band_dimension=band_dimension)
        self._amplitude_scaling = None
        self.set_amplitude_scaling(amplitude_scaling)

    @property
    def amplitude_scaling(self) -> Optional[numpy.ndarray]:
        """
        The scaling multiplier array, for CPHD/CRSD usage.

        Returns
        -------
        Optional[numpy.ndarray]
        """
        pass

    def set_amplitude_scaling(
            self,
            array: Optional[numpy.ndarray]) -> None:
        """
        Set the amplitude scaling array.

        Parameters
        ----------
        array : None|numpy.ndarray

        Returns
        -------
        None
        """
        pass

    def _validate_amplitude_scaling(self) -> None:
        pass

    def _forward_functional_step(
            self,
            data: numpy.ndarray,
            subscript: Tuple[slice, ...]) -> numpy.ndarray:
        out = ComplexFormatFunction._forward_functional_step(self, data, subscript)

        # NB: subscript is in raw coordinates, but we have verified that
        #   the first dimension is unchanged
        if self._amplitude_scaling is not None:
            out = self._amplitude_scaling[subscript[0]][:, numpy.newaxis] * out

        return out

    def _reverse_functional_step(
            self,
            data: numpy.ndarray,
            subscript: Tuple[slice, ...]) -> numpy.ndarray:
        # NB: subscript is in formatted coordinates, but we have verified that
        #   transpose_axes is None and band_dimension is the final dimension
        if self._amplitude_scaling is not None:
            data = (1./self._amplitude_scaling[subscript[0]])[:, numpy.newaxis] * data
        if issubclass(self._raw_dtype.type, numbers.Integral):
            data = numpy.rint(data)

        return ComplexFormatFunction._reverse_functional_step(self, data, subscript)

    def validate_shapes(self) -> None:
        pass


class CPHDDetails(object):
    """
    The basic CPHD element parser.
    """

    __slots__ = (
        '_file_name', '_file_object', '_closed', '_close_after', '_cphd_version', '_cphd_header', '_cphd_meta')

    def __init__(self, file_object: str):
        """

        Parameters
        ----------
        file_object : str|BinaryIO
            The path to or file like object referencing the CPHD file.
        """

        self._closed = False
        self._close_after = None
        self._cphd_version = None
        self._cphd_header = None
        self._cphd_meta = None
        self._file_object = None  # type: Optional[BinaryIO]

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
        if not head_bytes.startswith(b'CPHD'):
            raise SarpyIOError('File {} does not appear to be a CPHD file.'.format(self.file_name))

        self._extract_version()
        self._extract_header()
        self._extract_cphd()

    @property
    def file_name(self) -> str:
        """
        str: The CPHD filename.
        """
        pass

    @property
    def file_object(self) -> BinaryIO:
        """
        BinaryIO: The binary file object
        """
        pass

    @property
    def cphd_version(self) -> str:
        """
        str: The CPHD version.
        """
        pass

    @property
    def cphd_meta(self) -> Union[CPHDType1, CPHDType0_3]:
        """
        CPHDType1|CPHDType0_3: The CPHD metadata object, which is version dependent.
        """
        pass

    @property
    def cphd_header(self) -> Union[CPHDHeader1, CPHDHeader0_3]:
        """
        CPHDHeader1|CPHDHeader0_3: The CPHD header object, which is version dependent.
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

    def _extract_cphd(self) -> None:
        """
        Extract and interpret the CPHD structure from the file.
        """
        pass

    def get_cphd_bytes(self) -> bytes:
        """
        Extract the (uninterpreted) bytes representation of the CPHD structure.

        Returns
        -------
        bytes
        """
        pass

    def close(self):
        if self._closed:
            return

        if self._close_after:
            if hasattr(self.file_object, 'close'):
                self.file_object.close()
        self._file_object = None
        self._closed = True

    def __del__(self):
        self.close()


def _validate_cphd_details(
        cphd_details: Union[str, CPHDDetails],
        version: Union[None, str, Sequence[str]] = None) -> CPHDDetails:
    """
    Validate the input argument.

    Parameters
    ----------
    cphd_details : str|CPHDDetails
    version : None|str|Sequence[str]

    Returns
    -------
    CPHDDetails

    Raises
    ------
    TypeError
        The input was neither path to a CPHD file nor a CPHDDetails instance
    ValueError
        The CPHD file was the incorrect (specified) version
    """
    pass


##########
# Reading


class CPHDReader(CPHDTypeReader):
    """
    The Abstract CPHD reader instance, which just selects the proper CPHD reader
    class based on the CPHD version. Note that there is no __init__ method for
    this class, and it would be skipped regardless. Ensure that you make a direct
    call to the BaseReader.__init__() method when extending this class.

    **Updated in version 1.3.0** for reading changes.
    """

    __slots__ = ('_cphd_details', )

    def __new__(cls, *args, **kwargs):
        if len(args) == 0:
            raise ValueError(
                'The first argument of the constructor is required to be a file_path '
                'or CPHDDetails instance.')
        if is_file_like(args[0]):
            raise ValueError('File like object input not supported for CPHD reading at this time.')
        cphd_details = _validate_cphd_details(args[0])

        if cphd_details.cphd_version.startswith('0.3'):
            return object.__new__(CPHDReader0_3)
        elif cphd_details.cphd_version.startswith('1.'):
            return object.__new__(CPHDReader1)
        else:
            raise ValueError('Got unhandled CPHD version {}'.format(cphd_details.cphd_version))

    @property
    def cphd_details(self) -> CPHDDetails:
        """
        CPHDDetails: The cphd details object.
        """
        pass

    @property
    def cphd_version(self) -> str:
        """
        str: The CPHD version.
        """
        pass

    @property
    def cphd_header(self) -> Union[CPHDHeader1, CPHDHeader0_3]:
        """
        CPHDHeader1|CPHDHeader0_3: The CPHD header object, which is version dependent.
        """
        pass

    @property
    def file_name(self) -> str:
        pass

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

    def read_pvp_block(self) -> Dict[Union[int, str], numpy.ndarray]:
        raise NotImplementedError

    def read_signal_block(self) -> Dict[Union[int, str], numpy.ndarray]:
        raise NotImplementedError

    def read_signal_block_raw(self) -> Dict[Union[int, str], numpy.ndarray]:
        raise NotImplementedError

    def close(self):
        CPHDTypeReader.close(self)
        if hasattr(self, '_cphd_details'):
            if hasattr(self._cphd_details, 'close'):
                self._cphd_details.close()
            del self._cphd_details


class CPHDReader1(CPHDReader):
    """
    The CPHD version 1 reader.

    **Updated in version 1.3.0** for reading changes.
    """
    _allowed_versions = ('1.0', '1.1')

    def __new__(cls, *args, **kwargs):
        # we must override here, to avoid recursion with
        # the CPHDReader parent
        return object.__new__(cls)

    def __init__(self, cphd_details: Union[str, CPHDDetails]):
        """

        Parameters
        ----------
        cphd_details : str|CPHDDetails
        """

        self._channel_map = None  # type: Union[None, Dict[str, int]]
        self._pvp_memmap = None  # type: Union[None, Dict[str, numpy.ndarray]]
        self._support_array_memmap = None  # type: Union[None, Dict[str, numpy.ndarray]]
        self._cphd_details = _validate_cphd_details(cphd_details, version=self._allowed_versions)

        CPHDTypeReader.__init__(self, None, self._cphd_details.cphd_meta)
        # set data segments after setting up the pvp information, because
        #   we need the AmpSf to set up the format function for the data segment
        self._create_pvp_memmaps()
        self._create_support_array_memmaps()

        data_segments = self._create_data_segments()
        BaseReader.__init__(self, data_segments, reader_type='CPHD')

    @property
    def cphd_meta(self) -> CPHDType1:
        """
        CPHDType1: The CPHD structure.
        """
        pass

    @property
    def cphd_header(self) -> CPHDHeader1:
        """
        CPHDHeader1: The CPHD header object.
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
        Get corresponding integer index for CPHD channel.

        Parameters
        ----------
        index : int|str

        Returns
        -------
        int
        """

        cphd_meta = self.cphd_details.cphd_meta

        if isinstance(index, str):
            if index in self._channel_map:
                return self._channel_map[index]
            else:
                raise KeyError(_missing_channel_identifier_text.format(index))
        else:
            int_index = int(index)
            if not (0 <= int_index < cphd_meta.Data.NumCPHDChannels):
                raise ValueError(_index_range_text.format(cphd_meta.Data.NumCPHDChannels))
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

        cphd_meta = self.cphd_details.cphd_meta

        if isinstance(index, str):
            if index in self._channel_map:
                return index
            else:
                raise KeyError(_missing_channel_identifier_text.format(index))
        else:
            int_index = int(index)
            if not (0 <= int_index < cphd_meta.Data.NumCPHDChannels):
                raise ValueError(_index_range_text.format(cphd_meta.Data.NumCPHDChannels))
            return cphd_meta.Data.Channels[int_index].Identifier

    def read_support_array(
            self,
            index: Union[int, str],
            *ranges: Sequence[Union[None, int, Tuple[int, ...], slice]]) -> numpy.ndarray:
        # find the support array identifier
        pass

    def read_support_block(self) -> Dict[str, numpy.ndarray]:
        pass

    def read_pvp_variable(
            self,
            variable: str,
            index: Union[int, str],
            the_range: Union[None, int, Tuple[int, ...], slice] = None) -> Optional[numpy.ndarray]:
        pass

    def read_pvp_array(
            self,
            index: Union[int, str],
            the_range: Union[None, int, Tuple[int, ...], slice] = None) -> numpy.ndarray:
        index_key = self._validate_index_key(index)
        the_memmap = self._pvp_memmap[index_key]
        the_slice = verify_slice(the_range, the_memmap.shape[0])
        return numpy.copy(the_memmap[the_slice])

    def read_pvp_block(self) -> Dict[str, numpy.ndarray]:
        pass

    def read_signal_block(self) -> Dict[str, numpy.ndarray]:
        pass

    def read_signal_block_raw(self) -> Dict[Union[int, str], numpy.ndarray]:
        pass

    def read_chip(
            self,
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

    def read(
            self,
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

    def read_raw(
            self,
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
            The data_segment index or cphd channel identifier.
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

    def __call__(
            self,
            *ranges: Sequence[Union[None, int, slice]],
            index: int = 0,
            raw: bool = False,
            squeeze: bool = True) -> numpy.ndarray:
        index = self._validate_index(index)
        return BaseReader.__call__(self, *ranges, index=index, raw=raw, squeeze=squeeze)


class CPHDReader0_3(CPHDReader):
    """
    The CPHD version 0.3 reader.

    **Updated in version 1.3.0** for reading changes.
    """

    def __new__(cls, *args, **kwargs):
        # we must override here, to avoid recursion with
        # the CPHDReader parent
        return object.__new__(cls)

    def __init__(self, cphd_details: Union[str, CPHDDetails]):
        """

        Parameters
        ----------
        cphd_details : str|CPHDDetails
        """

        self._cphd_details = _validate_cphd_details(cphd_details, version='0.3')
        CPHDTypeReader.__init__(self, None, self._cphd_details.cphd_meta)
        self._create_pvp_memmaps()

        data_segments = self._create_data_segment()
        BaseReader.__init__(self, data_segments, reader_type="CPHD")

    @property
    def cphd_meta(self) -> CPHDType0_3:
        """
        CPHDType0_3: The CPHD structure, which is version dependent.
        """
        pass

    @property
    def cphd_header(self) -> CPHDHeader0_3:
        """
        CPHDHeader0_3: The CPHD header object.
        """
        pass

    def _validate_index(self, index: int) -> int:
        """
        Validate integer index value for CPHD channel.

        Parameters
        ----------
        index : int

        Returns
        -------
        int
        """

        int_index = int(index)
        if not (0 <= int_index < self.cphd_meta.Data.NumCPHDChannels):
            raise ValueError(_index_range_text.format(self.cphd_meta.Data.NumCPHDChannels))
        return int_index

    def _create_data_segment(self) -> List[DataSegment]:
        pass

    def _create_pvp_memmaps(self) -> None:
        """
        Helper method which creates the pvp mem_maps.

        Returns
        -------
        None
        """
        pass

    def read_pvp_variable(
            self,
            variable: str,
            index: int,
            the_range: Union[None, int, Tuple[int, ...], slice] = None) -> Optional[numpy.ndarray]:
        pass

    def read_pvp_array(
            self,
            index: int,
            the_range: Union[None, int, Tuple[int, ...], slice] = None) -> numpy.ndarray:
        int_index = self._validate_index(index)
        the_memmap = self._pvp_memmap[int_index]
        the_slice = verify_slice(the_range, the_memmap.shape[0])
        return numpy.copy(the_memmap[the_slice])

    def read_pvp_block(self) -> Dict[int, numpy.ndarray]:
        """
        Reads the entirety of the PVP block(s).

        Returns
        -------
        Dict[int, numpy.ndarray]
            Dictionary of `numpy.ndarray` containing the PVP arrays.
        """
        pass

    def read_signal_block(self) -> Dict[int, numpy.ndarray]:
        pass

    def read_signal_block_raw(self) -> Dict[int, numpy.ndarray]:
        pass

    def __call__(
            self,
            *ranges: Sequence[Union[None, int, slice]],
            index: int = 0,
            raw: bool = False,
            squeeze: bool = True) -> numpy.ndarray:
        index = self._validate_index(index)
        return BaseReader.__call__(self, *ranges, index=index, raw=raw, squeeze=squeeze)


def is_a(file_name: str) -> Optional[CPHDReader]:
    """
    Tests whether a given file_name corresponds to a CPHD file. Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str
        the file_name to check

    Returns
    -------
    CPHDReader|None
        Appropriate `CPHDTypeReader` instance if CPHD file, `None` otherwise
    """
    pass


###########
# Writing

class ElementDetails(object):
    __slots__ = (
        '_item_offset', '_item_bytes', '_item_written')

    def __init__(self, item_offset: int, item_bytes: Optional[bytes] = None):
        self._item_offset = None
        self._item_bytes = None
        self._item_written = False

        self.item_offset = item_offset
        self.item_bytes = item_bytes

    @property
    def item_offset(self) -> Optional[int]:
        """
        int: The item offset.
        """
        pass

    @item_offset.setter
    def item_offset(self, value: int) -> None:
        pass

    @property
    def item_bytes(self) -> Optional[bytes]:
        """
        None|bytes: The item bytes.
        """
        pass

    @item_bytes.setter
    def item_bytes(self, value: bytes) -> None:
        pass

    @property
    def item_written(self) -> bool:
        """
        bool: Has the item been written?
        """
        pass

    @item_written.setter
    def item_written(self, value: bool):
        pass

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

        file_object.seek(self.item_offset, os.SEEK_SET)
        file_object.write(self.item_bytes)
        self.item_written = True


class CPHDWritingDetails(object):
    __slots__ = (
        '_header', '_header_written', '_meta',
        '_channel_map', '_support_map',
        '_pvp_details', '_support_details', '_signal_details')

    def __init__(self, meta: CPHDType1, check_older_version: bool = False):

        self._header = None
        self._header_written = False
        self._meta = None
        self._channel_map = {}
        self._support_map = {}
        self._pvp_details = None
        self._support_details = None
        self._signal_details = None

        self.meta = meta
        self._set_header(check_older_version)

        # initialize the information for the pvp, support, and signal details
        self._populate_pvp_details()
        self._populate_support_details()
        self._populate_signal_details()

    @property
    def header(self) -> CPHDHeader1:
        pass

    def _set_header(self, check_older_version: bool):
        pass

    @property
    def use_version(self) -> str:
        pass

    @property
    def meta(self) -> CPHDType1:
        """
        CPHDType1: The metadata
        """
        pass

    @meta.setter
    def meta(self, value):
        pass

    def _populate_pvp_details(self) -> None:
        pass

    def _populate_support_details(self) -> None:
        pass

    def _populate_signal_details(self) -> None:
        pass

    @property
    def pvp_details(self) -> Optional[Tuple[ElementDetails, ...]]:
        pass

    @property
    def support_details(self) -> Optional[Tuple[ElementDetails, ...]]:
        pass

    @property
    def signal_details(self) -> Optional[Tuple[ElementDetails, ...]]:
        pass

    @property
    def channel_map(self) -> Dict[str, int]:
        pass

    @property
    def support_map(self) -> Optional[Dict[str, int]]:
        pass

    def _write_items(
            self,
            details: Optional[Sequence[ElementDetails]],
            file_object: BinaryIO) -> None:
        if details is None:
            return
        for index, entry in enumerate(details):
            entry.write_item(file_object)

    def _verify_item_written(
            self,
            details: Optional[Sequence[ElementDetails]],
            name: str) -> None:
        if details is None:
            return

        for index, entry in enumerate(details):
            if not entry.item_written:
                logger.error('{} data at index {} not written'.format(name, index))

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
        file_object.write(CPHD_SECTION_TERMINATOR)
        # write xml
        file_object.seek(self.header.XML_BLOCK_BYTE_OFFSET, os.SEEK_SET)
        file_object.write(self.meta.to_xml_bytes(urn=get_namespace(self.use_version)))
        file_object.write(CPHD_SECTION_TERMINATOR)
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
        self._write_items(self.pvp_details, file_object)
        self._write_items(self.support_details, file_object)
        self._write_items(self.signal_details, file_object)

    def verify_all_written(self) -> None:
        if not self._header_written:
            logger.error('header not written')

        self._verify_item_written(self.pvp_details, 'pvp')
        self._verify_item_written(self.support_details, 'support')
        self._verify_item_written(self.signal_details, 'signal')


class CPHDWriter1(BaseWriter):
    """
    The CPHD version 1 writer.

    **Updated in version 1.3.0** for writing changes.
    """
    _writing_details_type = CPHDWritingDetails

    __slots__ = (
        '_file_name', '_file_object', '_in_memory', '_writing_details',
        '_pvp_memmaps', '_support_memmaps', '_signal_data_segments',
        '_can_write_regular_data')

    def __init__(
            self,
            file_object: Union[str, BinaryIO],
            meta: Optional[CPHDType1] = None,
            writing_details: Optional[CPHDWritingDetails] = None,
            check_older_version: bool = False,
            check_existence: bool = True):
        """

        Parameters
        ----------
        file_object : str|BinaryIO
        meta : None|CPHDType1
        writing_details : None|CPHDWritingDetails
        check_older_version : bool
            Try to create an older version CPHD for compliance with other
            NGA applications
        check_existence : bool
            Should we check if the given file already exists, and raises an exception if so?
        """

        self._writing_details = None

        if isinstance(file_object, str):
            if check_existence and os.path.exists(file_object):
                raise SarpyIOError(
                    'Given file {} already exists, and a new CPHD file cannot be created here.'.format(file_object))
            file_object = open(file_object, 'wb')

        if not is_file_like(file_object):
            raise ValueError('file_object requires a file path or BinaryIO object')

        self._file_object = file_object
        if is_real_file(file_object):
            self._file_name = file_object.name
            self._in_memory = False
        else:
            self._file_name = None
            self._in_memory = True

        if meta is None and writing_details is None:
            raise ValueError('One of meta or writing_details must be provided.')
        if writing_details is None:
            writing_details = self._writing_details_type(meta, check_older_version=check_older_version)
        self.writing_details = writing_details

        self._pvp_memmaps = None  # type: Optional[Dict[str, numpy.ndarray]]
        self._support_memmaps = None  # type: Optional[Dict[str, numpy.ndarray]]
        self._signal_data_segments = None  # type: Optional[Dict[str, DataSegment]]
        self._can_write_regular_data = None  # type: Optional[Dict[str, bool]]
        self._closed = False

        data_segment = self._initialize_data()
        BaseWriter.__init__(self, data_segment)

    @property
    def writing_details(self) -> CPHDWritingDetails:
        pass

    @writing_details.setter
    def writing_details(self, value):
        pass

    @property
    def file_name(self) -> Optional[str]:
        pass

    @property
    def meta(self) -> CPHDType1:
        """
        CPHDType1: The metadata
        """
        pass

    @staticmethod
    def _verify_dtype(
            obs_dtype: numpy.dtype,
            exp_dtype: numpy.dtype,
            purpose: str) -> None:
        """
        This is a helper function for comparing two structured array dtypes.

        Parameters
        ----------
        obs_dtype : numpy.dtype
        exp_dtype : numpy.dtype
        purpose : str
        """
        pass

    def _validate_channel_index(self, index: Union[int, str]) -> int:
        """
        Get corresponding integer index for CPHD channel.

        Parameters
        ----------
        index : int|str

        Returns
        -------
        int
        """

        if isinstance(index, str):
            if index in self.writing_details.channel_map:
                return self.writing_details.channel_map[index]
            else:
                raise KeyError(_missing_channel_identifier_text.format(index))
        else:
            int_index = int(index)
            if not (0 <= int_index < self.meta.Data.NumCPHDChannels):
                raise ValueError(_index_range_text.format(self.meta.Data.NumCPHDChannels))
            return int_index

    def _validate_channel_key(self, index: Union[int, str]) -> str:
        """
        Gets the corresponding identifier for the CPHD channel.

        Parameters
        ----------
        index : int|str

        Returns
        -------
        str
        """

        if isinstance(index, str):
            if index in self.writing_details.channel_map:
                return index
            else:
                raise KeyError(_missing_channel_identifier_text.format(index))
        else:
            int_index = int(index)
            if not (0 <= int_index < self.meta.Data.NumCPHDChannels):
                raise ValueError(_index_range_text.format(self.meta.Data.NumCPHDChannels))
            return self.meta.Data.Channels[int_index].Identifier

    def _validate_support_index(self, index: Union[int, str]) -> int:
        """
        Get corresponding integer index for support array.

        Parameters
        ----------
        index : int|str

        Returns
        -------
        int
        """
        pass

    def _validate_support_key(self, index: Union[int, str]) -> str:
        """
        Gets the corresponding identifier for the support array.

        Parameters
        ----------
        index : int|str

        Returns
        -------
        str
        """
        pass

    def _initialize_data(self) -> List[DataSegment]:
        pass

    def write_support_array(self,
                            identifier: Union[int, str],
                            data: numpy.ndarray) -> None:
        """
        Write support array data to the file.

        Parameters
        ----------
        identifier : int|str
        data : numpy.ndarray
        """
        pass

    def write_pvp_array(self,
                        identifier: Union[int, str],
                        data: numpy.ndarray) -> None:
        """
        Write the PVP array data to the file.

        Parameters
        ----------
        identifier : int|str
        data : numpy.ndarray
        """
        pass

    def write_support_block(self, support_block: Dict[Union[int, str], numpy.ndarray]) -> None:
        """
        Write support block to the file.

        Parameters
        ----------
        support_block: dict
            Dictionary of `numpy.ndarray` containing the support arrays.
        """
        pass

    def write_pvp_block(self, pvp_block: Dict[Union[int, str], numpy.ndarray]) -> None:
        """
        Write PVP block to the file.

        Parameters
        ----------
        pvp_block: dict
            Dictionary of `numpy.ndarray` containing the PVP arrays.
        """
        pass

    def write_signal_block(self, signal_block: Dict[Union[int, str], numpy.ndarray]) -> None:
        """
        Write signal block to the file.

        Parameters
        ----------
        signal_block: dict
            Dictionary of `numpy.ndarray` containing the signal arrays in complex64 format.
        """
        pass

    def write_signal_block_raw(self, signal_block):
        """
        Write signal block to the file.

        Parameters
        ----------
        signal_block: dict
            Dictionary of `numpy.ndarray` containing the raw formatted
            (i.e. file storage format) signal arrays.
        """
        pass

    def write_file(
            self,
            pvp_block: Dict[Union[int, str], numpy.ndarray],
            signal_block: Dict[Union[int, str], numpy.ndarray],
            support_block: Optional[Dict[Union[int, str], numpy.ndarray]] = None):
        """
        Write the blocks to the file.

        Parameters
        ----------
        pvp_block: Dict[str, numpy.ndarray]
            Dictionary of `numpy.ndarray` containing the PVP arrays.
            Keys must be consistent with `self.meta`
        signal_block: Dict[str, numpy.ndarray]
            Dictionary of `numpy.ndarray` containing the complex64 formatted signal
            arrays.
            Keys must be consistent with `self.meta`
        support_block: None|Dict[str, numpy.ndarray]
            Dictionary of `numpy.ndarray` containing the support arrays.
        """
        pass

    def write_file_raw(
            self,
            pvp_block: Dict[Union[int, str], numpy.ndarray],
            signal_block: Dict[Union[int, str], numpy.ndarray],
            support_block: Optional[Dict[Union[int, str], numpy.ndarray]] = None):
        """
        Write the blocks to the file.

        Parameters
        ----------
        pvp_block: Dict[str, numpy.ndarray]
            Dictionary of `numpy.ndarray` containing the PVP arrays.
            Keys must be consistent with `self.meta`
        signal_block: Dict[str, numpy.ndarray]
            Dictionary of `numpy.ndarray` containing the raw formatted
            (i.e. file storage format) signal arrays.
            Keys must be consistent with `self.meta`
        support_block: None|Dict[str, numpy.ndarray]
            Dictionary of `numpy.ndarray` containing the support arrays.
        """
        pass

    def write_chip(
            self,
            data: numpy.ndarray,
            start_indices: Union[None, int, Tuple[int, ...]] = None,
            subscript: Union[None, Tuple[slice, ...]] = None,
            index: Union[int, str] = 0) -> None:
        self.__call__(data, start_indices=start_indices, subscript=subscript, index=index, raw=False)

    def write(
            self,
            data: numpy.ndarray,
            start_indices: Union[None, int, Tuple[int, ...]] = None,
            subscript: Union[None, Tuple[slice, ...]] = None,
            index: Union[int, str] = 0) -> None:
        self.__call__(data, start_indices=start_indices, subscript=subscript, index=index, raw=False)

    def write_raw(
            self,
            data: numpy.ndarray,
            start_indices: Union[None, int, Tuple[int, ...]] = None,
            subscript: Union[None, Tuple[slice, ...]] = None,
            index: Union[int, str] = 0) -> None:
        self.__call__(data, start_indices=start_indices, subscript=subscript, index=index, raw=True)

    def __call__(
            self,
            data: numpy.ndarray,
            start_indices: Union[None, int, Tuple[int, ...]] = None,
            subscript: Union[None, Tuple[slice, ...]] = None,
            index: Union[int, str] = 0,
            raw: bool = False) -> None:
        int_index = self._validate_channel_index(index)

        identifier = self._validate_channel_key(index)
        if not raw and not self._can_write_regular_data[identifier]:
            raise ValueError(
                'The channel `{}` has an AmpSF which has not been determined,\n\t'
                'but the corresponding PVP block has not yet been written'.format(identifier))

        BaseWriter.__call__(self, data, start_indices=start_indices, subscript=subscript, index=int_index, raw=raw)

        # check if it's fully written
        # NB: this could be refactored out, but leaving it makes the most logical
        #   sense given the pvp/support approach
        fully_written = self.data_segment[int_index].check_fully_written(warn=False)
        if fully_written:
            self.writing_details.signal_details[int_index].item_written = True

    def flush(self, force: bool = False) -> None:
        self._validate_closed()

        BaseWriter.flush(self, force=force)

        try:
            if self._in_memory:
                if self.data_segment is not None:
                    for index, entry in enumerate(self.data_segment):
                        details = self.writing_details.signal_details[index]
                        if details.item_written:
                            continue
                        if details.item_bytes is not None:
                            continue
                        if force or entry.check_fully_written(warn=force):
                            details.item_bytes = entry.get_raw_bytes(warn=False)

            self.writing_details.write_all_populated_items(self._file_object)
        except AttributeError:
            return

    def close(self):
        """
        This should perform any necessary final steps, like closing
        open file handles, deleting any temp files, etc.
        Trying to read newly created file without closing may raise a ValueError.
        """

        if hasattr(self, '_closed') and self._closed:
            return

        BaseWriter.close(self)  # NB: flush called here
        try:
            if self.writing_details is not None:
                self.writing_details.verify_all_written()
        except AttributeError:
            pass
        self._writing_details = None
        self._file_object.close()
