"""
Simple helper functions for constructing the NGA modified AFRL/RDE structure 
assuming either a known ground truth scenario or inferred analyst truth 
scenario.
"""

__classification__ = 'UNCLASSIFIED'
__author__ = "Thomas McCullough"

from typing import List, Dict, Union, Optional

import numpy

from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd import SICDReader

from sarpy.annotation.afrl_rde_elements.blocks import LabelSourceType
from sarpy.annotation.afrl_rde_elements.Research import ResearchType
from sarpy.annotation.afrl_rde_elements.CollectionInfo import CollectionInfoType
from sarpy.annotation.afrl_rde_elements.SubCollectionInfo import SubCollectionInfoType
from sarpy.annotation.afrl_rde_elements.ObjectInfo import ObjectInfoType, \
    TheObjectType, GeoLocationType as ObjectGeoLocation, \
    ImageLocationType as ObjectImageLocation, SizeType, OrientationType, \
    StringWithComponentType
from sarpy.annotation.afrl_rde_elements.FiducialInfo import FiducialInfoType, \
    TheFiducialType, GeoLocationType as FiducialGeoLocation, \
    ImageLocationType as FiducialImageLocation
from sarpy.annotation.afrl_rde_elements.ImageInfo import ImageInfoType
from sarpy.annotation.afrl_rde_elements.SensorInfo import SensorInfoType

from sarpy.annotation.label import LabelSchema, FileLabelCollection, LabelCollection, \
    LabelFeature, LabelProperties, LabelMetadata


class GroundTruthConstructor(object):
    """
    This class is a helper for performing a ground truth construction.
    """

    __slots__ = (
        '_collection_info', '_subcollection_info', '_label_source', '_objects', '_fiducials')

    def __init__(
            self, collection_info: CollectionInfoType,
            subcollection_info: SubCollectionInfoType,
            label_source: Optional[LabelSourceType] = None):
        """

        Parameters
        ----------
        collection_info : CollectionInfoType
        subcollection_info : SubCollectionInfoType
        label_source : None|LabelSourceType
        """

        self._collection_info = collection_info
        self._subcollection_info = subcollection_info
        if label_source is None:
            self._label_source = LabelSourceType(SourceType='Ground Truth', SourceID='Unspecified')
        else:
            self._label_source = label_source
        self._objects = []
        self._fiducials = []

    def add_fiducial(self, the_fiducial: TheFiducialType) -> None:
        """
        Adds the given fiducial to the collection.

        Parameters
        ----------
        the_fiducial : TheFiducialType
        """
        pass

    def add_fiducial_from_arguments(
            self,
            Name: str = None,
            SerialNumber: Optional[str] = None,
            FiducialType: Optional[str] = None,
            GeoLocation: FiducialGeoLocation = None) -> None:
        """
        Adds a fiducial to the collection.

        Parameters
        ----------
        Name : str
        SerialNumber : None|str
        FiducialType : None|str
        GeoLocation : FiducialGeoLocation
        """
        pass

    def add_object(
            self,
            the_object: TheObjectType) -> None:
        """
        Adds the given object to the collection.

        Parameters
        ----------
        the_object : TheObjectType
        """
        pass

    def add_object_from_arguments(
            self,
            SystemName: str = None,
            SystemComponent: Optional[str] = None,
            NATOName: Optional[str] = None,
            Function: Optional[str] = None,
            Version: Optional[str] = None,
            DecoyType: Optional[str] = None,
            SerialNumber: Optional[str] = None,
            ObjectClass: str = 'Unknown',
            ObjectSubClass: str = 'Unknown',
            ObjectTypeClass: str = 'Unknown',
            ObjectType: str = 'Unknown',
            ObjectLabel: str = None,
            Size: Optional[Union[SizeType, numpy.ndarray, list, tuple]] = None,
            Orientation: OrientationType = None,
            Articulation: Union[None, str, StringWithComponentType, List[StringWithComponentType]] = None,
            Configuration: Union[None, str, StringWithComponentType, List[StringWithComponentType]] = None,
            Accessories: Optional[str] = None,
            PaintScheme: Optional[str] = None,
            Camouflage: Optional[str] = None,
            Obscuration: Optional[str] = None,
            ObscurationPercent: Optional[float] = None,
            ImageLevelObscuration: Optional[str] = None,
            GeoLocation: ObjectGeoLocation = None,
            TargetToClutterRatio: Optional[str] = None,
            VisualQualityMetric: Optional[str] = None,
            UnderlyingTerrain: Optional[str] = None,
            OverlyingTerrain: Optional[str] = None,
            TerrainTexture: Optional[str] = None,
            SeasonalCover: Optional[str] = None) -> None:
        """
        Adds an object to the collection.

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
        Size : None|SizeType|numpy.ndarray|list|tuple
        Orientation : OrientationType
        Articulation : None|str|StringWithCompoundType|List[StringWithCompoundType]
        Configuration : None|str|StringWithCompoundType|List[StringWithCompoundType]
        Accessories : None|str
        PaintScheme : None|str
        Camouflage : None|str
        Obscuration : None|str
        ObscurationPercent : None|float
        ImageLevelObscuration : None|str
        GeoLocation : ObjectGeoLocation
        TargetToClutterRatio : None|str
        VisualQualityMetric : None|str
        UnderlyingTerrain : None|str
        OverlyingTerrain : None|str
        TerrainTexture : None|str
        SeasonalCover : None|str
        """
        pass

    def get_final_structure(self) -> ResearchType:
        """
        It is anticipated that this might be reused to localize for a whole series
        of different sicd files.

        Gets **a static copy** of the constructed AFRL Research structure. This has the
        provided CollectionInfo and SubCollectionInfo populated. It also
        has the ObjectInfo and FiducialInfo with the GeoLocation
        ground truth details that have been provided.

        No image location information has been populated, and there are no
        ImageInfo or SensorInfo populated, because these are independent
        of ground truth.

        Returns
        -------
        ResearchType
        """
        pass

    def localize_for_sicd(
            self,
            sicd: SICDType,
            base_sicd_file: str,
            layover_shift: bool = False,
            populate_in_periphery: bool = False,
            include_out_of_range: bool = False,
            padding_fraction: Optional[float] = 0.05,
            minimum_pad: Union[int, float] = 0,
            md5_checksum: Optional[str] = None):
        """
        Localize the AFRL structure for the given sicd structure.

        This returns **a static copy** of the AFRL structure, and this method
        can be repeatedly applied for a sequence of different sicd files which all
        apply to the same ground truth scenario.

        Parameters
        ----------
        sicd : SICDType
        base_sicd_file : str
        layover_shift : bool
        populate_in_periphery : bool
        include_out_of_range : bool
        padding_fraction : None|float
        minimum_pad : int|float
        md5_checksum : None|str

        Returns
        -------
        ResearchType
        """
        pass

    def localize_for_sicd_reader(
            self,
            sicd_reader: SICDReader,
            layover_shift: bool = False,
            populate_in_periphery: bool = False,
            include_out_of_range: bool = False,
            padding_fraction: Optional[float] = 0.05,
            minimum_pad: Union[int, float] = 0,
            populate_md5: bool = True):
        """
        Localize the AFRL structure for the given sicd file.

        This returns **a static copy** of the AFRL structure, and this method
        can be repeatedly applied for a sequence of different sicd files which all
        apply to the same ground truth scenario.

        Parameters
        ----------
        sicd_reader : SICDReader
        layover_shift : bool
        populate_in_periphery : bool
        include_out_of_range : bool
        padding_fraction : None|float
        minimum_pad : int|float
        populate_md5 : bool

        Returns
        -------
        ResearchType
        """
        pass


class AnalystTruthConstructor(object):
    """
    This class is a helper for performing an analyst truth construction.
    """

    __slots__ = (
        '_sicd', '_base_file',
        '_collection_info', '_subcollection_info', '_image_info', '_sensor_info',
        '_label_source', '_objects', '_fiducials',
        '_projection_type', '_proj_kwargs')

    def __init__(
            self,
            sicd: SICDType,
            base_file: str,
            collection_info: CollectionInfoType,
            subcollection_info: SubCollectionInfoType,
            label_source: Optional[LabelSourceType] = None,
            projection_type: str = 'HAE',
            proj_kwargs: Optional[Dict] = None,
            md5_checksum: Optional[str] = None):
        """

        Parameters
        ----------
        sicd : SICDType
        base_file : str
        collection_info : CollectionInfoType
        subcollection_info : SubCollectionInfoType
        label_source : None|LabelSourceType
        projection_type : str
            One of 'PLANE', 'HAE', or 'DEM'. The value of `proj_kwargs`
            will need to be appropriate.
        proj_kwargs : None|Dict
            The keyword arguments for the :func:`SICDType.project_image_to_ground_geo` method.
        md5_checksum : None|str
            The MD5 checksum of the full image file.
        """

        self._sicd = sicd
        self._base_file = base_file

        # TODO: should we create a decent shell for general Analyst Truth
        #  collection and subcollection info?
        self._collection_info = collection_info
        self._subcollection_info = subcollection_info
        self._image_info = ImageInfoType.from_sicd(self._sicd, self._base_file, md5_checksum=md5_checksum)
        self._sensor_info = SensorInfoType.from_sicd(self._sicd)
        if label_source is None:
            self._label_source = LabelSourceType(SourceType='Analyst Truth', SourceID='Unspecified')
        else:
            self._label_source = label_source

        self._objects = []
        self._fiducials = []

        self._projection_type = projection_type
        self._proj_kwargs = {} if proj_kwargs is None else proj_kwargs

    @property
    def image_info(self) -> ImageInfoType:
        """
        ImageInfoType: The basic image info object derived from the sicd
        """
        pass

    @property
    def sensor_info(self) -> SensorInfoType:
        """
        SensorInfoType: The basic sensor info object derived from the sicd.
        """
        pass

    def add_fiducial(self, the_fiducial: TheFiducialType) -> None:
        """
        Adds the given fiducial to the collection. Note that this object will be modified in place.

        Parameters
        ----------
        the_fiducial : TheFiducialType
        """
        pass

    def add_fiducial_from_arguments(
            self,
            Name: Optional[str] = None,
            SerialNumber: Optional[str] = None,
            FiducialType: Optional[str] = None,
            ImageLocation: FiducialImageLocation = None):
        """
        Adds a fiducial to the collection.

        Parameters
        ----------
        Name : None|str
        SerialNumber : None|str
        FiducialType : None|str
        ImageLocation : FiducialImageLocation
        """
        pass

    def add_object(
            self,
            the_object: TheObjectType,
            padding_fraction: Optional[float] = 0.05,
            minimum_pad: Union[int, float] = 0):
        """
        Adds the object to the collection. Note that this object will be modified in place.

        Parameters
        ----------
        the_object : TheObjectType
        padding_fraction : None|float
            Default fraction of box dimension by which to pad.
        minimum_pad : float|int
            The minimum number of pixels by which to pad for the chip
        """
        pass

    def add_object_from_arguments(
            self,
            padding_fraction: float = 0.05,
            minimum_pad: Union[int, float] = 0,
            SystemName: str = None,
            SystemComponent: Optional[str] = None,
            NATOName: Optional[str] = None,
            Function: Optional[str] = None,
            Version: Optional[str] = None,
            DecoyType: Optional[str] = None,
            SerialNumber: Optional[str] = None,
            ObjectClass: str = 'Unknown',
            ObjectSubClass: str = 'Unknown',
            ObjectTypeClass: str = 'Unknown',
            ObjectType: str = 'Unknown',
            ObjectLabel: str = None,
            Size: Union[None, SizeType, numpy.ndarray, list, tuple] = None,
            Orientation: OrientationType = None,
            Articulation: Union[None, str, StringWithComponentType, List[StringWithComponentType]] = None,
            Configuration: Union[None, str, StringWithComponentType, List[StringWithComponentType]] = None,
            Accessories: Optional[str] = None,
            PaintScheme: Optional[str] = None,
            Camouflage: Optional[str] = None,
            Obscuration: Optional[str] = None,
            ObscurationPercent: Optional[float] = None,
            ImageLevelObscuration: Optional[str] = None,
            ImageLocation: ObjectImageLocation = None,
            TargetToClutterRatio: Optional[str] = None,
            VisualQualityMetric: Optional[str] = None,
            UnderlyingTerrain: Optional[str] = None,
            OverlyingTerrain: Optional[str] = None,
            TerrainTexture: Optional[str] = None,
            SeasonalCover: Optional[str] = None) -> None:
        """
        Adds an object to the collection.

        Parameters
        ----------
        padding_fraction : None|float
            Default fraction of box dimension by which to pad.
        minimum_pad : float|int
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
        Size : None|SizeType|numpy.ndarray|list|tuple
        Orientation : OrientationType
        Articulation : None|str|StringWithComponentType|List[StringWithComponentType]
        Configuration : None|str|StringWithComponentType|List[StringWithComponentType]
        Accessories : None|str
        PaintScheme : None|str
        Camouflage : None|str
        Obscuration : None|str
        ObscurationPercent : None|float
        ImageLevelObscuration : None|str
        ImageLocation : ObjectImageLocation
        TargetToClutterRatio : None|str
        VisualQualityMetric : None|str
        UnderlyingTerrain : None|str
        OverlyingTerrain : None|str
        TerrainTexture : None|str
        SeasonalCover : None|str
        """
        pass

    def get_final_structure(self) -> ResearchType:
        """
        This is not anticipated to be reused, so the raw progress to date is returned.
        Care should be taken in modifying the returned structure directly.

        Returns
        -------
        ResearchType
        """
        pass


def convert_afrl_to_native(
        research: ResearchType,
        include_chip: bool = False) -> FileLabelCollection:
    """
    Converts an AFRL structure to a label structure for simple viewing.

    Parameters
    ----------
    research : ResearchType
    include_chip : bool
        Include the chip definition in the geometry structure?

    Returns
    -------
    FileLabelCollection
    """
    pass
