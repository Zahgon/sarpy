"""
Definition for the main NGA modified RDE/AFRL labeling object
"""

__classification__ = "UNCLASSIFIED"
__authors__ = "Thomas McCullough"

from typing import Optional
import os

from sarpy.io.xml.base import Serializable, parse_xml_from_string, parse_xml_from_file
from sarpy.io.xml.descriptors import SerializableDescriptor, StringDescriptor

from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd import SICDReader
from sarpy.io.general.utils import calculate_md5

from .base import DEFAULT_STRICT
from .CollectionInfo import CollectionInfoType
from .SubCollectionInfo import SubCollectionInfoType
from .ImageInfo import ImageInfoType
from .SensorInfo import SensorInfoType
from .FiducialInfo import FiducialInfoType
from .ObjectInfo import ObjectInfoType


_AFRL_SPECIFICATION_NAMESPACE = 'urn:AFRL_RDE:1.0.0'


class ResearchType(Serializable):
    _fields = (
        'MetadataVersion', 'DetailCollectionInfo', 'DetailSubCollectionInfo',
        'DetailImageInfo', 'DetailSensorInfo', 'DetailFiducialInfo', 'DetailObjectInfo')
    _required = (
        'MetadataVersion', 'DetailCollectionInfo', 'DetailSubCollectionInfo',
        'DetailImageInfo', 'DetailSensorInfo', 'DetailFiducialInfo', 'DetailObjectInfo')
    # descriptors
    MetadataVersion = StringDescriptor(
        'MetadataVersion', _required,
        docstring='The version number')  # type: str
    DetailCollectionInfo = SerializableDescriptor(
        'DetailCollectionInfo', CollectionInfoType, _required,
        docstring='High level information about the data collection'
    )  # type: Optional[CollectionInfoType]
    DetailSubCollectionInfo = SerializableDescriptor(
        'DetailSubCollectionInfo', SubCollectionInfoType, _required,
        docstring='Information about sub-division of the overall data collection'
    )  # type: Optional[SubCollectionInfoType]
    DetailImageInfo = SerializableDescriptor(
        'DetailImageInfo', ImageInfoType, _required,
        docstring='Information about the referenced image'
    )  # type: Optional[ImageInfoType]
    DetailSensorInfo = SerializableDescriptor(
        'DetailSensorInfo', SensorInfoType, _required,
        docstring='Information about the sensor'
    )  # type: Optional[SensorInfoType]
    DetailFiducialInfo = SerializableDescriptor(
        'DetailFiducialInfo', FiducialInfoType, _required,
        docstring='Information about the ground-truthed fiducials'
    )  # type: Optional[FiducialInfoType]
    DetailObjectInfo = SerializableDescriptor(
        'DetailObjectInfo', ObjectInfoType, _required,
        docstring='Information about the ground-truthed objects'
    )  # type: Optional[ObjectInfoType]

    def __init__(self, MetadataVersion='Unknown', DetailCollectionInfo=None,
                 DetailSubCollectionInfo=None, DetailImageInfo=None,
                 DetailSensorInfo=None, DetailFiducialInfo=None,
                 DetailObjectInfo=None, **kwargs):
        """
        Parameters
        ----------
        MetadataVersion : str
        DetailCollectionInfo : CollectionInfoType
        DetailSubCollectionInfo : SubCollectionInfoType
        DetailImageInfo : ImageInfoType
        DetailSensorInfo : SensorInfo
        DetailFiducialInfo : FiducialInfoType
        DetailObjectInfo : ObjectInfoType
        kwargs
            Other keyword arguments
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.MetadataVersion = MetadataVersion
        self.DetailCollectionInfo = DetailCollectionInfo
        self.DetailSubCollectionInfo = DetailSubCollectionInfo
        self.DetailImageInfo = DetailImageInfo
        self.DetailSensorInfo = DetailSensorInfo
        self.DetailFiducialInfo = DetailFiducialInfo
        self.DetailObjectInfo = DetailObjectInfo
        super(ResearchType, self).__init__(**kwargs)

    def to_xml_bytes(self, urn=None, tag='RESEARCH', check_validity=False, strict=DEFAULT_STRICT):
        if urn is None:
            urn = _AFRL_SPECIFICATION_NAMESPACE
        return super(ResearchType, self).to_xml_bytes(urn=urn, tag=tag, check_validity=check_validity, strict=strict)

    def to_xml_string(self, urn=None, tag='RESEARCH', check_validity=False, strict=DEFAULT_STRICT):
        pass

    def apply_sicd(self, sicd, base_file_name, layover_shift=False, populate_in_periphery=False, include_out_of_range=False,
                   padding_fraction=0.05, minimum_pad=0, md5_checksum=None):
        """
        Apply the given sicd to define all the relevant derived data, assuming
        that the starting point is physical ground truth populated, and image
        details and locations will be inferred. This modifies the structure in
        place.

        Parameters
        ----------
        sicd : SICDType
        base_file_name : str
        layover_shift : bool
        populate_in_periphery : bool
        include_out_of_range : bool
        padding_fraction : None|float
        minimum_pad : int|float
        md5_checksum : None|str
        """
        pass

    def apply_sicd_reader(
            self, sicd_reader, layover_shift=False, populate_in_periphery=False, include_out_of_range=False,
            padding_fraction=0.05, minimum_pad=0, populate_md5=True):
        """
        Apply the given sicd to define all the relevant derived data, assuming
        that the starting point is physical ground truth populated, and image
        details and locations will be inferred. This modifies the structure in
        place.

        Parameters
        ----------
        sicd_reader : SICDReader
        layover_shift : bool
        populate_in_periphery : bool
        include_out_of_range : bool
        padding_fraction : None|float
        minimum_pad : int|float
        populate_md5 : bool
        """
        pass

    @classmethod
    def from_xml_file(cls, file_path):
        """
        Construct the research object from an xml file path.

        Parameters
        ----------
        file_path : str

        Returns
        -------
        ResearchType
        """
        pass

    @classmethod
    def from_xml_string(cls, xml_string):
        """
        Construct the research object from an xml string.

        Parameters
        ----------
        xml_string : str|bytes

        Returns
        -------
        ResearchType
        """
        pass
