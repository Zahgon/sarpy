"""
Base annotation types for general use - based on the geojson implementation
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"

from collections import OrderedDict
import json
import logging
import os
from typing import Optional, Dict, List, Any, Union
from uuid import uuid4

from sarpy.geometry.geometry_elements import Jsonable, FeatureCollection, Feature, \
    GeometryCollection, GeometryObject, Geometry, basic_assemble_from_collection


_BASE_VERSION = "Base:1.0"

logger = logging.getLogger(__name__)


class GeometryProperties(Jsonable):
    __slots__ = ('_uid', '_name', '_color')
    _type = 'GeometryProperties'

    def __init__(self, uid=None, name=None, color=None):
        self._name = None
        self._color = None

        if uid is None:
            uid = str(uuid4())
        if not isinstance(uid, str):
            raise TypeError('uid must be a string, got {}'.format(type(uid)))
        self._uid = uid

        self.name = name
        self.color = color

    @property
    def uid(self):
        """
        str: A unique identifier for the associated geometry element
        """
        pass

    @property
    def name(self):
        """
        Optional[str]: The name
        """
        pass

    @name.setter
    def name(self, value):
        pass

    @property
    def color(self):
        """
        Optional[str]: The color
        """
        pass

    @color.setter
    def color(self, value):
        pass

    @classmethod
    def from_dict(cls, the_json):
        """
        Deserialize from json.

        Parameters
        ----------
        the_json : Dict

        Returns
        -------
        GeometryProperties
        """
        
        if not isinstance(the_json, dict):
            raise TypeError('This requires a dict. Got type {}'.format(type(the_json)))
        
        typ = the_json.get('type', None) # prevents key error from being thrown if 'type' isn't in the_json
        
        if typ is None:
            raise KeyError("the json requires the field 'type'")
        
        if typ != cls._type:
            raise ValueError('GeometryProperties cannot be constructed from {}, expecting {}'.format(typ, cls._type))

        return cls(
            uid=the_json.get('uid', None),
            name=the_json.get('name', None),
            color=the_json.get('color', None))

    def to_dict(self, parent_dict=None):
        """
        Serialize to json.

        Parameters
        ----------
        parent_dict : None|Dict

        Returns
        -------
        Dict
        """

        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        parent_dict['uid'] = self.uid
        if self.name is not None:
            parent_dict['name'] = self.name
        if self.color is not None:
            parent_dict['color'] = self.color
        return parent_dict


class AnnotationProperties(Jsonable):
    """
    The basic common properties for an annotation
    """

    __slots__ = ('_name', '_description', '_directory', '_geometry_properties', '_parameters')
    _type = 'AnnotationProperties'

    def __init__(self, name=None, description=None, directory=None,
                 geometry_properties=None, parameters=None):
        """

        Parameters
        ----------
        name : Optional[str]
        description : Optional[str]
        directory : Optional[str]
        geometry_properties : None|List[GeometryProperties]
        parameters : Optional[Jsonable]
        """

        self._name = None
        self._description = None
        self._directory = None
        self._geometry_properties = []
        self._parameters = None

        self.name = name
        self.description = description
        self.directory = directory
        self.geometry_properties = geometry_properties
        self.parameters = parameters

    @property
    def name(self):
        """
        Optional[str]: The name
        """
        pass

    @name.setter
    def name(self, value):
        pass

    @property
    def description(self):
        """
        Optional[str]: The description
        """
        pass

    @description.setter
    def description(self, value):
        pass

    @property
    def directory(self):
        """
        Optional[str]: The directory - for basic display and/or subdivision purposes
        """
        pass

    @directory.setter
    def directory(self, value):
        pass

    @property
    def geometry_properties(self):
        # type: () -> List[GeometryProperties]
        """
        List[GeometryProperties]: The geometry properties.
        """
        pass

    @geometry_properties.setter
    def geometry_properties(self, value):
        pass

    def add_geometry_property(self, entry):
        """
        Add a geometry property to the list.

        .. warning::

            Care should be taken that this list stay in sync with the parent geometry.

        Parameters
        ----------
        entry: Dict|GeometryProperties
            The geometry properties instance of serialized version of it.
        """
        pass

    def get_geometry_property(self, item):
        """
        Fetches the appropriate geometry property.

        Parameters
        ----------
        item : int|str
            The geometry properties uid or integer index.

        Returns
        -------
        GeometryProperties

        Raises
        ------
        KeyError
        """
        pass

    def get_geometry_property_and_index(self, item):
        """
        Fetches the appropriate geometry property and its integer index.

        Parameters
        ----------
        item : int|str
            The geometry properties uid or integer index.

        Returns
        -------
        (GeometryProperties, int)

        Raises
        ------
        KeyError
        """
        pass

    @property
    def parameters(self):
        """
        Optional[Jsonable]: The parameters
        """
        pass

    @parameters.setter
    def parameters(self, value):
        pass

    @classmethod
    def from_dict(cls, the_json):
        """
        Deserialize from json.

        Parameters
        ----------
        the_json : Dict

        Returns
        -------
        AnnotationProperties
        """

        if not isinstance(the_json, dict):
            raise TypeError('This requires a dict. Got type {}'.format(type(the_json)))

        typ = the_json.get('type', None) # prevents key error from being thrown if 'type' isn't in the_json
        
        if typ is None:
            raise KeyError("the json requires the field 'type'")
        
        if typ != cls._type:
            raise ValueError('AnnotationProperties cannot be constructed from {}, expecting {}'.format(typ, cls._type))
        
        return cls(
            name=the_json.get('name', None),
            description=the_json.get('description', None),
            directory=the_json.get('directory', None),
            geometry_properties=the_json.get('geometry_properties', None),
            parameters=the_json.get('parameters', None))

    def to_dict(self, parent_dict=None):
        """
        Serialize to json.

        Parameters

        ----------
        parent_dict : None|Dict

        Returns
        -------
        Dict
        """

        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        for field in ['name', 'description', 'directory']:
            value = getattr(self, field)
            if value is not None:
                parent_dict[field] = value

        if self.geometry_properties is not None:
            parent_dict['geometry_properties'] = [entry.to_dict() for entry in self.geometry_properties]
        if self.parameters is not None:
            parent_dict['parameters'] = self.parameters.to_dict()
        return parent_dict

    def replicate(self):
        pass


class AnnotationFeature(Feature):
    """
    An extension of the Feature class which has the properties attribute
    populated with AnnotationProperties instance.
    """
    _allowed_geometries = None
    _type = "AnnotationFeature"

    @property
    def properties(self):
        """
        The properties.

        Returns
        -------
        None|AnnotationProperties
        """
        pass

    @properties.setter
    def properties(self, properties):
        pass

    def get_name(self):
        """
        Gets a useful name.

        Returns
        -------
        str
        """
        pass

    @property
    def geometry(self):
        """
        The geometry object.

        Returns
        -------
        GeometryObject|GeometryCollection
        """
        pass

    @geometry.setter
    def geometry(self, geometry):
        pass

    @property
    def geometry_count(self):
        """
        int: The number of base geometry elements
        """
        pass

    def get_geometry_name(self, item):
        """
        Gets the name, or a reasonable default, for the geometry.

        Parameters
        ----------
        item : int|str

        Returns
        -------
        str
        """
        pass

    def get_geometry_property(self, item):
        """
        Gets the geometry properties object for the given index/uid.

        Parameters
        ----------
        item : int|str
            The geometry properties uid or integer index.

        Returns
        -------
        GeometryProperties

        Raises
        ------
        KeyError
        """
        pass

    def get_geometry_property_and_index(self, item):
        """
        Gets the geometry properties object and integer index for the given index/uid.

        Parameters
        ----------
        item : int|str
            The geometry properties uid or integer index.

        Returns
        -------
        (GeometryProperties, int)

        Raises
        ------
        KeyError
        """
        pass

    def get_geometry_and_geometry_properties(self, item):
        """
        Gets the geometry and geometry properties object for the given index/uid.

        Parameters
        ----------
        item : int|str
            The geometry properties uid or integer index.

        Returns
        -------
        (Point|Line|Polygon, GeometryProperties)

        Raises
        ------
        KeyError
        """
        pass

    def get_geometry_element(self, item):
        """
        Gets the basic geometry object at the given index.

        Parameters
        ----------
        item : int|str
            The integer index or associated geometry properties uid.

        Returns
        -------
        Point|Line|Polygon

        Raises
        ------
        ValueError|KeyError
        """
        pass

    def _validate_geometry_element(self, geometry):
        pass

    def add_geometry_element(self, geometry, properties=None):
        """
        Adds the given geometry to the feature geometry (collection).

        Parameters
        ----------
        geometry : GeometryObject
        properties : None|GeometryProperties
        """
        pass

    def remove_geometry_element(self, item):
        """
        Remove the geometry element at the given index

        Parameters
        ----------
        item : int|str
        """
        pass

    @classmethod
    def from_dict(cls, the_json):
        if not isinstance(the_json, dict):
            raise TypeError('This requires a dict. Got type {}'.format(type(the_json)))

        typ = the_json.get('type', None) # prevents key error from being thrown if 'type' isn't in the_json
        
        if typ is None:
            raise KeyError("the json requires the field 'type'")

        if typ != cls._type:
            raise ValueError('AnnotationFeature cannot be constructed from {}, expecting {}'.format(typ, cls._type))

        the_id = the_json.get('id', None)
        if the_id is None:
            the_id = the_json.get('uid', None)

        return cls(uid=the_id,
                   geometry=the_json.get('geometry', None),
                   properties=the_json.get('properties', None))

class AnnotationCollection(FeatureCollection):
    """
    An extension of the FeatureCollection class which has the features are
    AnnotationFeature instances.
    """
    _type = "AnnotationCollection"

    @property
    def features(self):
        """
        The features list.

        Returns
        -------
        List[AnnotationFeature]
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
        feature : AnnotationFeature|Dict
        """
        pass

    def __getitem__(self, item):
        # type: (Any) -> Union[AnnotationFeature, List[AnnotationFeature]]
        if self._features is None:
            raise StopIteration

        if isinstance(item, str):
            index = self._feature_dict[item]
            return self._features[index]
        return self._features[item]
    
    @classmethod
    def from_dict(cls, the_json):
        if not isinstance(the_json, dict):
            raise TypeError('This requires a dict. Got type {}'.format(type(the_json)))

        typ = the_json.get('type', None) # prevents key error from being thrown if 'type' isn't in the_json
        
        if typ is None:
            raise KeyError("the json requires the field 'type'")

        if typ != cls._type:
            raise ValueError('AnnotationCollection cannot be constructed from {}, expecting {}'.format(typ, cls._type))

        features = the_json.get('features', None)
        if features is None:
            feature_list = None
        else:
            feature_list = [AnnotationFeature.from_dict(entry) for entry in features]

        return cls(features=feature_list)


class FileAnnotationCollection(Jsonable):
    """
    An collection of annotation elements associated with a given single image element file.
    """

    __slots__ = (
         '_version', '_image_file_name', '_image_id', '_core_name', '_annotations')
    _type = 'FileAnnotationCollection'

    def __init__(self, version=None, annotations=None, image_file_name=None, image_id=None, core_name=None):
        if version is None:
            version = _BASE_VERSION
        self._version = version
        self._annotations = None

        if image_file_name is None:
            self._image_file_name = None
        elif isinstance(image_file_name, str):
            self._image_file_name = os.path.split(image_file_name)[1]
        else:
            raise TypeError('image_file_name must be a None or a string')

        self._image_id = image_id
        self._core_name = core_name

        if self._image_file_name is None and self._image_id is None and self._core_name is None:
            logger.error('One of image_file_name, image_id, or core_name should be defined.')

        self.annotations = annotations

    @property
    def version(self):
        """
        str: The version
        """
        pass

    @property
    def image_file_name(self):
        """
        The image file name, if appropriate.

        Returns
        -------
        None|str
        """
        pass

    @property
    def image_id(self):
        """
        The image id, if appropriate.

        Returns
        -------
        None|str
        """
        pass

    @property
    def core_name(self):
        """
        The image core name, if appropriate.

        Returns
        -------
        None|str
        """
        pass

    @property
    def annotations(self):
        """
        The annotations.

        Returns
        -------
        AnnotationCollection
        """
        pass

    @annotations.setter
    def annotations(self, annotations):
        # type: (Union[None, AnnotationCollection, Dict]) -> None
        pass

    def add_annotation(self, annotation):
        """
        Add an annotation.

        Parameters
        ----------
        annotation : AnnotationFeature
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
        FileAnnotationCollection
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
        FileAnnotationCollection
        """

        if not isinstance(the_dict, dict):
            raise TypeError('This requires a dict. Got type {}'.format(type(the_dict)))

        typ = the_dict.get('type', 'NONE')
        if typ != cls._type:
            raise ValueError('FileAnnotationCollection cannot be constructed from {}, expecting {}'.format(typ, cls._type))


        return cls(
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
        if self.image_file_name is not None:
            parent_dict['image_file_name'] = self.image_file_name
        if self.image_id is not None:
            parent_dict['image_id'] = self.image_id
        if self.core_name is not None:
            parent_dict['core_name'] = self.core_name
        if self.annotations is not None:
            parent_dict['annotations'] = self.annotations.to_dict()
        return parent_dict

    def to_file(self, file_name):
        pass
