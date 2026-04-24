"""
Module contained elements for defining TREs - really intended as read only objects.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"

import functools
import logging
import struct
from collections import OrderedDict
from typing import Union, List

from ..base import TRE

logger = logging.getLogger(__name__)


def _parse_type(typ_string, leng, value, start):
    """

    Parameters
    ----------
    typ_string : str
    leng : int
    value : bytes
    start : int

    Returns
    -------
    str|int|bytes|float
    """
    pass


def _str_encoder(val, formatspec):
    pass


def _create_encoder(typ_string, leng):
    pass


class TREElement(object):
    """
    Basic TRE element class
    """

    def __init__(self):
        self._field_ordering = []
        self._field_encoders = {}
        self._bytes_length = 0

    def __str__(self):
        return '{0:s}({1:s})'.format(self.__class__.__name__, self.to_dict())

    def __repr__(self):
        return '{0:s}(b"'.format(self.__class__.__name__) + self.to_bytes().decode() + '")'

    def add_field(self, attribute, typ_string, leng, value):
        """
        Add a field/attribute to the object - as we deserialize.

        Parameters
        ----------
        attribute : str
            The new field/attribute name for out object instance.
        typ_string : str
            One of 's' (string), 'd' (integer), 'b' (raw/bytes), or 'ieee754_binary32'
        leng : int
            The length in bytes of the representation of this attribute
        value : bytes
            The bytes array of the object we are deserializing

        Returns
        -------
        None
        """
        pass

    def add_loop(self, attribute, length, child_type, value, *args):
        """
        Add an attribute from a loop construct of a given type to the object - as we deserialize.

        Parameters
        ----------
        attribute : str
            The new field/attribute name for out object instance.
        length : int
            The number of loop iterations present.
        child_type : type
            The type of the child - must extend TREElement
        value : bytes
            The bytes array of the object we are deserializing
        args
            Any optional positional arguments that the child_type constructor should have.

        Returns
        -------
        None
        """
        pass

    def _attribute_to_bytes(self, attribute):
        """
        Get byte representation for the given attribute.

        Parameters
        ----------
        attribute : str

        Returns
        -------
        bytes
        """

        val = getattr(self, attribute, None)
        if val is None:
            return b''
        elif isinstance(val, TREElement):
            return val.to_bytes()
        else:
            return self._field_encoders[attribute](val)

    def to_dict(self):
        """
        Create a dictionary representation of the object.

        Returns
        -------
        dict
        """

        out = OrderedDict()
        for fld in self._field_ordering:
            val = getattr(self, fld)
            if val is None or isinstance(val, (bytes, str, int, float)):
                out[fld] = val
            elif isinstance(val, TREElement):
                out[fld] = val.to_dict()
            else:
                raise TypeError('Unhandled type {}'.format(type(val)))
        return out

    def get_bytes_length(self):
        """
        The length in bytes of the serialized representation.

        Returns
        -------
        int
        """

        return self._bytes_length

    def to_bytes(self):
        """
        Serialize to bytes.

        Returns
        -------
        bytes
        """

        items = [self._attribute_to_bytes(fld) for fld in self._field_ordering]
        return b''.join(items)

    def to_json(self):
        """
        Gets a json representation of this element.

        Returns
        -------
        dict|list
        """
        pass


class TRELoop(TREElement):
    """
    Provides the TRE loop construct
    """

    def __init__(self, length, child_type, value, start, *args, **kwargs):
        """

        Parameters
        ----------
        length : int
        child_type : type
        value : bytes
        start : int
        args
            optional positional args for child class construction
        kwargs
            optional keyword arguments for child class construction
        """

        if not issubclass(child_type, TREElement):
            raise TypeError('child_class must be a subclass of TREElement.')

        super(TRELoop, self).__init__()
        self._data = []
        loc = start
        for i in range(length):
            entry = child_type(value[loc:], *args, **kwargs)
            leng = entry.get_bytes_length()
            self._bytes_length += leng
            loc += leng
            self._data.append(entry)

    def to_dict(self):
        return [entry.to_dict() for entry in self._data]

    def to_bytes(self):
        return b''.join(entry.to_bytes() for entry in self._data)

    def __len__(self):
        return len(self._data)

    def __getitem__(self, item):  # type: (Union[int, slice]) -> Union[TREElement, List[TREElement]]
        return self._data[item]

    def to_json(self):
        """
        Gets a json representation of this element.

        Returns
        -------
        dict|list
        """
        pass


class TREExtension(TRE):
    """
    Extend this object to provide concrete TRE implementations.
    """

    __slots__ = ('_data', )
    _tag_value = None
    _data_type = None

    def __init__(self, value):
        if not issubclass(self._data_type, TREElement):
            raise TypeError('_data_type must be a subclass of TREElement. Got type {}'.format(self._data_type))
        if not isinstance(self._tag_value, str):
            raise TypeError('_tag_value must be a string')
        if len(self._tag_value) > 6:
            raise ValueError('Tag value must have 6 or fewer characters.')
        self._data = None
        self.DATA = value

    @property
    def TAG(self):
        pass

    @property
    def DATA(self):  # type: () -> _data_type
        pass

    @DATA.setter
    def DATA(self, value):
        # type: (Union[bytes, _data_type]) -> None
        pass

    @property
    def EL(self):
        pass

    @classmethod
    def minimum_length(cls):
        pass

    def get_bytes_length(self):
        return 11 + self.EL

    def to_bytes(self):
        return ('{0:6s}{1:05d}'.format(self.TAG, self.EL)).encode('utf-8') + self._data.to_bytes()

    @classmethod
    def from_bytes(cls, value, start):
        tag_value = value[start:start+6].decode('utf-8').strip()
        lng = int(value[start+6:start+11])
        if tag_value != cls._tag_value:
            raise ValueError('tag value must be {}. Got {}'.format(cls._tag_value, tag_value))
        return cls(value[start+11:start+11+lng])
