"""
Definition for the ObjectInfo NGA modified RDE/AFRL labeling object
"""

__classification__ = "UNCLASSIFIED"
__authors__ = "Thomas McCullough"

import logging
from typing import Optional, List

import numpy

from sarpy.io.xml.base import Serializable, Arrayable, create_text_node, \
    get_node_value
from sarpy.io.xml.descriptors import StringDescriptor, FloatDescriptor, \
    IntegerDescriptor, SerializableDescriptor, SerializableListDescriptor
from sarpy.io.complex.sicd_elements.blocks import RowColType
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.product.sidd2_elements.SIDD import SIDDType
from sarpy.geometry.geocoords import geodetic_to_ecf, ecf_to_geodetic, wgs_84_norm
from sarpy.geometry.geometry_elements import Point, Polygon, GeometryCollection, Geometry
from sarpy.annotation.base import GeometryProperties

from .base import DEFAULT_STRICT
from .blocks import RangeCrossRangeType, RowColDoubleType, LatLonEleType, \
    ProjectionPerturbationType, LabelSourceType


logger = logging.getLogger(__name__)

_no_projection_text = 'This sicd does not permit projection,\n\t' \
                      'so the image location can not be inferred'


# the Object and sub-component definitions

class PhysicalType(Serializable):
    _fields = ('ChipSize', 'CenterPixel')
    _required = _fields
    ChipSize = SerializableDescriptor(
        'ChipSize', RangeCrossRangeType, _required, strict=DEFAULT_STRICT,
        docstring='The chip size of the physical object, '
                  'in the appropriate plane')  # type: RangeCrossRangeType
    CenterPixel = SerializableDescriptor(
        'CenterPixel', RowColDoubleType, _required, strict=DEFAULT_STRICT,
        docstring='The center pixel of the physical object, '
                  'in the appropriate plane')  # type: RowColDoubleType

    def __init__(self, ChipSize=None, CenterPixel=None, **kwargs):
        """
        Parameters
        ----------
        ChipSize : RangeCrossRangeType|numpy.ndarray|list|tuple
        CenterPixel : RowColDoubleType|numpy.ndarray|list|tuple
        kwargs
            Other keyword arguments
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.ChipSize = ChipSize
        self.CenterPixel = CenterPixel
        super(PhysicalType, self).__init__(**kwargs)

    @classmethod
    def from_ranges(cls, row_range, col_range, row_limit, col_limit):
        """
        Construct from the row/column ranges and limits.

        Parameters
        ----------
        row_range
        col_range
        row_limit
        col_limit

        Returns
        -------
        PhysicalType
        """
        pass


class PlanePhysicalType(Serializable):
    _fields = (
        'Physical', 'PhysicalWithShadows')
    _required = _fields
    Physical = SerializableDescriptor(
        'Physical', PhysicalType, _required,
        docstring='Chip details for the physical object in the appropriate plane')  # type: PhysicalType
    PhysicalWithShadows = SerializableDescriptor(
        'PhysicalWithShadows', PhysicalType, _required,
        docstring='Chip details for the physical object including shadows in '
                  'the appropriate plane')  # type: PhysicalType

    def __init__(self, Physical=None, PhysicalWithShadows=None, **kwargs):
        """

        Parameters
        ----------
        Physical : PhysicalType
        PhysicalWithShadows : PhysicalType
        kwargs
            Other keyword arguments
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.Physical = Physical
        self.PhysicalWithShadows = PhysicalWithShadows
        super(PlanePhysicalType, self).__init__(**kwargs)


class SizeType(Serializable, Arrayable):
    _fields = ('Length', 'Width', 'Height')
    _required = _fields
    _numeric_format = {key: '0.17G' for key in _fields}
    # Descriptors
    Length = FloatDescriptor(
        'Length', _required, strict=True, docstring='The Length attribute.')  # type: float
    Width = FloatDescriptor(
        'Width', _required, strict=True, docstring='The Width attribute.')  # type: float
    Height = FloatDescriptor(
        'Height', _required, strict=True, docstring='The Height attribute.')  # type: float

    def __init__(self, Length=None, Width=None, Height=None, **kwargs):
        """
        Parameters
        ----------
        Length : float
        Width : float
        Height : float
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.Length, self.Width, self.Height = Length, Width, Height
        super(SizeType, self).__init__(**kwargs)

    def get_max_diameter(self):
        """
        Gets the nominal maximum diameter for the item, in meters.

        Returns
        -------
        float
        """
        pass

    def get_array(self, dtype='float64'):
        """
        Gets an array representation of the class instance.

        Parameters
        ----------
        dtype : str|numpy.dtype|numpy.number
            numpy data type of the return

        Returns
        -------
        numpy.ndarray
            array of the form [Length, Width, Height]
        """

        return numpy.array([self.Length, self.Width, self.Height], dtype=dtype)

    @classmethod
    def from_array(cls, array):
        """
        Create from an array type entry.

        Parameters
        ----------
        array: numpy.ndarray|list|tuple
            assumed [Length, Width, Height]

        Returns
        -------
        SizeType
        """

        if array is None:
            return None
        if isinstance(array, (numpy.ndarray, list, tuple)):
            if len(array) < 3:
                raise ValueError('Expected array to be of length 3, and received {}'.format(array))
            return cls(Length=array[0], Width=array[1], Height=array[2])
        raise ValueError('Expected array to be numpy.ndarray, list, or tuple, got {}'.format(type(array)))


class OrientationType(Serializable):
    _fields = ('Roll', 'Pitch', 'Yaw', 'AzimuthAngle')
    _required = ()
    _numeric_format = {key: '0.17G' for key in _fields}
    # descriptors
    Roll = FloatDescriptor(
        'Roll', _required)  # type: float
    Pitch = FloatDescriptor(
        'Pitch', _required)  # type: float
    Yaw = FloatDescriptor(
        'Yaw', _required)  # type: float
    AzimuthAngle = FloatDescriptor(
        'AzimuthAngle', _required)  # type: float

    def __init__(self, Roll=None, Pitch=None, Yaw=None, AzimuthAngle=None, **kwargs):
        """
        Parameters
        ----------
        Roll : float
        Pitch : float
        Yaw : float
        AzimuthAngle : float
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.Roll = Roll
        self.Pitch = Pitch
        self.Yaw = Yaw
        self.AzimuthAngle = AzimuthAngle
        super(OrientationType, self).__init__(**kwargs)


class ImageLocationType(Serializable):
    _fields = (
        'CenterPixel', 'LeftFrontPixel', 'RightFrontPixel', 'RightRearPixel',
        'LeftRearPixel')
    _required = ('CenterPixel', )
    # descriptors
    CenterPixel = SerializableDescriptor(
        'CenterPixel', RowColType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: RowColType
    LeftFrontPixel = SerializableDescriptor(
        'LeftFrontPixel', RowColType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[RowColType]
    RightFrontPixel = SerializableDescriptor(
        'RightFrontPixel', RowColType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[RowColType]
    RightRearPixel = SerializableDescriptor(
        'RightRearPixel', RowColType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[RowColType]
    LeftRearPixel = SerializableDescriptor(
        'LeftRearPixel', RowColType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[RowColType]

    def __init__(self, CenterPixel=None, LeftFrontPixel=None, RightFrontPixel=None,
                 RightRearPixel=None, LeftRearPixel=None, **kwargs):
        """
        Parameters
        ----------
        CenterPixel : RowColType|numpy.ndarray|list|tuple
        LeftFrontPixel : RowColType|numpy.ndarray|list|tuple
        RightFrontPixel : RowColType|numpy.ndarray|list|tuple
        RightRearPixel : RowColType|numpy.ndarray|list|tuple
        LeftRearPixel : RowColType|numpy.ndarray|list|tuple
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.CenterPixel = CenterPixel
        self.LeftFrontPixel = LeftFrontPixel
        self.RightFrontPixel = RightFrontPixel
        self.RightRearPixel = RightRearPixel
        self.LeftRearPixel = LeftRearPixel
        super(ImageLocationType, self).__init__(**kwargs)

    @classmethod
    def from_geolocation(cls, geo_location, the_structure):
        """
        Construct the image location from the geographical location via
        projection using the SICD model.

        Parameters
        ----------
        geo_location : GeoLocationType
        the_structure : SICDType|SIDDType

        Returns
        -------
        None|ImageLocationType
            None if projection fails, the value otherwise
        """
        pass

    def infer_center_pixel(self):
        """
        Infer the center pixel, if not populated.

        Returns
        -------
        None
        """
        pass

    def get_nominal_box(self, row_length=10, col_length=10):
        """
        Get a nominal box containing the object, using the default side length if necessary.

        Parameters
        ----------
        row_length : int|float
            The side length to use for the rectangle, if not defined.
        col_length : int|float
            The side length to use for the rectangle, if not defined.

        Returns
        -------
        None|numpy.ndarray
        """
        pass

    def get_geometry_object(self):
        """
        Gets the geometry for the given image section.

        Returns
        -------
        geometry : None|Point|GeometryCollection
        geometry_properties : None|List[GeometryProperties]
        """
        pass


class GeoLocationType(Serializable):
    _fields = (
        'CenterPixel', 'LeftFrontPixel', 'RightFrontPixel', 'RightRearPixel',
        'LeftRearPixel')
    _required = ('CenterPixel', )
    # descriptors
    CenterPixel = SerializableDescriptor(
        'CenterPixel', LatLonEleType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: LatLonEleType
    LeftFrontPixel = SerializableDescriptor(
        'LeftFrontPixel', LatLonEleType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[LatLonEleType]
    RightFrontPixel = SerializableDescriptor(
        'RightFrontPixel', LatLonEleType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[LatLonEleType]
    RightRearPixel = SerializableDescriptor(
        'RightRearPixel', LatLonEleType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[LatLonEleType]
    LeftRearPixel = SerializableDescriptor(
        'LeftRearPixel', LatLonEleType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[LatLonEleType]

    def __init__(self, CenterPixel=None, LeftFrontPixel=None, RightFrontPixel=None,
                 RightRearPixel=None, LeftRearPixel=None, **kwargs):
        """
        Parameters
        ----------
        CenterPixel : LatLonEleType|numpy.ndarray|list|tuple
        LeftFrontPixel : None|LatLonEleType|numpy.ndarray|list|tuple
        RightFrontPixel : None|LatLonEleType|numpy.ndarray|list|tuple
        RightRearPixel : None|LatLonEleType|numpy.ndarray|list|tuple
        LeftRearPixel : None|LatLonEleType|numpy.ndarray|list|tuple
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.CenterPixel = CenterPixel
        self.LeftFrontPixel = LeftFrontPixel
        self.RightFrontPixel = RightFrontPixel
        self.RightRearPixel = RightRearPixel
        self.LeftRearPixel = LeftRearPixel
        super(GeoLocationType, self).__init__(**kwargs)

    # noinspection PyUnusedLocal
    @classmethod
    def from_image_location(cls, image_location, the_structure, projection_type='HAE', **proj_kwargs):
        """
        Construct the geographical location from the image location via
        projection using the SICD model.

        .. Note::
            This assumes that the image coordinates are with respect to the given
            image (chip), and NOT including any sicd.ImageData.FirstRow/Col values,
            which will be added here.

        Parameters
        ----------
        image_location : ImageLocationType
        the_structure : SICDType|SIDDType
        projection_type : str
            The projection type selector, one of `['PLANE', 'HAE', 'DEM']`. Using `'DEM'`
            requires configuration for the DEM pathway described in
            :func:`sarpy.geometry.point_projection.image_to_ground_dem`.
        proj_kwargs
            The keyword arguments for the :func:`SICDType.project_image_to_ground_geo` method.

        Returns
        -------
        None|GeoLocationType
            Coordinates may be populated as `NaN` if projection fails.
        """
        pass

    def infer_center_pixel(self):
        """
        Infer the center pixel, if not populated.

        Returns
        -------
        None
        """
        pass


class StringWithComponentType(Serializable):
    _fields = ('Component', 'Value')
    _required = ('Value', )
    Component = StringDescriptor(
        'Component', _required)  # type: str
    Value = StringDescriptor(
        'Value', _required)  # type: str
    _set_as_attribute = ('Component', )

    def __init__(self, Component=None, Value=None, **kwargs):
        """

        Parameters
        ----------
        Component : str
        Value : str
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.Component = Component
        self.Value = Value
        super(StringWithComponentType, self).__init__(**kwargs)

    @classmethod
    def from_node(cls, node, xml_ns, ns_key=None, kwargs=None):
        value = get_node_value(node)
        component = node.attrib.get('Component', None)
        return cls(Value=value, Component=component)
    
    def to_node(self, doc, tag, ns_key=None, parent=None, check_validity=False, strict=DEFAULT_STRICT, exclude=()):        
        if (ns_key is not None and ns_key != 'default') and not tag.startswith(ns_key + ':'):
            use_tag = '{}:{}'.format(ns_key, tag)
        else:
            use_tag = tag
        if self.Value is None:
            value = ''
        else:
            value = self.Value
        node = create_text_node(doc, use_tag, value, parent=parent)
        if self.Component is not None:
            node.attrib['Component'] = self.Component
        return node


class TheObjectType(Serializable):
    _fields = (
        'SystemName', 'SystemComponent', 'NATOName', 'Function', 'Version', 'DecoyType', 'SerialNumber',
        'ObjectClass', 'ObjectSubClass', 'ObjectTypeClass', 'ObjectType', 'ObjectLabel',
        'SlantPlane', 'GroundPlane', 'Size', 'Orientation',
        'Articulation', 'Configuration',
        'Accessories', 'PaintScheme', 'Camouflage', 'Obscuration', 'ObscurationPercent', 'ImageLevelObscuration',
        'ImageLocation', 'GeoLocation',
        'TargetToClutterRatio', 'VisualQualityMetric',
        'UnderlyingTerrain', 'OverlyingTerrain', 'TerrainTexture', 'SeasonalCover', 
        'ProjectionPerturbation')
    _required = ('SystemName', 'ImageLocation', 'GeoLocation')
    _numeric_format = {'ObscurationPercent': '0.17G', }
    _collections_tags = {
        'Articulation': {'array': False, 'child_tag': 'Articulation'}, 
        'Configuration': {'array': False, 'child_tag': 'Configuration'}}
    # descriptors
    SystemName = StringDescriptor(
        'SystemName', _required, strict=DEFAULT_STRICT,
        docstring='Name of the object.')  # type: str
    SystemComponent = StringDescriptor(
        'SystemComponent', _required, strict=DEFAULT_STRICT,
        docstring='Name of the weapon system component.')  # type: Optional[str]
    NATOName = StringDescriptor(
        'NATOName', _required, strict=DEFAULT_STRICT,
        docstring='Name of the object in NATO naming convention.')  # type: Optional[str]
    Function = StringDescriptor(
        'Function', _required, strict=DEFAULT_STRICT,
        docstring='Function of the object.')  # type: Optional[str]
    Version = StringDescriptor(
        'Version', _required, strict=DEFAULT_STRICT,
        docstring='Version number of the object.')  # type: Optional[str]
    DecoyType = StringDescriptor(
        'DecoyType', _required, strict=DEFAULT_STRICT,
        docstring='Object is a decoy or surrogate.')  # type: Optional[str]
    SerialNumber = StringDescriptor(
        'SerialNumber', _required, strict=DEFAULT_STRICT,
        docstring='Serial number of the object.')  # type: Optional[str]
    # label elements
    ObjectClass = StringDescriptor(
        'ObjectClass', _required, strict=DEFAULT_STRICT,
        docstring='Top level class indicator; e.g., Aircraft, Ship, '
                  'Ground Vehicle, Missile Launcher, etc.')  # type: Optional[str]
    ObjectSubClass = StringDescriptor(
        'ObjectSubClass', _required, strict=DEFAULT_STRICT,
        docstring='Sub-class indicator; e.g., military, commercial')  # type: Optional[str]
    ObjectTypeClass = StringDescriptor(
        'ObjectTypeClass', _required, strict=DEFAULT_STRICT,
        docstring='Object type class indicator; e.g., '
                  'for Aircraft/Military - Propeller, Jet')  # type: Optional[str]
    ObjectType = StringDescriptor(
        'ObjectType', _required, strict=DEFAULT_STRICT,
        docstring='Object type indicator, e.g., '
                  'for Aircraft/Military/Jet - Bomber, Fighter')  # type: Optional[str]
    ObjectLabel = StringDescriptor(
        'ObjectLabel', _required, strict=DEFAULT_STRICT,
        docstring='Object label indicator, e.g., '
                  'for Bomber - Il-28, Tu-22M, Tu-160')  # type: Optional[str]
    SlantPlane = SerializableDescriptor(
        'SlantPlane', PlanePhysicalType, _required, strict=DEFAULT_STRICT,
        docstring='Object physical definition in the slant plane')  # type: Optional[PlanePhysicalType]
    GroundPlane = SerializableDescriptor(
        'GroundPlane', PlanePhysicalType, _required, strict=DEFAULT_STRICT,
        docstring='Object physical definition in the ground plane')  # type: Optional[PlanePhysicalType]
    # specific physical quantities
    Size = SerializableDescriptor(
        'Size', SizeType, _required, strict=DEFAULT_STRICT,
        docstring='The actual physical size of the object')  # type: Optional[SizeType]
    Orientation = SerializableDescriptor(
        'Orientation', OrientationType, _required, strict=DEFAULT_STRICT,
        docstring='The actual orientation size of the object')  # type: Optional[OrientationType]
    Articulation = SerializableListDescriptor(
        'Articulation', StringWithComponentType, _collections_tags, _required, 
        docstring='')  # type: List[StringWithComponentType]
    Configuration = SerializableListDescriptor(
        'Configuration', StringWithComponentType, _collections_tags, _required, 
        docstring='')  # type: List[StringWithComponentType]        
    Accessories = StringDescriptor(
        'Accessories', _required, strict=DEFAULT_STRICT,
        docstring='Defines items that are out of the norm, or have been added or removed.')  # type: Optional[str]
    PaintScheme = StringDescriptor(
        'PaintScheme', _required, strict=DEFAULT_STRICT,
        docstring='Paint scheme of object (e.g. olive drab, compass ghost grey, etc.).')  # type: Optional[str]
    Camouflage = StringDescriptor(
        'Camouflage', _required, strict=DEFAULT_STRICT,
        docstring='Details the camouflage on the object.')  # type: Optional[str]
    Obscuration = StringDescriptor(
        'Obscuration', _required, strict=DEFAULT_STRICT,
        docstring='General description of the obscuration.')  # type: Optional[str]
    ObscurationPercent = FloatDescriptor(
        'ObscurationPercent', _required, strict=DEFAULT_STRICT,
        docstring='The percent obscuration.')  # type: Optional[float]
    ImageLevelObscuration = StringDescriptor(
        'ImageLevelObscuration', _required, strict=DEFAULT_STRICT,
        docstring='Specific description of the obscuration based on the sensor look angle.')  # type: Optional[str]
    # location of the labeled item
    ImageLocation = SerializableDescriptor(
        'ImageLocation', ImageLocationType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: ImageLocationType
    GeoLocation = SerializableDescriptor(
        'GeoLocation', GeoLocationType, _required, strict=DEFAULT_STRICT,
        docstring='')  # type: GeoLocationType
    # text quality descriptions
    TargetToClutterRatio = StringDescriptor(
        'TargetToClutterRatio', _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[str]
    VisualQualityMetric = StringDescriptor(
        'VisualQualityMetric', _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[str]
    UnderlyingTerrain = StringDescriptor(
        'UnderlyingTerrain', _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[str]
    OverlyingTerrain = StringDescriptor(
        'OverlyingTerrain', _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[str]
    TerrainTexture = StringDescriptor(
        'TerrainTexture', _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[str]
    SeasonalCover = StringDescriptor(
        'SeasonalCover', _required, strict=DEFAULT_STRICT,
        docstring='')  # type: Optional[str]
    ProjectionPerturbation = SerializableDescriptor(
        'ProjectionPerturbation', ProjectionPerturbationType, _required, 
        docstring='')  # type: Optional[ProjectionPerturbationType]

    def __init__(self, SystemName=None, SystemComponent=None, NATOName=None,
                 Function=None, Version=None, DecoyType=None, SerialNumber=None,
                 ObjectClass=None, ObjectSubClass=None, ObjectTypeClass=None,
                 ObjectType=None, ObjectLabel=None,
                 SlantPlane=None, GroundPlane=None,
                 Size=None, Orientation=None,
                 Articulation=None, Configuration=None,
                 Accessories=None, PaintScheme=None, Camouflage=None,
                 Obscuration=None, ObscurationPercent=None, ImageLevelObscuration=None,
                 ImageLocation=None, GeoLocation=None,
                 TargetToClutterRatio=None, VisualQualityMetric=None,
                 UnderlyingTerrain=None, OverlyingTerrain=None,
                 TerrainTexture=None, SeasonalCover=None, 
                 ProjectionPerturbation=None,
                 **kwargs):
        """
        Parameters
        ----------
        SystemName : str
        SystemComponent : None|str
        NATOName : None|str
        Function : None|str
        Version : None|str
        DecoyType : None|str
        SerialNumber : None|str
        ObjectClass : None|str
        ObjectSubClass : None|str
        ObjectTypeClass : None|str
        ObjectType : None|str
        ObjectLabel : None|str
        SlantPlane : None|PlanePhysicalType
        GroundPlane : None|PlanePhysicalType
        Size : None|SizeType|numpy.ndarray|list|tuple
        Orientation : OrientationType
        Articulation : None|str|List[StringWithComponentType]
        Configuration : None|str|List[StringWithComponentType]
        Accessories : None|str
        PaintScheme : None|str
        Camouflage : None|str
        Obscuration : None|str
        ObscurationPercent : None|float
        ImageLevelObscuration : None|str
        ImageLocation : ImageLocationType
        GeoLocation : GeoLocationType
        TargetToClutterRatio : None|str
        VisualQualityMetric : None|str
        UnderlyingTerrain : None|str
        OverlyingTerrain : None|str
        TerrainTexture : None|str
        SeasonalCover : None|str
        ProjectionPerturbation : None|ProjectionPerturbationType
        kwargs
            Other keyword arguments
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.SystemName = SystemName
        self.SystemComponent = SystemComponent
        self.NATOName = NATOName
        self.Function = Function
        self.Version = Version
        self.DecoyType = DecoyType
        self.SerialNumber = SerialNumber

        self.ObjectClass = ObjectClass
        self.ObjectSubClass = ObjectSubClass
        self.ObjectTypeClass = ObjectTypeClass
        self.ObjectType = ObjectType
        self.ObjectLabel = ObjectLabel

        self.SlantPlane = SlantPlane
        self.GroundPlane = GroundPlane
        self.Size = Size
        self.Orientation = Orientation

        if isinstance(Articulation, (str, dict)):
            self.add_articulation(Articulation)
        elif isinstance(Articulation, list):
            for entry in Articulation:
                self.add_articulation(entry)
        else:
            self.Articulation = Articulation

        if isinstance(Configuration, (str, dict)):
            self.add_configuration(Configuration)
        elif isinstance(Configuration, list):
            for entry in Configuration:
                self.add_configuration(entry)
        else:
            self.Configuration = Configuration

        self.Accessories = Accessories
        self.PaintScheme = PaintScheme
        self.Camouflage = Camouflage
        self.Obscuration = Obscuration
        self.ObscurationPercent = ObscurationPercent
        self.ImageLevelObscuration = ImageLevelObscuration

        self.ImageLocation = ImageLocation
        self.GeoLocation = GeoLocation

        self.TargetToClutterRatio = TargetToClutterRatio
        self.VisualQualityMetric = VisualQualityMetric
        self.UnderlyingTerrain = UnderlyingTerrain
        self.OverlyingTerrain = OverlyingTerrain
        self.TerrainTexture = TerrainTexture
        self.SeasonalCover = SeasonalCover
        self.ProjectionPerturbation = ProjectionPerturbation
        super(TheObjectType, self).__init__(**kwargs)

    def _check_placement(self, rows, cols, row_bounds, col_bounds, overlap_cutoff=0.5):
        """
        Checks the bounds condition for the provided box.

        Here inclusion is defined by what proportion of the area of the proposed
        chip is actually contained inside the image bounds.

        Parameters
        ----------
        rows : int|float
            The number of rows in the image.
        cols : int|float
            The number of columns in the image.
        row_bounds : List
            Of the form `[row min, row max]`
        col_bounds : List
            Of the form `[col min, col max]`
        overlap_cutoff : float
            Determines the transition from in the periphery to out of the image.

        Returns
        -------
        int
            1 - completely in the image
            2 - the proposed chip has `overlap_cutoff <= fractional contained area < 1`
            3 - the proposed chip has `fractional contained area < overlap_cutoff`
        """
        pass

    def set_image_location_from_sicd(self, sicd, populate_in_periphery=False):
        """
        Set the image location information with respect to the given SICD,
        assuming that the physical coordinates are populated.

        Parameters
        ----------
        sicd : SICDType
        populate_in_periphery : bool

        Returns
        -------
        int
            -1 - insufficient metadata to proceed or other failure
            0 - nothing to be done
            1 - successful
            2 - object in the image periphery, populating based on `populate_in_periphery`
            3 - object not in the image field
        """
        pass

    def set_geo_location_from_sicd(self, sicd, projection_type='HAE', **proj_kwargs):
        """
        Set the geographical location information with respect to the given SICD,
        assuming that the image coordinates are populated.

        .. Note::
            This assumes that the image coordinates are with respect to the given
            image (chip), and NOT including any sicd.ImageData.FirstRow/Col values,
            which will be added here.

        Parameters
        ----------
        sicd : SICDType
        projection_type : str
            The projection type selector, one of `['PLANE', 'HAE', 'DEM']`. Using `'DEM'`
            requires configuration for the DEM pathway described in
            :func:`sarpy.geometry.point_projection.image_to_ground_dem`.
        proj_kwargs
            The keyword arguments for the :func:`SICDType.project_image_to_ground_geo` method.
        """
        pass

    def set_chip_details_from_sicd(self, sicd, layover_shift=False, populate_in_periphery=False, padding_fraction=0.05, minimum_pad=0):
        """
        Set the chip information with respect to the given SICD, assuming that the
        image location and size are defined.

        Parameters
        ----------
        sicd : SICDType
        layover_shift : bool
            Shift based on layover direction? This should be `True` if the identification of
            the bounds and/or center pixel do not include any layover, as in
            populating location from known ground truth. This should be `False` if
            the identification of bounds and/or center pixel do include layover,
            potentially as based on annotation of the imagery itself in pixel
            space.
        populate_in_periphery : bool
            Should we populate for peripheral?
        padding_fraction : None|float
            Default fraction of box dimension by which to pad.
        minimum_pad : int|float
            The minimum number of pixels by which to pad for the chip definition

        Returns
        -------
        int
            -1 - insufficient metadata to proceed
            0 - nothing to be done
            1 - successful
            2 - object in the image periphery, populating based on `populate_in_periphery`
            3 - object not in the image field
        """
        pass

    def get_image_geometry_object_for_sicd(self, include_chip=False):
        """
        Gets the geometry element describing the image geometry for a sicd.

        Returns
        -------
        geometry : Geometry
            The geometry object
        geometry_properties : List[GeometryProperties]
            The associated geometry properties list
        """
        pass

    def add_articulation(self, value):
        pass

    def add_configuration(self, value):
        pass


# the main type

class ObjectInfoType(Serializable):
    _fields = (
        'NumberOfObjectsInImage', 'NumberOfObjectsInScene', 'LabelSource', 'Objects')
    _required = ('NumberOfObjectsInImage', 'NumberOfObjectsInScene', 'LabelSource', 'Objects')
    _collections_tags = {'Objects': {'array': False, 'child_tag': 'Object'}}
    # descriptors
    NumberOfObjectsInImage = IntegerDescriptor(
        'NumberOfObjectsInImage', _required, strict=DEFAULT_STRICT,
        docstring='Number of ground truthed objects in the image.')  # type: int
    NumberOfObjectsInScene = IntegerDescriptor(
        'NumberOfObjectsInScene', _required, strict=DEFAULT_STRICT,
        docstring='Number of ground truthed objects in the scene.')  # type: int
    LabelSource = SerializableDescriptor(
        'LabelSource', LabelSourceType, _required, strict=DEFAULT_STRICT,
        docstring='The source of the labels')  # type: LabelSourceType
    Objects = SerializableListDescriptor(
        'Objects', TheObjectType, _collections_tags, _required, strict=DEFAULT_STRICT,
        docstring='The object collection')  # type: List[TheObjectType]

    def __init__(self, NumberOfObjectsInImage=None, NumberOfObjectsInScene=None,
                 LabelSource=None, Objects=None, **kwargs):
        """
        Parameters
        ----------
        NumberOfObjectsInImage : int
        NumberOfObjectsInScene : int
        LabelSource : LabelSourceType
        Objects : List[ObjectType]
        kwargs
            Other keyword arguments
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.NumberOfObjectsInImage = NumberOfObjectsInImage
        self.NumberOfObjectsInScene = NumberOfObjectsInScene
        self.LabelSource = LabelSource
        self.Objects = Objects
        super(ObjectInfoType, self).__init__(**kwargs)

    def set_image_location_from_sicd(
            self, sicd, layover_shift=False, populate_in_periphery=False,
            include_out_of_range=False, padding_fraction=None, minimum_pad=None):
        """
        Set the image location information with respect to the given SICD,
        assuming that the physical coordinates are populated. The `NumberOfObjectsInImage`
        will be set, and `NumberOfObjectsInScene` will be left unchanged.

        Parameters
        ----------
        sicd : SICDType
        layover_shift : bool
            Account for possible layover shift in calculated chip sizes?
        populate_in_periphery : bool
            Populate image information for objects on the periphery?
        include_out_of_range : bool
            Include the objects which are out of range (with no image location information)?
        padding_fraction : None|float
        minimum_pad : None|int|float
        """
        pass
