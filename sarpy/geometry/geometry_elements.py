"""
This module provides basic geometry elements generally geared towards (geo)json usage.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"

import copy
from collections import OrderedDict
from uuid import uuid4
from typing import Union, List, Tuple, Dict, Callable, Any
import json
import logging

import numpy


logger = logging.getLogger(__name__)

_poorly_formed_text = 'Poorly formed json {}'
_disallowed_text = 'Got disallowed type {}'

##########
# utility functions


def _compress_identical(coords):
    """
    Eliminate consecutive points with same first two coordinates.

    Parameters
    ----------
    coords : numpy.ndarray

    Returns
    -------
    numpy.ndarray
        coords array with consecutive identical points supressed (last point retained)
    """
    pass


def _validate_contain_arguments(pts_x, pts_y):
    # helper method for Polygon functionality
    if not isinstance(pts_x, numpy.ndarray):
        pts_x = numpy.array(pts_x, dtype=numpy.float64)
    if not isinstance(pts_y, numpy.ndarray):
        pts_y = numpy.array(pts_y, dtype=numpy.float64)

    if pts_x.shape != pts_y.shape:
        raise ValueError(
            'pts_x and pts_y must be the same shape. Got {} and {}'.format(pts_x.shape, pts_y.shape))
    return pts_x, pts_y


def _validate_grid_contain_arguments(grid_x, grid_y):
    # helper method for Polygon functionality
    pass


def _get_kml_coordinate_string(coordinates, transform):
    # type: (numpy.ndarray, Union[None, Callable]) -> str
    pass


def _line_segments_intersect(pt0, pt1, pt2, pt3):
    """
    Does line segment defined by points 0 & 1 internally intersect with line
    segment defined by points 2 & 3? For these purposes, co-linearity will be
    considered False.

    Parameters
    ----------
    pt0 : numpy.ndarray|list|tuple
    pt1 : numpy.ndarray|list|tuple
    pt2 : numpy.ndarray|list|tuple
    pt3 : numpy.ndarray|list|tuple

    Returns
    -------
    bool
    """
    pass


def _validate_point_array(point):
    """
    Extract array from point, or verify the input is consistent with point
    definition.

    Parameters
    ----------
    point : Point|numpy.ndarray|Tuple|List

    Returns
    -------
    numpy.ndarray
        A numpy.ndarray of shape `(N, )` with `N >= 2`.
    """

    if isinstance(point, Point):
        return point.coordinates
    if not isinstance(point, numpy.ndarray):
        point = numpy.array(point, dtype='float64')
    if point.ndim != 1 or point.size < 2:
        raise ValueError('point input must yield a one-dimensional array of at least two elements.')
    return point


def _line_segment_distance(line_coord, coord):
    """
    Get the (2-d) distance from the point given by coord from the line segment defined by line_coord.

    Parameters
    ----------
    line_coord : numpy.ndarray
        This is implicitly assumed to be shape (2, 2).
    coord : numpy.ndarray
        This is implicitly assumed to be shape (2,).

    Returns
    -------
    float
    """

    dir_vec = line_coord[1, :] - line_coord[0, :]  # direction vector for segment
    dir_vec /= numpy.linalg.norm(dir_vec)
    norm_vec = numpy.array([dir_vec[1], -dir_vec[0]])
    diff_vec0 = coord - line_coord[0, :]  # vector from first end to point
    diff_vec1 = coord - line_coord[1, :]  # vector from last end to point

    if numpy.sign(diff_vec1.dot(dir_vec)) == numpy.sign(diff_vec0.dot(dir_vec)):
        # one of the endpoints is the minimum distance
        return min(float(numpy.linalg.norm(diff_vec0)), float(numpy.linalg.norm(diff_vec1)))
    else:
        # the point is "between" the two endpoints
        return float(numpy.abs(diff_vec1.dot(norm_vec)))


###############
# Geojson base object

class Jsonable(object):
    """
    Abstract class for json serializability.
    """
    _type = 'Jsonable'

    @property
    def type(self):
        """
        The type identifier.

        Returns
        -------
        str
        """
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

        """

        raise NotImplementedError

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

        raise NotImplementedError

    def __str__(self):
        return '{}(**{})'.format(self.__class__.__name__, json.dumps(self.to_dict(), indent=1))

    def __repr__(self):
        return '{}(**{})'.format(self.__class__.__name__, self.to_dict())

    def copy(self):
        """
        Make a deep copy of the item.

        Returns
        -------

        """

        the_type = self.__class__
        return the_type.from_dict(self.to_dict())

    def replicate(self):
        """
        Make a replica of the item, where uid has not been copied.

        Returns
        -------

        """
        pass


#######
# Geojson object definitions

class Feature(Jsonable):
    """
    Generic feature class - basic geojson functionality. Should generally be extended
    to coherently handle properties for specific use case.
    """

    __slots__ = ('_uid', '_geometry', '_properties')
    _type = 'Feature'

    def __init__(self, uid=None, geometry=None, properties=None):
        self._geometry = None
        self._properties = None

        self.geometry = geometry
        self.properties = properties

        if uid is None and isinstance(properties, dict):
            uid = properties.get('identifier', None)

        if uid is None:
            self._uid = str(uuid4())
        elif not isinstance(uid, str):
            raise TypeError('uid must be a string.')
        else:
            self._uid = uid

    @property
    def uid(self):
        """
        The feature unique identifier.

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
    def properties(self):  # type: () -> Union[None, int, float, str, list, dict, Jsonable]
        """
        The properties.

        Returns
        -------
        None|int|float|str|dict|list|Jsonable: The properties.
        """
        pass

    @properties.setter
    def properties(self, properties):
        pass

    @classmethod
    def from_dict(cls, the_json):
        typ = the_json['type']
        if typ != cls._type:
            raise ValueError('Feature cannot be constructed from {}'.format(the_json))

        the_id = the_json.get('id', None)
        if the_id is None:
            the_id = the_json.get('uid', None)

        return cls(uid=the_id,
                   geometry=the_json.get('geometry', None),
                   properties=the_json.get('properties', None))

    def to_dict(self, parent_dict=None):
        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        parent_dict['id'] = self.uid

        if self.geometry is not None:
            parent_dict['geometry'] = self.geometry.to_dict()

        if self.properties is not None:
            if isinstance(self.properties, (int, float, str, list, dict)):
                parent_dict['properties'] = self.properties
            elif isinstance(self.properties, Jsonable):
                parent_dict['properties'] = self.properties.to_dict()
            else:
                logger.warning(
                    'Got unexpected Feature properties type `{}`,'
                    '\n\tnot serializing'.format(type(self.properties)))
        return parent_dict

    def add_to_kml(self, doc, coord_transform, parent=None):
        """
        Add this feature to the kml document. **Note that coordinates or transformed
        coordinates are assumed to be WGS-84 coordinates in longitude, latitude order.**
        Currently only the first two (i.e. longitude and latitude) are used in
        this export.

        Parameters
        ----------
        doc : sarpy.io.kml.Document
        coord_transform : None|callable
            If callable, the the transform will be applied to the coordinates before
            adding to the document.
        parent : None|minidom.Element
            The parent node.

        Returns
        -------
        None
        """
        pass

    def replicate(self):
        pass


class FeatureCollection(Jsonable):
    """
    Generic FeatureCollection class - basic geojson functionality. Should generally be
    extended to coherently handle specific Feature extension.
    """

    __slots__ = ('_features', '_feature_dict')
    _type = 'FeatureCollection'

    def __init__(self, features=None):
        self._features = None
        self._feature_dict = None
        if features is not None:
            self.features = features

    def __len__(self):
        if self._features is None:
            return 0
        return len(self._features)

    def __getitem__(self, item):
        # type: (Any) -> Union[Feature, List[Feature]]
        if self._features is None:
            raise StopIteration

        if isinstance(item, str):
            index = self._feature_dict[item]
            return self._features[index]
        return self._features[item]

    def __delitem__(self, item):
        # type: (Any) -> None
        if self._features is None:
            return

        if isinstance(item, Feature):
            item = Feature.uid
        if not isinstance(item, (str, int)):
            raise ValueError('Unexpected type `{}`'.format(type(item)))

        if isinstance(item, str):
            index = self._feature_dict[item]
            del self._features[index]
        else:
            del self._features[item]
        self._rebuild_feature_dict()

    @property
    def features(self):
        """
        The features list.

        Returns
        -------
        List[Feature]
        """
        pass

    @features.setter
    def features(self, features):
        pass

    def get_integer_index(self, feature_id):
        """
        Gets the integer index for the given feature id.

        Parameters
        ----------
        feature_id : str

        Returns
        -------
        int
        """
        pass

    def _rebuild_feature_dict(self):
        pass

    @classmethod
    def from_dict(cls, the_json):
        typ = the_json['type']
        if typ != cls._type:
            raise ValueError('FeatureCollection cannot be constructed from {}'.format(the_json))
        return cls(features=the_json['features'])

    def to_dict(self, parent_dict=None):
        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        if self._features is None:
            parent_dict['features'] = None
        else:
            parent_dict['features'] = [entry.to_dict() for entry in self._features]
        return parent_dict

    def add_feature(self, feature):
        """
        Add a feature.

        Parameters
        ----------
        feature : Feature

        Returns
        -------
        None
        """
        pass

    def export_to_kml(self, file_name, coord_transform=None, **params):
        """
        Export to a kml document. **Note that underlying geometry coordinates or
        transformed coordinates are assumed in longitude, latitude order.**
        Currently only the first two (i.e. longitude and latitude) are used in this export.

        Parameters
        ----------
        file_name : str|zipfile.ZipFile|file like
        coord_transform : None|callable
            The coordinate transform function.
        params : dict

        Returns
        -------
        None
        """
        pass

    def replicate(self):
        pass


class Geometry(Jsonable):
    """
    Abstract Geometry base class.
    """
    _type = 'Geometry'
    _is_collection = False

    @classmethod
    def from_dict(cls, geometry):
        """
        Deserialize from json.

        Parameters
        ----------
        geometry : Dict

        Returns
        -------

        """

        typ = geometry['type']
        if typ == 'GeometryCollection':
            obj = GeometryCollection.from_dict(geometry)
            return obj
        else:
            obj = GeometryObject.from_dict(geometry)
            return obj

    def to_dict(self, parent_dict=None):
        raise NotImplementedError

    def add_to_kml(self, doc, parent, coord_transform):
        """
        Add the geometry to the kml document. **Note that coordinates or transformed
        coordinates are assumed in longitude, latitude order.**

        Parameters
        ----------
        doc : sarpy.io.kml.Document
        parent : xml.dom.minidom.Element
        coord_transform : None|callable

        Returns
        -------
        None
        """

        raise NotImplementedError

    def apply_projection(self, proj_method):
        """
        Gets a new version after applying a transform method.

        Parameters
        ----------
        proj_method : callable

        Returns
        -------
        Geometry
        """

        raise NotImplementedError

    def get_bbox(self):
        """
        Get the bounding box list.

        Returns
        -------
        None|List
            Of the form [min coord 0, min coord 1, ..., max coord 0, max coord 1, ...]/
        """

        raise NotImplementedError

    @property
    def is_collection(self):
        """
        bool: Is this a collection object?
        """
        pass


class GeometryCollection(Geometry):
    """
    Geometry collection - following the geojson structure
    """

    __slots__ = ('_geometries', )
    _type = 'GeometryCollection'
    _is_collection = True

    def __init__(self, geometries=None):
        """

        Parameters
        ----------
        geometries : None|List[Geometry]
        """

        self._geometries = []
        if geometries is not None:
            self.geometries = geometries

    @property
    def collection(self):
        pass

    @property
    def geometries(self):
        # type: () -> List[Geometry]
        """
        List[Geometry]: The geometry collection.
        """
        pass

    @geometries.setter
    def geometries(self, geometries):
        pass

    def get_bbox(self):
        if self._geometries is None:
            return None

        mins = [None, None, None]
        maxs = [None, None, None]
        for geometry in self.geometries:
            t_bbox = geometry.get_bbox()
            coord_count = int(len(t_bbox)/2)
            for i in range(min(coord_count, 3)):
                entry = t_bbox[i]
                if mins[i] is None or entry < mins[i]:
                    mins[i] = entry
                entry = t_bbox[coord_count+i]
                if maxs[i] is None or entry > maxs[i]:
                    maxs[i] = entry
        if mins[2] is None:
            mins = mins[:2]
            maxs = maxs[:2]
        mins.extend(maxs)
        return mins

    @classmethod
    def from_dict(cls, geometry):
        # type: (Union[None, Dict]) -> GeometryCollection
        typ = geometry.get('type', None)
        if typ != cls._type:
            raise ValueError('GeometryCollection cannot be constructed from {}'.format(geometry))

        geometries = []
        if geometry['geometries'] is not None:
            for entry in geometry['geometries']:
                if isinstance(entry, Geometry):
                    geometries.append(entry)
                elif isinstance(entry, dict):
                    geometries.append(Geometry.from_dict(entry))
                else:
                    raise TypeError(
                        'The geometries attribute must contain either a Geometry or json serialization of a Geometry. '
                        'Got an entry of type {}'.format(type(entry)))
        return cls(geometries)

    def to_dict(self, parent_dict=None):
        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        parent_dict['geometries'] = [entry.to_dict() for entry in self.geometries]
        return parent_dict

    def add_to_kml(self, doc, parent, coord_transform):
        pass

    def apply_projection(self, proj_method):
        """
        Gets a new version after applying a transform method.

        Parameters
        ----------
        proj_method : callable

        Returns
        -------
        GeometryObject
        """
        pass

    @classmethod
    def assemble_from_collection(cls, *args):
        """
        Assemble a geometry collection from the input constituents.

        Parameters
        ----------
        args
            A list of input GeometryObjects

        Returns
        -------
        GeometryCollection
        """

        def handle_arg(arg_in):
            if isinstance(arg_in, (Point, LineString, Polygon)):
                geometries.append(arg_in)
            elif arg_in.is_collection:
                for entry in arg_in.collection:
                    handle_arg(entry)
            else:
                raise ValueError('Got unhandled argument type `{}`'.format(type(arg)))

        if len(args) == 0:
            return cls()

        geometries = []
        for arg in args:
            handle_arg(arg)

        return cls(geometries=geometries)


class GeometryObject(Geometry):
    """
    Abstract geometry object class - mirrors basic geojson functionality
    """

    _type = 'Geometry'

    def get_coordinate_list(self):
        """
        The geojson style coordinate list.

        Returns
        -------
        List
        """

        raise NotImplementedError

    def get_bbox(self):
        raise NotImplementedError

    @classmethod
    def from_dict(cls, geometry):
        # type: (Dict) -> GeometryObject
        typ = geometry.get('type', None)
        if typ is None:
            raise ValueError('Poorly formed json for GeometryObject {}'.format(geometry))
        elif typ == 'Point':
            return Point(coordinates=geometry['coordinates'])
        elif typ == 'MultiPoint':
            return MultiPoint(coordinates=geometry['coordinates'])
        elif typ == 'LineString':
            return LineString(coordinates=geometry['coordinates'])
        elif typ == 'MultiLineString':
            return MultiLineString(coordinates=geometry['coordinates'])
        elif typ == 'Polygon':
            return Polygon(coordinates=geometry['coordinates'])
        elif typ == 'MultiPolygon':
            return MultiPolygon(coordinates=geometry['coordinates'])
        else:
            raise ValueError('Unknown type {} for GeometryObject from json {}'.format(typ, geometry))

    def to_dict(self, parent_dict=None):
        if parent_dict is None:
            parent_dict = OrderedDict()
        parent_dict['type'] = self.type
        parent_dict['coordinates'] = self.get_coordinate_list()
        return parent_dict

    def add_to_kml(self, doc, parent, coord_transform):
        raise NotImplementedError

    def apply_projection(self, proj_method):
        """
        Gets a new version after applying a transform method.

        Parameters
        ----------
        proj_method : callable

        Returns
        -------
        GeometryObject
        """

        raise NotImplementedError

    def get_minimum_distance(self, point):
        """
        Get the minimum distance from the point, to the point or line segments of
        the given geometrical shape. This just assumes two-dimensional coordinates.

        Parameters
        ----------
        point : Point|numpy.ndarray|tuple|list

        Returns
        -------
        float
        """

        raise NotImplementedError


class Point(GeometryObject):
    """
    A geometric point.
    """

    __slots__ = ('_coordinates', )
    _type = 'Point'

    def __init__(self, coordinates=None):
        """

        Parameters
        ----------
        coordinates : None|numpy.ndarray|List[float]|Point
        """

        self._coordinates = None
        if coordinates is not None:
            self.coordinates = coordinates

    @property
    def coordinates(self):
        """
        numpy.ndarray: The coordinate array.
        """
        pass

    @coordinates.setter
    def coordinates(self, coordinates):
        # type: (Union[None, List, Tuple, numpy.ndarray]) -> None
        pass

    def get_bbox(self):
        if self._coordinates is None:
            return None

        out = self._coordinates.tolist()
        out.extend(self._coordinates.tolist())
        return out

    def get_coordinate_list(self):
        if self._coordinates is None:
            return None
        else:
            return self._coordinates.tolist()

    @classmethod
    def from_dict(cls, geometry):
        # type: (Dict) -> Point
        if not geometry.get('type', None) == cls._type:
            raise ValueError(_poorly_formed_text.format(geometry))
        return cls(coordinates=geometry['coordinates'])

    def add_to_kml(self, doc, parent, coord_transform):
        pass

    def apply_projection(self, proj_method):
        # type: (callable) -> Point
        pass

    def get_minimum_distance(self, point):
        if self._coordinates is None:
            return None

        point = _validate_point_array(point)
        diff = self.coordinates[:2] - point[:2]
        return float(numpy.linalg.norm(diff))


class MultiPoint(GeometryObject):
    """
    A collection of geometric points.
    """

    _type = 'MultiPoint'
    __slots__ = ('_points', )
    _is_collection = True

    def __init__(self, coordinates=None):
        """

        Parameters
        ----------
        coordinates : None|numpy.ndarray|List[float]|List[Point]|MultiPoint
        """

        self._points = None
        if isinstance(coordinates, MultiPoint):
            coordinates = coordinates.get_coordinate_list()
        if coordinates is not None:
            self.points = coordinates

    @property
    def collection(self):
        pass

    @property
    def points(self):
        # type: () -> List[Point]
        """
        List[Point]: The point collection.
        """
        pass

    @points.setter
    def points(self, points):
        pass

    def get_bbox(self):
        if self._points is None:
            return None

        # create our output space
        siz = max(point.coordinates.size for point in self.points)
        mins = [None, ]*siz
        maxs = [None, ]*siz

        for element in self.get_coordinate_list():
            for i, entry in enumerate(element):
                if mins[i] is None or (entry < mins[i]):
                    mins[i] = entry
                if maxs[i] is None or (entry > maxs[i]):
                    maxs[i] = entry
        mins.extend(maxs)
        return mins

    def get_coordinate_list(self):
        if self._points is None:
            return None
        return [point.get_coordinate_list() for point in self._points]

    @classmethod
    def from_dict(cls, geometry):
        # type: (Dict) -> MultiPoint
        if not geometry.get('type', None) == cls._type:
            raise ValueError(_poorly_formed_text.format(geometry))
        return cls(coordinates=geometry['coordinates'])

    def add_to_kml(self, doc, parent, coord_transform):
        pass

    def apply_projection(self, proj_method):
        # type: (callable) -> MultiPoint
        pass

    def get_minimum_distance(self, point):
        if self._points is None:
            return float('inf')

        return min(entry.get_minimum_distance(point) for entry in self.points)

    @classmethod
    def assemble_from_collection(cls, *args):
        """
        Assemble a multipoint collection from input constituents.

        Parameters
        ----------
        args
            A list of input Point and MultiPoint objects.

        Returns
        -------
        MultiPoint
        """

        def handle_arg(arg_in):
            if isinstance(arg_in, Point):
                points.append(arg_in)
            elif isinstance(arg_in, MultiPoint):
                points.extend(arg_in.points)
            elif isinstance(arg_in, GeometryCollection):
                for entry in arg_in.geometries:
                    handle_arg(entry)
            else:
                raise ValueError(_disallowed_text.format(type(arg_in)))

        if len(args) == 0:
            return cls()

        points = []
        for arg in args:
            handle_arg(arg)
        return cls(points)


class LineString(GeometryObject):
    """
    A geometric line.
    """

    __slots__ = ('_coordinates', )
    _type = 'LineString'

    def __init__(self, coordinates=None):
        """

        Parameters
        ----------
        coordinates : None|numpy.ndarray|List[List[float]]|LineString|LinearRing
        """

        self._coordinates = None
        if isinstance(coordinates, (LineString, LinearRing)):
            coordinates = coordinates.get_coordinate_list()
        if coordinates is not None:
            self.coordinates = coordinates

    @property
    def coordinates(self):
        # type: () -> numpy.ndarray
        """
        numpy.ndarray: The coordinate array.
        """
        pass

    @coordinates.setter
    def coordinates(self, coordinates):
        # type: (Union[None, List, Tuple, numpy.ndarray]) -> None
        pass

    def self_intersection(self):
        """
        Does this self intersect?

        Returns
        -------
        bool
        """
        pass

    def get_bbox(self):
        if self._coordinates is None:
            return None

        mins = numpy.min(self.coordinates, axis=0)
        maxs = numpy.max(self.coordinates, axis=0)
        min_list = mins.tolist()
        max_list = maxs.tolist()
        assert(isinstance(min_list, list))
        assert (isinstance(max_list, list))
        min_list.extend(max_list)
        return min_list

    def get_coordinate_list(self):
        if self._coordinates is None:
            return None
        else:
            return self._coordinates.tolist()

    @classmethod
    def from_dict(cls, geometry):
        # type: (dict) -> LineString
        if not geometry.get('type', None) == cls._type:
            raise ValueError(_poorly_formed_text.format(geometry))
        return cls(coordinates=geometry['coordinates'])

    def get_length(self):
        """
        Gets the length of the line.

        Returns
        -------
        None|float
        """
        pass

    def add_to_kml(self, doc, parent, coord_transform):
        pass

    def apply_projection(self, proj_method):
        # type: (callable) -> LineString
        pass

    def get_minimum_distance(self, point):
        if self._coordinates is None:
            return float('inf')
        p_coord = _validate_point_array(point)[:2]
        if self._coordinates.shape[0] == 1:
            return float(numpy.linalg.norm(self._coordinates[0, :] - p_coord))
        elif self._coordinates.shape[0] == 2:
            return _line_segment_distance(self._coordinates[:, :2], p_coord)
        else:
            return min(
                _line_segment_distance(self._coordinates[i:i+2, :2], p_coord)
                for i in range(self._coordinates.shape[0]-1))


class MultiLineString(GeometryObject):
    """
    A collection of geometric lines.
    """

    __slots__ = ('_lines', )
    _type = 'MultiLineString'
    _is_collection = True

    def __init__(self, coordinates=None):
        """

        Parameters
        ----------
        coordinates : None|List[numpy.ndarray]|List[List[List[float]]]|List[LineString]|MultiLineString
        """

        self._lines = None
        if isinstance(coordinates, MultiLineString):
            coordinates = coordinates.get_coordinate_list()
        if coordinates is not None:
            self.lines = coordinates

    @property
    def collection(self):
        pass

    @property
    def lines(self):
        # type: () -> List[LineString]
        """
        List[LineString]: The line collection.
        """
        pass

    @lines.setter
    def lines(self, lines):
        pass

    def get_bbox(self):
        if self._lines is None:
            return None

        siz = max(line.coordinates.shape[1] for line in self.lines)
        mins = [None, ]*siz
        maxs = [None, ]*siz
        for line in self.lines:
            t_bbox = line.get_bbox()
            num_mins = len(t_bbox)//2
            for i, entry in enumerate(t_bbox):
                if(i < num_mins):
                    if mins[i] is None or entry < mins[i]:
                        mins[i] = entry
                else:
                    if maxs[i-num_mins] is None or entry > maxs[i-num_mins]:
                        maxs[i-num_mins] = entry
        mins.extend(maxs)
        return mins

    def get_coordinate_list(self):
        if self._lines is None:
            return None
        return [line.get_coordinate_list() for line in self._lines]

    @classmethod
    def from_dict(cls, geometry):
        # type: (Dict) -> MultiLineString
        if not geometry.get('type', None) == cls._type:
            raise ValueError(_poorly_formed_text.format(geometry))
        return cls(coordinates=geometry['coordinates'])

    def get_length(self):
        """
        Gets the length of the lines.

        Returns
        -------
        None|float
        """
        pass

    def add_to_kml(self, doc, parent, coord_transform):
        pass

    def apply_projection(self, proj_method):
        # type: (callable) -> MultiLineString
        pass

    def get_minimum_distance(self, point):
        if self._lines is None:
            return float('inf')
        return min(entry.get_minimum_distance(point) for entry in self.lines)

    @classmethod
    def assemble_from_collection(cls, *args):
        """
        Assemble a multiline collection from input constituents.

        Parameters
        ----------
        args
            A list of input LineString and MultiLineString objects.

        Returns
        -------
        MultiLineString
        """

        def handle_arg(arg_in):
            if isinstance(arg_in, LineString):
                points.append(arg_in)
            elif isinstance(arg_in, MultiLineString):
                points.extend(arg_in.lines)
            elif isinstance(arg_in, GeometryCollection):
                for entry in arg_in.geometries:
                    handle_arg(entry)
            else:
                raise ValueError(_disallowed_text.format(type(arg_in)))

        if len(args) == 0:
            return cls()

        points = []
        for arg in args:
            handle_arg(arg)
        return cls(points)


class LinearRing(LineString):
    """
    This is not directly a valid geojson member, but plays the role of a single
    polygonal element, and is only used as a Polygon constituent.
    """
    __slots__ = ('_coordinates', '_diffs', '_bounding_box', '_segmentation', '_orientation')
    _type = 'LinearRing'

    def __init__(self, coordinates=None):
        """

        Parameters
        ----------
        coordinates : None|numpy.ndarray|List[List[float]]|LinearRing|LineString
        """

        self._coordinates = None
        self._diffs = None
        self._bounding_box = None
        self._segmentation = None
        self._orientation = 1
        if isinstance(coordinates, (LineString, LinearRing)):
            coordinates = coordinates.get_coordinate_list()
        super(LinearRing, self).__init__(coordinates)

    def get_coordinate_list(self):
        if self._coordinates is None:
            return None
        else:
            return self._coordinates.tolist()

    def reverse_orientation(self):
        if self._coordinates is None:
            return
        self.coordinates = self._coordinates[::-1, :]
        self._orientation *= -1

    @property
    def orientation(self):
        """
        int: +1 for positive orientation (counter-clockwise) and -1 for negative orientation (clockwise).
        """

        return self._orientation

    @property
    def bounding_box(self):
        """
        The bounding box of the form [[x_min, x_max], [y_min, y_max]].
        *Note that would be extremely misleading for a naively constructed
        lat/lon polygon crossing the boundary of discontinuity and/or surrounding a pole.*

        Returns
        -------
        numpy.ndarray
        """
        pass

    def get_perimeter(self):
        """
        Gets the perimeter of the linear ring.

        Returns
        -------
        float
        """
        pass

    def get_area(self):
        """
        Gets the area of the polygon. If a polygon is self-intersecting, then this
        result may be pathological. A positive value represents a polygon with positive
        orientation, while a negative value represents a polygon with negative orientation.

        Returns
        -------
        float
        """

        return float(
            0.5*numpy.sum(self._coordinates[:-1, 0]*self._coordinates[1:, 1] -
                          self._coordinates[1:, 0]*self._coordinates[:-1, 1]))

    def get_centroid(self):
        """
        Gets the centroid of the polygon - note that this may not actually lie in
        the polygon interior for non-convex polygon. This will result in an undefined value
        if the polygon is degenerate.

        Returns
        -------
        numpy.ndarray
        """
        pass

    @property
    def coordinates(self):
        """
        Gets the coordinates array.

        Returns
        -------
        numpy.ndarray
        """
        pass

    @coordinates.setter
    def coordinates(self, coordinates):
        pass

    def set_coordinates(self, coordinates):
        pass

    @staticmethod
    def _construct_segmentation(coords, o_coords):
        # helper method
        pass

    def _contained_segment_data(self, x, y):
        """
        This is a helper function for the polygon containment effort.
        This determines whether the x or y segmentation should be utilized, and
        the details for doing so.

        Parameters
        ----------
        x : numpy.ndarray
        y : numpy.ndarray

        Returns
        -------
        (int|None, int|None, str)
            the segment index start (inclusive), the segment index end (exclusive),
            and "x" or "y" for which segmentation is better.
        """

        def segment(coord, segments):
            tmin = coord.min()
            tmax = coord.max()

            if tmax < segments[0]['min'] or tmin > segments[-1]['max']:
                return None, None

            if len(segments) == 1:
                return 0, 1

            t_first_ind = None if tmin > segments[0]['max'] else 0
            t_last_ind = None if tmax < segments[-1]['min'] else len(segments)

            for i, seg in enumerate(segments):
                if seg['min'] <= tmin < seg['max']:
                    t_first_ind = i
                if seg['min'] <= tmax <= seg['max']:
                    t_last_ind = i+1
                if t_first_ind is not None and t_last_ind is not None:
                    break
            return t_first_ind, t_last_ind

        # let's determine first/last x & y segments and which is better (fewer)
        x_first_ind, x_last_ind = segment(x, self._segmentation['x'])
        if x_first_ind is None:
            return None, None, 'x'

        y_first_ind, y_last_ind = segment(y, self._segmentation['y'])
        if y_first_ind is None:
            return None, None, 'y'

        if (y_last_ind - y_first_ind) <= (x_last_ind - x_first_ind):
            return y_first_ind, y_last_ind, 'y'
        return x_first_ind, x_last_ind, 'x'

    def _contained_do_segment(self, x, y, segment, direction):
        """
        Helper function for polygon containment effort.

        Parameters
        ----------
        x : numpy.ndarray
        y : numpy.ndarray
        segment : dict
        direction : str

        Returns
        -------
        numpy.ndarray
        """

        # we require that all these points are relevant to this slice
        in_poly = numpy.zeros(x.shape, dtype='bool')
        crossing_counts = numpy.zeros(x.shape, dtype=numpy.int32)
        indices = segment['inds']
        orient = self.orientation

        for i in indices:
            if direction == 'x' and self._coordinates[i, 0] == self._coordinates[i+1, 0]:
                # we are segmented horizontally and processing vertically.
                # This is a vertical line - only consider inclusion.
                y_min = min(self._coordinates[i, 1], self._coordinates[i+1, 1])
                y_max = max(self._coordinates[i, 1], self._coordinates[i+1, 1])
                # points on the edge are included
                in_poly[(x == self._coordinates[i, 0]) & (y_min <= y) & (y <= y_max)] = True
            elif direction == 'y' and self._coordinates[i, 1] == self._coordinates[i+1, 1]:
                # we are segmented vertically and processing horizontally.
                # This is a horizontal line - only consider inclusion.
                x_min = min(self._coordinates[i, 0], self._coordinates[i+1, 0])
                x_max = max(self._coordinates[i, 0], self._coordinates[i+1, 0])
                # points on the edge are included
                in_poly[(y == self._coordinates[i, 1]) & (x_min <= x) & (x <= x_max)] = True
            else:
                nx, ny = self._diffs[i, 1],  -self._diffs[i, 0]
                crossing = orient*((x - self._coordinates[i, 0])*nx + (y - self._coordinates[i, 1])*ny)
                # dot product of vector connecting (x, y) to segment vertex with normal vector of segment
                crossing_counts[crossing > 0] += 1  # positive crossing number
                crossing_counts[crossing < 0] -= 1  # negative crossing number
                # points on the edge are included
                in_poly[(crossing == 0)] = True
        in_poly |= (crossing_counts != 0)
        return in_poly

    def _contained(self, x, y):
        """
        Helper method for polygon inclusion.

        Parameters
        ----------
        x : numpy.ndarray
        y : numpy.ndarray

        Returns
        -------
        numpy.ndarray
        """

        out = numpy.zeros(x.shape, dtype='bool')

        ind_beg, ind_end, direction = self._contained_segment_data(x, y)
        if ind_beg is None:
            return out  # it missed the whole bounding box

        for index in range(ind_beg, ind_end):
            if direction == 'x':
                seg = self._segmentation['x'][index]
                mask = ((x >= seg['min']) & (x <= seg['max']) & (y >= seg['min_value']) & (y <= seg['max_value']))
            else:
                seg = self._segmentation['y'][index]
                mask = ((y >= seg['min']) & (y <= seg['max']) & (x >= seg['min_value']) & (x <= seg['max_value']))
            if numpy.any(mask):
                out[mask] = self._contained_do_segment(x[mask], y[mask], seg, direction)
        return out

    def contain_coordinates(self, pts_x, pts_y, block_size=None):
        """
        Determines inclusion of the given points in the interior of the polygon.
        The methodology here is based on the Jordan curve theorem approach.

        ** Warning - This method may provide erroneous results for a lat/lon polygon
        crossing the bound of discontinuity and/or surrounding a pole.**

        Note - If the points constitute an x/y grid, then the grid contained method will
        be much more performant.

        Parameters
        ----------
        pts_x : numpy.ndarray|list|tuple|float|int
        pts_y : numpy.ndarray|list|tuple|float|int
        block_size : None|int
            If provided, processing block size. The minimum value used will be
            50,000.

        Returns
        -------
        numpy.ndarray|bool
            boolean array indicating inclusion.
        """

        pts_x, pts_y = _validate_contain_arguments(pts_x, pts_y)

        o_shape = pts_x.shape

        if len(o_shape) == 0:
            pts_x = numpy.reshape(pts_x, (1, ))
            pts_y = numpy.reshape(pts_y, (1, ))
        else:
            pts_x = numpy.reshape(pts_x, (-1, ))
            pts_y = numpy.reshape(pts_y, (-1, ))

        if block_size is not None:
            block_size = int(block_size)
            block_size = max(50000, block_size)

        if block_size is None or pts_x.size <= block_size:
            in_poly = self._contained(pts_x, pts_y)
        else:
            in_poly = numpy.zeros(pts_x.shape, dtype='bool')
            start_block = 0
            while start_block < pts_x.size:
                end_block = min(start_block+block_size, pts_x.size)
                in_poly[start_block:end_block] = self._contained(
                    pts_x[start_block:end_block], pts_y[start_block:end_block])
                start_block = end_block

        if len(o_shape) == 0:
            return in_poly[0]
        else:
            return numpy.reshape(in_poly, o_shape)

    def grid_contained(self, grid_x, grid_y):
        """
        Determines inclusion of a coordinate grid inside the polygon. The coordinate
        grid is defined by the two one-dimensional coordinate arrays `grid_x` and `grid_y`.

        Parameters
        ----------
        grid_x : numpy.ndarray
        grid_y : numpy.ndarray

        Returns
        -------
        numpy.ndarray
            boolean mask for point inclusion of the grid. Output is of shape
            `(grid_x.size, grid_y.size)`.
        """
        pass

    def apply_projection(self, proj_method):
        # type: (callable) -> LinearRing
        pass

    def to_dict(self, parent_dict=None):
        """
        Serialize the LinearRing to json.

        Note that the geojson standard requires that the serialized object has
        positive orientation. In the case of an LinearRing defined with negative
        orientation, the orientation of the object and the serialized object will
        be reversed.

        Parameters
        ----------
        parent_dict : None|Dict

        Returns
        -------
        Dict
        """

        if self.orientation > 0:
            return super(LinearRing, self).to_dict(parent_dict=parent_dict)
        else:
            self.reverse_orientation()
            out = super(LinearRing, self).to_dict(parent_dict=parent_dict)
            self.reverse_orientation()
            return out


class Polygon(GeometryObject):
    """
    A polygon object consisting of an outer LinearRing, and some collection of
    interior LinearRings representing holes or voids.
    """

    __slots__ = ('_outer_ring', '_inner_rings')
    _type = 'Polygon'

    def __init__(self, coordinates=None):
        """

        Parameters
        ----------
        coordinates : None|List[numpy.ndarray]|List[List[float]]|List[LinearRing]|List[LineString]|Polygon
            The first element is the outer ring, any remaining will be inner rings.
        """

        self._outer_ring = None  # type: Union[None, LinearRing]
        self._inner_rings = None  # type: Union[None, List[LinearRing]]
        if isinstance(coordinates, Polygon):
            coordinates = coordinates.get_coordinate_list()
        if coordinates is None:
            return
        if not isinstance(coordinates, list):
            raise TypeError('coordinates must be a list of linear ring coordinate arrays.')
        if len(coordinates) < 1:
            return
        self.set_outer_ring(coordinates[0])
        for entry in coordinates[1:]:
            self.add_inner_ring(entry)

    def self_intersection(self):
        """
        Does this Polygon self intersect?

        Returns
        -------
        bool
        """
        pass

    @property
    def outer_ring(self):
        """
        LinearRing: The outer ring.
        """
        pass

    @property
    def inner_rings(self):
        """
        None|List[LinearRing]: The inner rings.
        """
        pass

    @classmethod
    def from_dict(cls, geometry):
        # type: (Dict) -> Polygon
        if not geometry.get('type', None) == cls._type:
            raise ValueError(_poorly_formed_text.format(geometry))
        return cls(coordinates=geometry['coordinates'])

    def get_bbox(self):
        if self._outer_ring is None:
            return None
        return self._outer_ring.get_bbox()

    def get_coordinate_list(self):
        if self._outer_ring is None:
            return None

        out = [self._outer_ring.get_coordinate_list(), ]
        if self._inner_rings is not None:
            for ir in self._inner_rings:
                ir_reversed = LinearRing(ir.coordinates[::-1, :])
                out.append(ir_reversed.get_coordinate_list())
        return out

    def set_outer_ring(self, coordinates):
        """
        Set the outer ring for the Polygon.

        Parameters
        ----------
        coordinates : LinearRing|numpy.ndarray|list

        Returns
        -------
        None
        """
        pass

    def add_inner_ring(self, coordinates):
        pass

    def get_perimeter(self):
        """
        Gets the perimeter of the linear ring.

        Returns
        -------
        None|float
        """
        pass

    def get_area(self):
        """
        Gets the area of the polygon.

        Returns
        -------
        None|float
        """

        if self._outer_ring is None:
            return None

        area = abs(self._outer_ring.get_area())  # positive
        if self._inner_rings is not None:
            for entry in self._inner_rings:
                area -= abs(entry.get_area())  # negative
        return area

    def get_centroid(self):
        """
        Gets the centroid of the outer ring of the polygon - note that this may not actually lie in
        the polygon interior for non-convex polygon. This will result in an undefined value
        if the polygon is degenerate.

        Returns
        -------
        numpy.ndarray
        """
        pass

    def contain_coordinates(self, pts_x, pts_y, block_size=None):
        """
        Determines inclusion of the given points in the interior of the polygon.
        The methodology here is based on the Jordan curve theorem approach.

        ** Warning - This method may provide erroneous results for a lat/lon polygon
        crossing the bound of discontinuity and/or surrounding a pole.**

        Note - If the points constitute an x/y grid, then the grid contained method will
        be much more performant.

        Parameters
        ----------
        pts_x : numpy.ndarray|list|tuple|float|int
        pts_y : numpy.ndarray|list|tuple|float|int
        block_size : None|int
            If provided, processing block size. The minimum value used will be
            50,000.

        Returns
        -------
        numpy.ndarray|bool
            boolean array indicating inclusion.
        """

        pts_x, pts_y = _validate_contain_arguments(pts_x, pts_y)

        if self._outer_ring is None:
            return numpy.zeros(pts_x.shape, dtype='bool')

        o_shape = pts_x.shape
        in_poly = self._outer_ring.contain_coordinates(pts_x, pts_y, block_size=block_size)
        if self._inner_rings is not None:
            for ir in self._inner_rings:
                in_poly &= ~ir.contain_coordinates(pts_x, pts_y, block_size=block_size)

        if len(o_shape) == 0:
            return in_poly
        else:
            return numpy.reshape(in_poly, o_shape)

    def grid_contained(self, grid_x, grid_y):
        """
        Determines inclusion of a coordinate grid inside the polygon. The coordinate
        grid is defined by the two one-dimensional coordinate arrays `grid_x` and `grid_y`.

        Parameters
        ----------
        grid_x : numpy.ndarray
        grid_y : numpy.ndarray

        Returns
        -------
        numpy.ndarray
            boolean mask for point inclusion of the grid. Output is of shape
            `(grid_x.size, grid_y.size)`.
        """
        pass

    def add_to_kml(self, doc, parent, coord_transform):
        pass

    def apply_projection(self, proj_method):
        # type: (callable) -> Polygon
        pass

    def get_minimum_distance(self, point):
        if self._outer_ring is None:
            return float('inf')

        o_dist = self.outer_ring.get_minimum_distance(point)
        if self._inner_rings is None or len(self._inner_rings) < 1:
            return o_dist
        i_dist = min(entry.get_minimum_distance(point) for entry in self.inner_rings)
        return min(o_dist, i_dist)


class MultiPolygon(GeometryObject):
    """
    A collection of polygon objects.
    """

    __slots__ = ('_polygons', )
    _type = 'MultiPolygon'
    _is_collection = True

    def __init__(self, coordinates=None):
        """

        Parameters
        ----------
        coordinates : None|List[List[List[float]]]|List[Polygon]|MultiPolygon
        """

        self._polygons = None
        if isinstance(coordinates, MultiPolygon):
            coordinates = coordinates.get_coordinate_list()
        if coordinates is not None:
            self.polygons = coordinates

    @property
    def collection(self):
        pass

    @property
    def polygons(self):
        # type: () -> List[Polygon]
        """
        List[Polygon]: The polygon collection.
        """
        pass

    @polygons.setter
    def polygons(self, polygons):
        pass

    def get_bbox(self):
        if self._polygons is None:
            return None
        mins = []
        maxs = []
        for polygon in self.polygons:
            t_bbox = polygon.get_bbox()
            num_mins = len(t_bbox)//2
            for i, entry in enumerate(t_bbox):
                if (i < num_mins):
                    if len(mins) < num_mins:
                        mins.append(entry)
                    elif entry < mins[i]:
                        mins[i] = entry
                else:
                    if len(maxs) < num_mins:
                        maxs.append(entry)
                    elif entry > maxs[i-num_mins]:
                        maxs[i-num_mins] = entry
        mins.extend(maxs)
        return mins

    @classmethod
    def from_dict(cls, geometry):
        # type: (Dict) -> MultiPolygon
        if not geometry.get('type', None) == cls._type:
            raise ValueError(_poorly_formed_text.format(geometry))
        return cls(coordinates=geometry['coordinates'])

    def get_coordinate_list(self):
        if self._polygons is None:
            return None
        return [polygon.get_coordinate_list() for polygon in self._polygons]

    def get_perimeter(self):
        """
        Gets the perimeter of the linear ring.

        Returns
        -------
        None|float
        """
        pass

    def get_area(self):
        """
        Gets the area of the polygon.

        Returns
        -------
        None|float
        """

        if self._polygons is None:
            return None
        return sum(entry.get_area() for entry in self._polygons)

    def contain_coordinates(self, pts_x, pts_y, block_size=None):
        """
        Determines inclusion of the given points in the interior of the polygon.
        The methodology here is based on the Jordan curve theorem approach.

        ** Warning - This method may provide erroneous results for a lat/lon polygon
        crossing the bound of discontinuity and/or surrounding a pole.**

        Note - If the points constitute an x/y grid, then the grid contained method will
        be much more performant.

        Parameters
        ----------
        pts_x : numpy.ndarray|list|tuple|float|int
        pts_y : numpy.ndarray|list|tuple|float|int
        block_size : None|int
            If provided, processing block size. The minimum value used will be
            50,000.

        Returns
        -------
        numpy.ndarray|bool
            boolean array indicating inclusion.
        """

        pts_x, pts_y = _validate_contain_arguments(pts_x, pts_y)

        if self._polygons is None or len(self._polygons) == 0:
            return numpy.zeros(pts_x.shape, dtype='bool')

        in_poly = self._polygons[0].contain_coordinates(pts_x, pts_y, block_size=block_size)
        for entry in self._polygons[1:]:
            in_poly |= entry.contain_coordinates(pts_x, pts_y, block_size=block_size)
        return in_poly

    def grid_contained(self, grid_x, grid_y):
        """
        Determines inclusion of a coordinate grid inside the polygon. The coordinate
        grid is defined by the two one-dimensional coordinate arrays `grid_x` and `grid_y`.

        Parameters
        ----------
        grid_x : numpy.ndarray
        grid_y : numpy.ndarray

        Returns
        -------
        numpy.ndarray
            boolean mask for point inclusion of the grid. Output is of shape
            `(grid_x.size, grid_y.size)`.
        """
        pass

    def add_to_kml(self, doc, parent, coord_transform):
        pass

    def apply_projection(self, proj_method):
        # type: (callable) -> MultiPolygon
        pass

    def get_minimum_distance(self, point):
        if self._polygons is None:
            return float('inf')
        return min(entry.get_minimum_distance(point) for entry in self.polygons)

    @classmethod
    def assemble_from_collection(cls, *args):
        """
        Assemble a multipolygon collection from input constituents.

        Parameters
        ----------
        args
            A list of input Polygon and MultiPolygon objects.

        Returns
        -------
        MultiPolygon
        """

        def handle_arg(arg_in):
            if isinstance(arg_in, LinearRing):
                polygons.append(Polygon([arg_in, ]))
            elif isinstance(arg_in, Polygon):
                polygons.append(arg_in)
            elif isinstance(arg_in, MultiPolygon):
                polygons.extend(arg_in.polygons)
            elif isinstance(arg_in, GeometryCollection):
                for entry in arg_in.geometries:
                    handle_arg(entry)
            else:
                raise ValueError(_disallowed_text.format(type(arg_in)))

        if len(args) == 0:
            return cls()

        polygons = []
        for arg in args:
            handle_arg(arg)
        return cls(polygons)


def basic_assemble_from_collection(*args):
    """
    Assemble the most suitable (flat) collective type from the input collection.

    Parameters
    ----------
    args
        The input geometry objects.

    Returns
    -------
    GeometryCollection|MultiPoint|MultiLineString|MultiPolygon
    """

    try:
        return MultiPoint.assemble_from_collection(*args)
    except ValueError:
        pass

    try:
        return MultiLineString.assemble_from_collection(*args)
    except ValueError:
        pass

    try:
        return MultiPolygon.assemble_from_collection(*args)
    except ValueError:
        pass

    return GeometryCollection.assemble_from_collection(*args)
