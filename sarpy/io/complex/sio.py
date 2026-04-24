"""
Functionality for reading SIO data into a SICD model.

The SIO format is believed to be based on a memo from General Dynamics.  Some SIO features may not
be implemented and compatibility with other SIO software is not guaranteed.
"""

__classification__ = "UNCLASSIFIED"
__author__ = ("Thomas McCullough", "Wade Schwartzkopf")


import os
import struct
import logging
import re
from typing import Union, Dict, Tuple, Optional, BinaryIO

import numpy

from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.sicd_elements.blocks import RowColType
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd_elements.ImageData import ImageDataType, FullImageType
from sarpy.io.complex.sicd import AmpLookupFunction

from sarpy.io.general.base import BaseWriter, SarpyIOError
from sarpy.io.general.data_segment import NumpyArraySegment, NumpyMemmapSegment
from sarpy.io.general.format_function import ComplexFormatFunction
from sarpy.io.general.utils import is_file_like, is_real_file
from sarpy.io.xml.base import parse_xml_from_string

logger = logging.getLogger(__name__)

_unsupported_pix_size = 'Got unsupported sio data type/pixel size = `{}`'


###########
# parser and interpreter for hdf5 attributes

class SIODetails(object):
    __slots__ = (
        '_file_name', '_magic_number', '_head', '_user_data', '_data_offset',
        '_caspr_data', '_reverse_axes', '_transpose_axes', '_sicd')

    # NB: there are really just two types of SIO file (with user_data and without),
    #   with endian-ness layered on top
    ENDIAN = {
        0xFF017FFE: '>', 0xFE7F01FF: '<',  # no user data
        0xFF027FFD: '>', 0xFD7F02FF: '<'}  # with user data

    def __init__(self, file_name: str):
        self._file_name = file_name
        self._user_data = None
        self._data_offset = 20
        self._caspr_data = None
        self._reverse_axes = None
        self._transpose_axes = None
        self._sicd = None

        if not os.path.isfile(file_name):
            raise SarpyIOError('Path {} is not a file'.format(file_name))

        with open(file_name, 'rb') as fi:
            self._magic_number = struct.unpack(">I", fi.read(4))[0]
            endian = self.ENDIAN.get(self._magic_number, None)
            if endian is None:
                raise SarpyIOError(
                    'File {} is not an SIO file. Got magic number {}'.format(file_name, self._magic_number))

            # reader basic header - (rows, columns, data_type, pixel_size)?
            init_head = numpy.array(struct.unpack('{}4I'.format(endian), fi.read(16)), dtype=numpy.uint64)
            if not (numpy.all(init_head[2:] == numpy.array([13, 8]))
                    or numpy.all(init_head[2:] == numpy.array([12, 4]))
                    or numpy.all(init_head[2:] == numpy.array([11, 2]))):
                raise SarpyIOError(_unsupported_pix_size.format(init_head[2:]))
            self._head = init_head

    @property
    def file_name(self) -> str:
        pass

    @property
    def data_offset(self):  # type: () -> int
        pass

    @property
    def raw_data_size(self) -> Optional[Tuple[int, ...]]:
        pass

    @property
    def formatted_data_size(self) -> Union[None, Tuple[int, ...]]:
        pass

    @property
    def raw_data_type(self):  # type: () -> Union[None, str]
        # head[2] = (2X = vector, 1X = complex/scalar, 0X = real/scalar), where
        #   X = (1 = unsigned int, 2 = signed int, 3 = float, (4=double? I would guess)
        # head[3] = pixel size in bytes (2*bit depth for complex, or band*bit depth for vector)
        pass

    @property
    def pixel_type(self) -> str:
        pass

    def get_symmetry(self) -> Tuple[Optional[Tuple[int, ...]], Optional[Tuple[int, ...]]]:
        pass

    def _read_user_data(self):
        pass

    def _find_caspr_data(self) -> None:
        pass

    def get_sicd(self) -> SICDType:
        """
        Extract the SICD details.

        Returns
        -------
        SICDType
        """
        pass


#######
#  The actual reading implementation

class SIOReader(SICDTypeReader):
    """
    **Changed in version 1.3.0** for reading changes.
    """
    __slots__ = ('_sio_details', )

    def __init__(self, sio_details):
        """

        Parameters
        ----------
        sio_details : str|SIODetails
            filename or SIODetails object
        """

        if isinstance(sio_details, str):
            sio_details = SIODetails(sio_details)
        if not isinstance(sio_details, SIODetails):
            raise TypeError('The input argument for SIOReader must be a filename or '
                            'SIODetails object.')
        self._sio_details = sio_details
        sicd_meta = sio_details.get_sicd()

        if sicd_meta.ImageData.PixelType == 'AMP8I_PHS8I':
            format_function = AmpLookupFunction(sio_details.raw_data_type, sicd_meta.ImageData.AmpTable)
        else:
            format_function = ComplexFormatFunction(
                sio_details.raw_data_type, order='IQ', band_dimension=-1)
        reverse_axes, transpose_axes = sio_details.get_symmetry()
        data_segment = NumpyMemmapSegment(
            sio_details.file_name, sio_details.data_offset,
            sio_details.raw_data_type, sio_details.raw_data_size,
            'complex64', sio_details.formatted_data_size,
            reverse_axes=reverse_axes, transpose_axes=transpose_axes,
            format_function=format_function, mode='r', close_file=True)

        SICDTypeReader.__init__(self, data_segment, sicd_meta, close_segments=True)
        self._check_sizes()

    @property
    def sio_details(self) -> SIODetails:
        """
        SIODetails: The sio details object.
        """
        pass

    @property
    def file_name(self) -> str:
        pass


########
# base expected functionality for a module with an implemented Reader

def is_a(file_name: str) -> Optional[SIOReader]:
    """
    Tests whether a given file_name corresponds to a SIO file. Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str
        the file_name to check

    Returns
    -------
    SIOReader|None
        `SIOReader` instance if SIO file, `None` otherwise
    """
    pass


#######
#  The actual writing implementation

class SIOWriter(BaseWriter):
    """
    **Changed in version 1.3.0** for writing changes.
    """

    _slots__ = (
        '_file_name', '_file_object', '_in_memory',
        '_data_offset', '_data_written')

    def __init__(
            self,
            file_object: Union[str, BinaryIO],
            sicd_meta: SICDType,
            user_data: Optional[Dict[str, str]] = None,
            check_older_version: bool = False,
            check_existence: bool = True):
        """

        Parameters
        ----------
        file_object : str|BinaryIO
        sicd_meta : SICDType
        user_data : None|Dict[str, str]
        check_older_version : bool
            Try to use an older version (1.1) of the SICD standard, for possible
            application compliance issues?
        check_existence : bool
            Should we check if the given file already exists, and raises an exception if so?
        """

        self._data_written = True
        if isinstance(file_object, str):
            if check_existence and os.path.exists(file_object):
                raise SarpyIOError(
                    'Given file {} already exists,\n\t'
                    'and a new SIO file cannot be created here.'.format(file_object))
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

        # choose magic number (with user data) and corresponding endian-ness
        magic_number = 0xFD7F02FF
        endian = SIODetails.ENDIAN[magic_number]

        # define basic image details
        raw_shape = (sicd_meta.ImageData.NumRows, sicd_meta.ImageData.NumCols, 2)
        pixel_type = sicd_meta.ImageData.PixelType
        if pixel_type == 'RE32F_IM32F':
            raw_dtype = numpy.dtype('{}f4'.format(endian))
            element_type = 13
            element_size = 8
            format_function = ComplexFormatFunction(raw_dtype, order='IQ', band_dimension=2)
        elif pixel_type == 'RE16I_IM16I':
            raw_dtype = numpy.dtype('{}i2'.format(endian))
            element_type = 12
            element_size = 4
            format_function = ComplexFormatFunction(raw_dtype, order='IQ', band_dimension=2)
        else:
            raw_dtype = numpy.dtype('{}u1'.format(endian))
            element_type = 11
            element_size = 2
            format_function = AmpLookupFunction(raw_dtype, sicd_meta.ImageData.AmpTable)

        # construct the sio header
        header = numpy.array(
            [raw_shape[0], raw_shape[1], element_type, element_size],
            dtype='>u4')
        # construct the user data - must be {str : str}
        if user_data is None:
            user_data = {}
        uh_args = sicd_meta.get_des_details(check_older_version)
        user_data['SICDMETA'] = sicd_meta.to_xml_string(tag='SICD', urn=uh_args['DESSHTN'])

        # write the initial things to the buffer
        self._file_object.seek(0, os.SEEK_SET)
        self._file_object.write(struct.pack('>I', magic_number))
        self._file_object.write(struct.pack('{}4I'.format(endian), *header))
        self._file_object.write(struct.pack('{}I'.format(endian), len(user_data)))
        # write the user data - name size, name, value size, value
        for name in user_data:
            name_bytes = name.encode('utf-8')
            self._file_object.write(struct.pack('{}I'.format(endian), len(name_bytes)))
            self._file_object.write(struct.pack('{}{}s'.format(endian, len(name_bytes)), name_bytes))
            val_bytes = user_data[name].encode('utf-8')
            self._file_object.write(struct.pack('{}I'.format(endian), len(val_bytes)))
            self._file_object.write(struct.pack('{}{}s'.format(endian, len(val_bytes)), val_bytes))
        self._data_offset = self._file_object.tell()
        # initialize the single data segment
        if self._in_memory:
            underlying_array = numpy.full(raw_shape, fill_value=0, dtype=raw_dtype)
            data_segment = NumpyArraySegment(
                underlying_array, 'complex64', raw_shape[:2], format_function=format_function, mode='w')
            self._data_written = False
        else:
            data_segment = NumpyMemmapSegment(
                self._file_name, self._data_offset, raw_dtype, raw_shape,
                'complex64', raw_shape[:2], format_function=format_function, mode='w', close_file=False)
            self._data_written = True
        BaseWriter.__init__(self, data_segment)

    @property
    def file_name(self) -> Optional[str]:
        """
        None|str: The file name, if feasible.
        """
        pass

    def flush(self, force: bool = False) -> None:
        BaseWriter.flush(self, force=force)
        if self._data_written:
            return

        if force or self.data_segment[0].check_fully_written(warn=force):
            self._file_object.seek(self._data_offset, os.SEEK_SET)
            self._file_object.write(self.data_segment[0].get_raw_bytes(warn=False))

    def close(self) -> None:
        """
        Completes any necessary final steps.
        """

        if not hasattr(self, '_closed') or self._closed:
            return

        self.flush(force=True)
        BaseWriter.close(self)
        self._file_object = None