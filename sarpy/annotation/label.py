"""
This module provides structures for performing data labelling on a background image
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import logging
import time
from collections import OrderedDict
import json
from typing import Union, List, Tuple, Any, Dict, Optional
from datetime import datetime
import getpass

from sarpy.annotation.base import AnnotationProperties, FileAnnotationCollection, \
    AnnotationFeature, AnnotationCollection
from sarpy.geometry.geometry_elements import Jsonable, Geometry, Point, MultiPoint, \
    LineString, MultiLineString, Polygon, MultiPolygon, GeometryCollection

_LABEL_VERSION = "Label:1.0"
logger = logging.getLogger(__name__)
POSSIBLE_GEOMETRIES = ('point', 'line', 'polygon')


class LabelSchema(object):
    """
    The basic structure for an annotation/labelling schema.

    The label names may certainly be modified in place through use of the `labels`
    property, without worry for causing errors. This is discouraged, because having two
    schemas with same version number/ids and differing names can likely lead to confusion.

    Any modification of label ids of sub-id structure should be performed by using the
    :func:`set_labels_and_subtypes` method, or difficult to diagnose runtime errors
    will likely be introduced.
    """

    __slots__ = (
        '_version', '_labels', '_classification', '_version_date', '_subtypes',
        '_parent_types', '_confidence_values', '_permitted_geometries',
        '_integer_ids', '_maximum_id')

    def __init__(
            self,
            version: Optional[str] = '1.0',
            labels: Optional[Dict[str, str]] = None,
            version_date: Optional[str] = None,
            classification: str = "UNCLASSIFIED",
            subtypes: Optional[Dict[str, List[str]]] = None,
            confidence_values: Optional[List[Union[int, str]]] = None,
            permitted_geometries: Optional[List[str]] = None):
        """

        Parameters
        ----------
        version : None|str
            The version of the schema.
        labels : None|Dict[str, str]
            The {<label id> : <label name>} pair dictionary. Each entry must be a string,
            and '' is not a valid label id.
        version_date : None|str
            The date for this schema. If `None`, then the current time will be used.
        classification : str
            The classification for this schema.
        subtypes : None|Dict[str, List[str]]
            The {<label id> : <sub id list>} pairs. The root ids (i.e. those ids
            not belonging as sub-id to some other id) will be populated in the subtypes
            entry with empty string key (i.e. ''). Every key and entry of subtypes
            (excluding the subtypes root '') must correspond to an entry of labels,
            and no id can be a direct subtype of more than one id.
        confidence_values : None|List[Union[str, int]]
            The possible confidence values.
        permitted_geometries : None|List[str]
            The possible geometry types.
        """

        self._version_date = None
        self._labels = None
        self._subtypes = None
        self._parent_types = None
        self._confidence_values = None
        self._permitted_geometries = None
        self._integer_ids = True
        self._maximum_id = None  # type: Union[None, int]

        self._version = version
        self.update_version_date(value=version_date)
        self._classification = classification

        self.confidence_values = confidence_values
        self.permitted_geometries = permitted_geometries
        self.set_labels_and_subtypes(labels, subtypes)

    @property
    def version(self) -> str:
        """
        The version of the schema.

        Returns
        -------
        str
        """
        pass

    @property
    def version_date(self) -> str:
        """
        The date for this schema version - this should be a viable datetime format,
        but this is unenforced.

        Returns
        -------
        str
        """
        pass

    def update_version_date(self, value: Optional[str] = None):
        pass

    @property
    def classification(self) -> str:
        """
        str: The classification for the contents of this schema.
        """
        pass

    @property
    def suggested_next_id(self) -> Optional[int]:
        """
        None|int: If all ids are integer type, this returns max_id+1. Otherwise, this
        yields None.
        """
        pass

    @property
    def labels(self) -> Dict[str, str]:
        """
        The complete label dictionary of the form `{label_id : label_name}`.

        Returns
        -------
        Dict[str, str]
        """
        pass

    @property
    def subtypes(self) -> Dict[str, List[str]]:
        """
        The complete dictionary of subtypes of the form `{parent_id : <subids list>}`.

        Returns
        -------
        Dict[str, List[str]]
        """
        pass

    @property
    def parent_types(self) -> Dict[str, List[str]]:
        """
        The dictionary of parent types of the form `{child_id : <set of parent ids>}`.
        It is canonically defined that an id is a parent of itself. The order of
        the `parent_ids` list is ascending order of parentage, i.e.
        `[<self>, <parent>, <parent of parent>, ...]`.

        Returns
        -------
        Dict[str, List[str]]
        """
        pass

    @property
    def confidence_values(self) -> List[Union[int, str]]:
        """
        The list of confidence values.

        Returns
        -------
        List
            Each element should be a json type (most likely use cases are str or int).
        """
        pass

    @confidence_values.setter
    def confidence_values(self, conf_values):
        pass

    @property
    def permitted_geometries(self) -> Optional[List[str]]:
        """
        The collection of permitted geometry types. None corresponds to all.
        Entries should be one of `{'point', 'line', 'polygon'}`.

        Returns
        -------
        None|List[str]
        """
        pass

    @permitted_geometries.setter
    def permitted_geometries(self, values):
        pass

    def get_id_from_name(self, the_name: str) -> Optional[str]:
        """
        Determine the id from the given name. Get `None` if this fails.

        Parameters
        ----------
        the_name : str

        Returns
        -------
        None|str
        """
        pass

    def get_parent(self, the_id: str) -> str:
        """
        Get the parent id for the given element id. The empty string is returned
        for elements with no parent.

        Parameters
        ----------
        the_id : str

        Returns
        -------
        str
        """
        pass

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), indent=1)

    def __repr__(self) -> str:
        return json.dumps(self.to_dict())

    def _inspect_new_id_for_integer(self, the_id: Union[int, str]) -> None:
        pass

    def _inspect_ids_for_integer(self) -> None:
        pass

    @staticmethod
    def _find_inverted_fork(
            subtypes: Dict[str, List[str]],
            labels: Dict[str, str]) -> Dict[str, List[str]]:
        """
        Look for parents claiming the same child. This assigns all unclaimed children
        to '' parent.

        Parameters
        ----------
        subtypes : dict
        labels : dict

        Returns
        -------
        dict
        """
        pass

    @staticmethod
    def _find_cycle(subtypes: Dict[str, List[str]]) -> None:
        """
        Find any cycles in the data.

        Parameters
        ----------
        subtypes

        Returns
        -------
        None
        """
        pass

    def set_labels_and_subtypes(
            self,
            labels: Dict[str, str],
            subtypes: Dict[str, List[str]]) -> None:
        """
        Set the labels and subtypes. **Note that subtypes may be modified in place.**

        Parameters
        ----------
        labels : None|dict
        subtypes : None|dict

        Returns
        -------
        None
        """
        pass

    def _construct_parent_types(self) -> None:
        pass

    def _validate_entry(
            self,
            the_id: str,
            the_name: str,
            the_parent: str) -> Tuple[str, str, str]:
        """
        Validate the basics for the given entry.

        Parameters
        ----------
        the_id : str
        the_name : str
        the_parent : str

        Returns
        -------
        the_id: str
        the_name: str
        the_parent: str
        """
        pass

    def add_entry(
            self,
            the_id: str,
            the_name: str,
            the_parent: str = '') -> None:
        """
        Adds a new entry. Note that leading or trailing blanks will be trimmed
        from all input values.

        Parameters
        ----------
        the_id : str
            The id for the label.
        the_name : str
            The name for the label.
        the_parent : str
            The parent id, where blank denotes no parent.

        Returns
        -------
        None
        """
        pass

    def change_entry(
            self,
            the_id: str,
            the_name: str,
            the_parent: str) -> bool:
        """
        Modify the values for a schema element.

        Parameters
        ----------
        the_id : str
        the_name : str
        the_parent : str

        Returns
        -------
        bool
            True if anything was actually changed. False otherwise.
        """
        pass

    def delete_entry(
            self,
            the_id: str,
            recursive: bool = False) -> None:
        """
        Deletes the entry from the schema.

        If the given element has children and `recursive=False`, a ValueError
        will be raised. If the given element has children and `recursive=True`,
        then all children will be deleted.

        Parameters
        ----------
        the_id : str
        recursive : bool
        """
        pass

    def reorder_child_element(
            self,
            the_id: str,
            spaces: int = 1) -> bool:
        """
        Move the one space (forward or backward) in the list of children for the
        current parent. This is explicitly changes no actual parent/child
        relationships, and only changes the child list ORDERING.

        Parameters
        ----------
        the_id : str
        spaces : int
            How many spaces to shift the entry.

        Returns
        -------
        bool
            True of something actually changed, False otherwise.
        """
        pass

    @classmethod
    def from_file(cls, file_name: str):
        """
        Read schema from a file.

        Parameters
        ----------
        file_name : str

        Returns
        -------
        LabelSchema
        """

        with open(file_name, 'r') as fi:
            input_dict = json.load(fi)
        return cls.from_dict(input_dict)

    @classmethod
    def from_dict(cls, input_dict: Dict):
        """
        Construct from a dictionary.

        Parameters
        ----------
        input_dict : dict

        Returns
        -------
        LabelSchema
        """

        version = input_dict['version']
        labels = input_dict['labels']
        version_date = input_dict.get('version_date', None)
        classification = input_dict.get('classification', 'UNCLASSIFIED')
        subtypes = input_dict.get('subtypes', None)
        conf_values = input_dict.get('confidence_values', None)
        perm_geometries = input_dict.get('permitted_geometries', None)
        return cls(
            version, labels, version_date=version_date, classification=classification,
            subtypes=subtypes, confidence_values=conf_values, permitted_geometries=perm_geometries)

    def to_dict(self) -> Dict:
        """
        Serialize to a dictionary representation.

        Returns
        -------
        dict
        """

        out = OrderedDict()
        out['version'] = self.version
        out['version_date'] = self.version_date
        out['classification'] = self.classification
        if self.confidence_values is not None:
            out['confidence_values'] = self.confidence_values
        if self.permitted_geometries is not None:
            out['permitted_geometries'] = self.permitted_geometries
        out['labels'] = self._labels
        out['subtypes'] = self._subtypes
        return out

    def to_file(self, file_name: str) -> None:
        """
        Write to a (json) file.

        Parameters
        ----------
        file_name : str

        Returns
        -------
        None
        """
        pass

    def is_valid_confidence(self, value: List) -> bool:
        """
        Is the given value a valid confidence (i.e. is in `confidence_values`)?
        Note that `None` is always considered valid here.

        Parameters
        ----------
        value

        Returns
        -------
        bool
        """
        pass

    def is_valid_geometry(self, value: List) -> bool:
        """
        Is the given geometry type allowed (i.e. is in `permitted_geometries`)?
        Note that `None` is always considered valid here.

        Parameters
        ----------
        value : str|Geometry

        Returns
        -------
        bool
        """
        pass


##########
# elements for labeling a feature

class LabelMetadata(Jsonable):
    """
    Basic annotation metadata building block - everything but the geometry object
    """

    __slots__ = ('label_id', 'user_id', 'comment', 'confidence', 'timestamp')
    _type = 'LabelMetadata'

    def __init__(
            self,
            label_id: Optional[str] = None,
            user_id: Optional[str] = None,
            comment: Optional[str] = None,
            confidence: Union[None, int, str] = None,
            timestamp: Union[None, int, float] = None):
        """

        Parameters
        ----------
        label_id : None|str
            The label id
        user_id : None|str
            The user id - will default to current user name
        comment : None|str
        confidence : None|str|int
            The confidence value
        timestamp : None|float|int
            The POSIX timestamp (in seconds) - should be construction time.
        """

        self.label_id = label_id  # type: Union[None, str]
        if user_id is None:
            user_id = getpass.getuser()
        self.user_id = user_id  # type: str
        self.comment = comment  # type: Union[None, str]
        self.confidence = confidence  # type: Union[None, str, int]

        if timestamp is None:
            timestamp = time.time()
        if not isinstance(timestamp, float):
            timestamp = float(timestamp)
        self.timestamp = timestamp  # type: float

    @classmethod
    def from_dict(cls, the_json: Dict):
        typ = the_json['type']
        if typ != cls._type:
            raise ValueError('LabelMetadata cannot be constructed from {}'.format(the_json))
        return cls(
            label_id=the_json.get('label_id', None),
            user_id=the_json.get('user_id', None),
            comment=the_json.get('comment', None),
            confidence=the_json.get('confidence', None),
            timestamp=the_json.get('timestamp', None))

    def to_dict(self, parent_dict: Optional[Dict] = None):
        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        for attr in self.__slots__:
            parent_dict[attr] = getattr(self, attr)
        return parent_dict

    def replicate(self):
        pass


class LabelMetadataList(Jsonable):
    """
    The collection of LabelMetadata elements.
    """

    __slots__ = ('_elements', )
    _type = 'LabelMetadataList'

    def __init__(self, elements: Union[None, List[LabelMetadata], Dict] = None):
        """

        Parameters
        ----------
        elements : None|List[LabelMetadata|dict]
        """

        self._elements = None
        if elements is not None:
            self.elements = elements

    def __len__(self):
        if self._elements is None:
            return 0
        return len(self._elements)

    def __getitem__(self, item):
        # type: (Any) -> LabelMetadata
        if self._elements is None:
            raise StopIteration
        return self._elements[item]

    @property
    def elements(self) -> Optional[List[LabelMetadata]]:
        """
        The LabelMetadata elements.

        Returns
        -------
        None|List[LabelMetadata]
        """
        pass

    @elements.setter
    def elements(self, elements):
        pass

    def insert_new_element(self, element: LabelMetadata) -> None:
        """
        Inserts an element at the head of the elements list.

        Parameters
        ----------
        element : LabelMetadata

        Returns
        -------
        None
        """
        pass

    @classmethod
    def from_dict(cls, the_json):
        # type: (dict) -> LabelMetadataList
        typ = the_json['type']
        if typ != cls._type:
            raise ValueError('LabelMetadataList cannot be constructed from {}'.format(the_json))
        return cls(elements=the_json.get('elements', None))

    def to_dict(self, parent_dict: Optional[Dict] = None):
        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        if self._elements is None:
            parent_dict['elements'] = None
        else:
            parent_dict['elements'] = [entry.to_dict() for entry in self._elements]
        return parent_dict

    def replicate(self):  # type: () ->  LabelMetadataList
        pass

    def get_label_id(self) -> Optional[str]:
        """
        Gets the current label id.

        Returns
        -------
        None|str
        """
        pass


class LabelProperties(AnnotationProperties):
    _type = 'LabelProperties'

    @property
    def parameters(self):
        """
        LabelMetadataList: The parameters
        """
        pass

    @parameters.setter
    def parameters(self, value):
        pass

    def get_label_id(self):
        """
        Gets the current label id.

        Returns
        -------
        None|str
        """
        pass


############
# the feature extensions

class LabelFeature(AnnotationFeature):
    """
    A specific extension of the Feature class which has the properties attribute
    populated with LabelProperties instance.
    """

    @property
    def properties(self):
        """
        The properties.

        Returns
        -------
        None|LabelProperties
        """
        pass

    @properties.setter
    def properties(self, properties):
        pass

    def add_annotation_metadata(self, value):
        """
        Adds the new label to the series of labeling efforts.

        Parameters
        ----------
        value : LabelMetadata
        """
        pass

    def get_label_id(self):
        """
        Gets the label id.

        Returns
        -------
        None|str
        """
        pass


class LabelCollection(AnnotationCollection):
    """
    A specific extension of the FeatureCollection class which has the features are
    LabelFeature instances.
    """

    @property
    def features(self):
        """
        The features list.

        Returns
        -------
        List[LabelFeature]
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
        feature : LabelFeature
        """
        pass

    def __getitem__(self, item):
        # type: (Any) -> Union[LabelFeature, List[LabelFeature]]
        if self._features is None:
            raise StopIteration

        if isinstance(item, str):
            index = self._feature_dict[item]
            return self._features[index]
        return self._features[item]


###########
# serialized file object

class FileLabelCollection(FileAnnotationCollection):
    """
    An collection of annotation elements associated with a given single image element file.
    """

    __slots__ = (
        '_version', '_label_schema', '_image_file_name', '_image_id', '_core_name', '_annotations')
    _type = 'FileLabelCollection'

    def __init__(self, label_schema, version=None, annotations=None,
                 image_file_name=None, image_id=None, core_name=None):
        if version is None:
            version = _LABEL_VERSION

        if isinstance(label_schema, str):
            label_schema = LabelSchema.from_file(label_schema)
        elif isinstance(label_schema, dict):
            label_schema = LabelSchema.from_dict(label_schema)
        if not isinstance(label_schema, LabelSchema):
            raise TypeError('label_schema must be an instance of a LabelSchema.')
        self._label_schema = label_schema

        FileAnnotationCollection.__init__(
            self, version=version, annotations=annotations, image_file_name=image_file_name,
            image_id=image_id, core_name=core_name)

    @property
    def label_schema(self):
        """
        The label schema.

        Returns
        -------
        LabelSchema
        """
        pass

    @property
    def annotations(self):
        """
        The annotations.

        Returns
        -------
        LabelCollection
        """
        pass

    @annotations.setter
    def annotations(self, annotations):
        # type: (Union[None, LabelCollection, dict]) -> None
        pass

    def add_annotation(self, annotation, validate_confidence=True, validate_geometry=True):
        """
        Add an annotation, with a check for valid values in confidence and geometry type.

        Parameters
        ----------
        annotation : LabelFeature
            The prospective annotation.
        validate_confidence : bool
            Should we check that all confidence values follow the schema?
        validate_geometry : bool
            Should we check that all geometries are of allowed type?

        Returns
        -------
        None
        """
        pass

    def is_annotation_valid(self, annotation):
        """
        Is the given annotation valid according to the schema?

        Parameters
        ----------
        annotation : LabelFeature

        Returns
        -------
        bool
        """
        pass

    def _valid_confidences(self, annotation):
        pass

    def _valid_geometry(self, annotation):
        pass

    def validate_annotations(self, strict=True):
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
        FileLabelCollection
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
        FileLabelCollection
        """

        if not isinstance(the_dict, dict):
            raise TypeError('This requires a dict. Got type {}'.format(type(the_dict)))
        if 'label_schema' not in the_dict:
            raise KeyError('this dictionary must contain a label_schema')

        typ = the_dict.get('type', 'NONE')
        if typ != cls._type:
            raise ValueError('FileLabelCollection cannot be constructed from the input dictionary')

        return cls(
            the_dict['label_schema'],
            version=the_dict.get('version', 'UNKNOWN'),
            annotations=the_dict.get('annotations', None),
            image_file_name=the_dict.get('image_file_name', None),
            image_id=the_dict.get('image_id', None),
            core_name=the_dict.get('core_name', None))

    def to_dict(self, parent_dict=None):
        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        parent_dict['version'] = self.version
        parent_dict['label_schema'] = self.label_schema.to_dict()
        if self.image_file_name is not None:
            parent_dict['image_file_name'] = self.image_file_name
        if self.image_id is not None:
            parent_dict['image_id'] = self.image_id
        if self.core_name is not None:
            parent_dict['core_name'] = self.core_name
        if self.annotations is not None:
            parent_dict['annotations'] = self.annotations.to_dict()
        return parent_dict
