"""
This module provides structures for annotating a given SICD type file for RCS
calculations
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import logging
from collections import OrderedDict, defaultdict
import json
from typing import Union, Any, List

import numpy

from sarpy.geometry.geometry_elements import Jsonable, Polygon, MultiPolygon
from sarpy.annotation.base import AnnotationFeature, AnnotationProperties, \
    AnnotationCollection, FileAnnotationCollection

from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.utils import get_im_physical_coords


_RCS_VERSION = "RCS:1.0"
logger = logging.getLogger(__name__)

DEFAULT_NAME_MAPPING = OrderedDict(
    RCS='RCSSFPoly',
    BetaZero='BetaZeroSFPoly',
    GammaZero='GammaZeroSFPoly',
    SigmaZero='SigmaZeroSFPoly')


def _get_polygon_bounds(polygon, data_size):
    """
    Gets the row/column bounds for the polygon and a polygon inclusion mask for
    the defined rectangular pixel grid.

    Parameters
    ----------
    polygon : Polygon
    data_size : Tuple[int, int]

    Returns
    -------
    row_bounds : Tuple[int, int]
        The lower and upper bounds for the rows.
    col_bounds : Tuple[int, int]
        The lower and upper bounds for the columns.
    mask: numpy.ndarray
        The boolean inclusion mask.
    """
    pass


def create_rcs_value_collection_for_reader(reader, polygon):
    """
    Given a SICD type reader and a polygon with coordinates in pixel space
    (all sicd footprint assumed applicable), construct the `RCSValueCollection`.

    Parameters
    ----------
    reader : SICDTypeReader
    polygon : Polygon|MultiPolygon

    Returns
    -------
    RCSValueCollection
    """
    pass


class RCSStatistics(Jsonable):
    __slots__ = ('mean', 'std', 'max', 'min')
    _type = 'RCSStatistics'

    def __init__(self, mean=None, std=None, max=None, min=None):
        """

        Parameters
        ----------
        mean : None|float
            All values are assumed the be stored here in units of power
        std : None|float
            All values are assumed the be stored here in units of power
        max : None|float
            All values are assumed the be stored here in units of power
        min : None|float
            All values are assumed the be stored here in units of power
        """

        if mean is not None:
            mean = float(mean)
        if std is not None:
            std = float(std)
        if max is not None:
            max = float(max)
        if min is not None:
            min = float(min)

        self.mean = mean  # type: Union[None, float]
        self.std = std  # type: Union[None, float]
        self.max = max  # type: Union[None, float]
        self.min = min  # type: Union[None, float]

    @classmethod
    def from_dict(cls, the_json):
        typ = the_json['type']
        if typ != cls._type:
            raise ValueError('RCSStatistics cannot be constructed from {}'.format(the_json))
        return cls(
            mean=the_json.get('mean', None),
            std=the_json.get('std', None),
            max=the_json.get('max', None),
            min=the_json.get('min', None))

    def to_dict(self, parent_dict=None):
        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        for attr in self.__slots__:
            parent_dict[attr] = getattr(self, attr)
        return parent_dict

    def get_field_list(self):
        pass


class RCSValue(Jsonable):
    """
    The collection of RCSStatistics elements.
    """

    __slots__ = ('polarization', 'units', '_index', '_value', '_noise')
    _type = 'RCSValue'

    def __init__(self, polarization, units, index, value=None, noise=None):
        """

        Parameters
        ----------
        polarization : str
        units: str
        index : int
        value : None|RCSStatistics
        noise : None|RCSStatistics
        """
        self._value = None
        self._noise = None
        self._index = None
        self.polarization = polarization
        self.units = units
        self.index = index
        self.value = value
        self.noise = noise

    @property
    def value(self):
        """
        None|RCSStatistics: The value
        """
        pass

    @value.setter
    def value(self, val):
        pass

    @property
    def index(self):
        """
        int: The image index to which this applies
        """

        return self._index

    @index.setter
    def index(self, value):
        if value is None:
            value = 0
        self._index = int(value)

    @property
    def noise(self):
        """
        None|RCSStatistics: The noise
        """
        pass

    @noise.setter
    def noise(self, val):
        pass

    @classmethod
    def from_dict(cls, the_json):  # type: (dict) -> RCSValue
        typ = the_json['type']
        if typ != cls._type:
            raise ValueError('RCSValue cannot be constructed from {}'.format(the_json))
        return cls(
            the_json.get('polarization', None),
            the_json.get('units', None),
            the_json.get('index', None),
            value=the_json.get('value', None),
            noise=the_json.get('noise', None))

    def to_dict(self, parent_dict=None):
        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        parent_dict['polarization'] = self.polarization
        parent_dict['units'] = self.units
        parent_dict['index'] = self.index
        if self.value is not None:
            parent_dict['value'] = self.value.to_dict()
        if self.noise is not None:
            parent_dict['noise'] = self.noise.to_dict()
        return parent_dict


class RCSValueCollection(Jsonable):
    """
    A specific type for the AnnotationProperties.parameters
    """

    __slots__ = ('_pixel_count', '_elements')
    _type = 'RCSValueCollection'

    def __init__(self, pixel_count=None, elements=None):
        """

        Parameters
        ----------
        pixel_count : None|int
        elements : None|List[RCSValue|dict]
        """

        self._pixel_count = None
        self._elements = []

        self.pixel_count = pixel_count
        self.elements = elements

    def __len__(self):
        return len(self._elements)

    def __getitem__(self, item):
        # type: (Union[int, str]) -> Union[None, RCSValue]
        return self._elements[item]

    @property
    def pixel_count(self):
        # type: () -> Union[None, int]
        """
        None|int: The number of integer pixel grid elements contained in the interior
        of the associated geometry element.
        """
        pass

    @pixel_count.setter
    def pixel_count(self, value):
        pass

    @property
    def elements(self):
        # type: () -> Union[None, List[RCSValue]]
        """
        List[RCSValue]: The RCSValue elements.
        """
        pass

    @elements.setter
    def elements(self, elements):
        pass

    def insert_new_element(self, element):
        """
        Inserts an element at the end of the elements list.

        Parameters
        ----------
        element : RCSValue
        """
        pass

    @classmethod
    def from_dict(cls, the_json):
        # type: (dict) -> RCSValueCollection

        typ = the_json['type']
        if typ != cls._type:
            raise ValueError('RCSValueCollection cannot be constructed from {}'.format(the_json))
        return cls(
            pixel_count=the_json.get('pixel_count', None), elements=the_json.get('elements', None))

    def to_dict(self, parent_dict=None):
        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        parent_dict['pixel_count'] = self.pixel_count
        if len(self._elements) > 0:
            parent_dict['elements'] = [entry.to_dict() for entry in self._elements]
        return parent_dict


class RCSProperties(AnnotationProperties):
    _type = 'RCSProperties'

    @property
    def parameters(self):
        """
        RCSValueCollection: The parameters
        """
        pass

    @parameters.setter
    def parameters(self, value):
        pass


class RCSFeature(AnnotationFeature):
    """
    A specific extension of the Feature class which has the properties attribute
    populated with RCSValueCollection instance.
    """
    _allowed_geometries = (Polygon, MultiPolygon)

    @property
    def properties(self):
        # type: () -> RCSProperties
        """
        The properties.

        Returns
        -------
        RCSProperties
        """
        pass

    @properties.setter
    def properties(self, properties):
        pass

    def set_rcs_parameters_from_reader(self, reader):
        """
        Given a SICD type reader construct the `RCSValueCollection` and set that
        as the properties.parameters value.

        Parameters
        ----------
        reader : SICDTypeReader
        """
        pass


class RCSCollection(AnnotationCollection):
    """
    A specific extension of the AnnotationCollection class which has that the
    features are RCSFeature instances.
    """

    @property
    def features(self):
        """
        The features list.

        Returns
        -------
        List[RCSFeature]
        """
        pass

    @features.setter
    def features(self, features):
        pass

    def add_feature(self, feature):
        """
        Add an annotation.

        Parameters
        ----------
        feature : RCSFeature|dict
        """
        pass

    def __getitem__(self, item):
        # type: (Any) -> Union[RCSFeature, List[RCSFeature]]
        if self._features is None:
            raise StopIteration

        if isinstance(item, str):
            index = self._feature_dict[item]
            return self._features[index]
        return self._features[item]


###########
# serialized file object

class FileRCSCollection(FileAnnotationCollection):
    """
    An collection of RCS statistics elements.
    """
    _type = 'FileRCSCollection'

    def __init__(self, version=None, annotations=None, image_file_name=None,
                 image_id=None, core_name=None):
        if version is None:
            version = _RCS_VERSION

        FileAnnotationCollection.__init__(
            self, version=version, annotations=annotations, image_file_name=image_file_name,
            image_id=image_id, core_name=core_name)

    @property
    def annotations(self):
        """
        The annotations.

        Returns
        -------
        RCSCollection
        """
        pass

    @annotations.setter
    def annotations(self, annotations):
        # type: (Union[None, RCSCollection, dict]) -> None
        pass

    def add_annotation(self, annotation):
        """
        Add an annotation.

        Parameters
        ----------
        annotation : RCSFeature
            The prospective annotation.
        """
        pass

    def delete_annotation(self, annotation_id):
        """
        Deletes the annotation associated with the given id.

        Parameters
        ----------
        annotation_id : str
        """
        pass

    @classmethod
    def from_file(cls, file_name):
        """
        Read from (json) file.

        Parameters
        ----------
        file_name : str

        Returns
        -------
        FileRCSCollection
        """

        with open(file_name, 'r') as fi:
            the_dict = json.load(fi)
        return cls.from_dict(the_dict)

    @classmethod
    def from_dict(cls, the_dict):
        """
        Define from a dictionary representation.

        Parameters
        ----------
        the_dict : dict

        Returns
        -------
        FileRCSCollection
        """

        if not isinstance(the_dict, dict):
            raise TypeError('This requires a dict. Got type {}'.format(type(the_dict)))

        typ = the_dict.get('type', 'NONE')
        if typ != cls._type:
            raise ValueError('FileRCSCollection cannot be constructed from the input dictionary')

        return cls(
            version=the_dict.get('version', 'UNKNOWN'),
            annotations=the_dict.get('annotations', None),
            image_file_name=the_dict.get('image_file_name', None),
            image_id=the_dict.get('image_id', None),
            core_name=the_dict.get('core_name', None))
