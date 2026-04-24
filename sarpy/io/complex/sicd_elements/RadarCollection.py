"""
The RadarCollectionType definition.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


from typing import List, Union, Optional, Dict, Tuple
import logging

import numpy

from sarpy.io.xml.base import Serializable, Arrayable, SerializableArray, \
    ParametersCollection, parse_float
from sarpy.io.xml.descriptors import StringDescriptor, StringEnumDescriptor, \
    FloatDescriptor, IntegerDescriptor, SerializableDescriptor, \
    SerializableArrayDescriptor, UnitVectorDescriptor, ParametersDescriptor

from .base import DEFAULT_STRICT, FLOAT_FORMAT, \
    SerializableCPArrayDescriptor, SerializableCPArray
from .blocks import XYZType, LatLonHAECornerRestrictionType, \
    POLARIZATION1_VALUES, POLARIZATION2_VALUES, DUAL_POLARIZATION_VALUES
from .utils import polstring_version_required

import sarpy.geometry.geocoords as geocoords


logger = logging.getLogger(__name__)


def get_band_name(freq: float) -> str:
    """
    Gets the band names associated with the given frequency (in Hz).

    Parameters
    ----------
    freq : float
        The frequency in Hz.

    Returns
    -------
    str
    """

    if freq is None:
        return 'UN'
    elif 3e6 <= freq < 3e7:
        return 'HF'
    elif 3e7 <= freq < 3e8:
        return 'VHF'
    elif 3e8 <= freq < 1e9:
        return 'UHF'
    elif 1e9 <= freq < 2e9:
        return 'L'
    elif 2e9 <= freq < 4e9:
        return 'S'
    elif 4e9 <= freq < 8e9:
        return 'C'
    elif 8e9 <= freq < 1.2e10:
        return 'X'
    elif 1.2e10 <= freq < 1.8e10:
        return 'KU'
    elif 1.8e10 <= freq < 2.7e10:
        return 'K'
    elif 2.7e10 <= freq < 4e10:
        return 'KA'
    elif 4e10 <= freq < 7.5e10:
        return 'V'
    elif 7.5e10 <= freq < 1.1e11:
        return 'W'
    elif 1.1e11 <= freq < 3e11:
        return 'MM'
    else:
        return 'UN'


class TxFrequencyType(Serializable, Arrayable):
    """
    The transmit frequency range.
    """

    _fields = ('Min', 'Max')
    _required = _fields
    _numeric_format = {'Min': FLOAT_FORMAT, 'Max': FLOAT_FORMAT}
    # descriptors
    Min = FloatDescriptor(
        'Min', _required, strict=DEFAULT_STRICT,
        docstring='The transmit minimum frequency in Hz.')  # type: float
    Max = FloatDescriptor(
        'Max', _required, strict=DEFAULT_STRICT,
        docstring='The transmit maximum frequency in Hz.')  # type: float

    def __init__(
            self,
            Min: float = None,
            Max: float = None,
            **kwargs):
        """

        Parameters
        ----------
        Min : float
        Max : float
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.Min, self.Max = Min, Max
        super(TxFrequencyType, self).__init__(**kwargs)

    @property
    def center_frequency(self) -> Optional[float]:
        """
        None|float: The center frequency
        """
        pass

    def _apply_reference_frequency(self, reference_frequency: float):
        pass

    def _basic_validity_check(self) -> bool:
        condition = super(TxFrequencyType, self)._basic_validity_check()
        if self.Min is not None and self.Max is not None and self.Max < self.Min:
            self.log_validity_error(
                'Invalid frequency bounds Min ({}) > Max ({})'.format(self.Min, self.Max))
            condition = False
        return condition

    def get_band_abbreviation(self) -> str:
        """
        Gets the band abbreviation for the suggested name.

        Returns
        -------
        str
        """

        band_name = get_band_name(self.center_frequency)
        return band_name + '_'*(3 - len(band_name))

    def get_array(self, dtype=numpy.float64) -> numpy.ndarray:
        """
        Gets an array representation of the data.

        Parameters
        ----------
        dtype : str|numpy.dtype|numpy.number
            data type of the return

        Returns
        -------
        numpy.ndarray
            data array with appropriate entry order
        """

        return numpy.array([self.Min, self.Max], dtype=dtype)

    @classmethod
    def from_array(cls, array: Union[numpy.ndarray, list, tuple]):
        """
        Create from an array type entry.

        Parameters
        ----------
        array: numpy.ndarray|list|tuple
            assumed [Min, Max]

        Returns
        -------
        LatLonType
        """

        if array is None:
            return None
        if isinstance(array, (numpy.ndarray, list, tuple)):
            if len(array) < 2:
                raise ValueError('Expected array to be of length 2, and received {}'.format(len(array)))
            return cls(Min=array[0], Max=array[1])
        raise ValueError('Expected array to be numpy.ndarray, list, or tuple, got {}'.format(type(array)))


class WaveformParametersType(Serializable):
    """
    Transmit and receive demodulation waveform parameters.
    """

    _fields = (
        'TxPulseLength', 'TxRFBandwidth', 'TxFreqStart', 'TxFMRate', 'RcvDemodType', 'RcvWindowLength',
        'ADCSampleRate', 'RcvIFBandwidth', 'RcvFreqStart', 'RcvFMRate', 'index')
    _required = ('index', )
    _set_as_attribute = ('index', )
    _numeric_format = {
        'TxPulseLength': FLOAT_FORMAT, 'TxRFBandwidth': '0.17E', 'TxFreqStart': '0.17E',
        'TxFMRate': '0.17E', 'RcvWindowLength': FLOAT_FORMAT, 'ADCSampleRate': '0.17E',
        'RcvIFBandwidth': '0.17E', 'RcvFreqStart': '0.17E', 'RcvFMRate': '0.17E'}

    # descriptors
    TxPulseLength = FloatDescriptor(
        'TxPulseLength', _required, strict=DEFAULT_STRICT,
        docstring='Transmit pulse length in seconds.')  # type: float
    TxRFBandwidth = FloatDescriptor(
        'TxRFBandwidth', _required, strict=DEFAULT_STRICT,
        docstring='Transmit RF bandwidth of the transmit pulse in Hz.')  # type: float
    TxFreqStart = FloatDescriptor(
        'TxFreqStart', _required, strict=DEFAULT_STRICT,
        docstring='Transmit Start frequency for Linear FM waveform in Hz, may be relative '
                  'to reference frequency.')  # type: float
    TxFMRate = FloatDescriptor(
        'TxFMRate', _required, strict=DEFAULT_STRICT,
        docstring='Transmit FM rate for Linear FM waveform in Hz/second.')  # type: float
    RcvWindowLength = FloatDescriptor(
        'RcvWindowLength', _required, strict=DEFAULT_STRICT,
        docstring='Receive window duration in seconds.')  # type: float
    ADCSampleRate = FloatDescriptor(
        'ADCSampleRate', _required, strict=DEFAULT_STRICT,
        docstring='Analog-to-Digital Converter sampling rate in samples/second.')  # type: float
    RcvIFBandwidth = FloatDescriptor(
        'RcvIFBandwidth', _required, strict=DEFAULT_STRICT,
        docstring='Receive IF bandwidth in Hz.')  # type: float
    RcvFreqStart = FloatDescriptor(
        'RcvFreqStart', _required, strict=DEFAULT_STRICT,
        docstring='Receive demodulation start frequency in Hz, may be relative to reference frequency.')  # type: float
    index = IntegerDescriptor(
        'index', _required, strict=False, docstring="The array index.")  # type: int

    def __init__(
            self,
            TxPulseLength: Optional[float] = None,
            TxRFBandwidth: Optional[float] = None,
            TxFreqStart: Optional[float] = None,
            TxFMRate: Optional[float] = None,
            RcvDemodType: Optional[str] = None,
            RcvWindowLength: Optional[float] = None,
            ADCSampleRate: Optional[float] = None,
            RcvIFBandwidth: Optional[float] = None,
            RcvFreqStart: Optional[float] = None,
            RcvFMRate: Optional[float] = None,
            index: int = None,
            **kwargs):
        """

        Parameters
        ----------
        TxPulseLength : float
        TxRFBandwidth : float
        TxFreqStart : float
        TxFMRate : float
        RcvDemodType : str
        RcvWindowLength : float
        ADCSampleRate : float
        RcvIFBandwidth : float
        RcvFreqStart : float
        RcvFMRate : float
        index : int
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self._RcvFMRate = None
        self.TxPulseLength, self.TxRFBandwidth = TxPulseLength, TxRFBandwidth
        self.TxFreqStart, self.TxFMRate = TxFreqStart, TxFMRate
        self.RcvWindowLength = RcvWindowLength
        self.ADCSampleRate = ADCSampleRate
        self.RcvIFBandwidth = RcvIFBandwidth
        self.RcvFreqStart = RcvFreqStart
        # NB: self.RcvDemodType is read only.
        if RcvDemodType == 'CHIRP' and RcvFMRate is None:
            self.RcvFMRate = 0.0
        elif RcvDemodType == 'STRETCH' and RcvFMRate is not None:
            self.RcvFMRate = RcvFMRate
        else:
            self.RcvFMRate = None
        self.index = index
        super(WaveformParametersType, self).__init__(**kwargs)

    @property
    def RcvDemodType(self) -> Optional[str]:
        """
        str: READ ONLY. Receive demodulation used when Linear FM waveform is
        used on transmit. This value is derived form the value of `RcvFMRate`.

        * `None` - `RcvFMRate` is `None`.

        * `'CHIRP'` - `RcvFMRate=0`.

        * `'STRETCH'` - `RcvFMRate` is non-zero.
        """
        pass

    @property
    def RcvFMRate(self) -> Optional[float]:
        """
        float: Receive FM rate in Hz/sec. Also, determines the value of `RcvDemodType`. **Optional.**
        """
        pass

    @RcvFMRate.setter
    def RcvFMRate(self, value: Optional[float]):
        pass

    def _basic_validity_check(self) -> bool:
        valid = super(WaveformParametersType, self)._basic_validity_check()
        return valid

    def derive(self):
        """
        Populate derived data in `WaveformParametersType`.

        Returns
        -------
        None
        """
        pass

    def _apply_reference_frequency(self, reference_frequency: float):
        pass


class TxStepType(Serializable):
    """
    Transmit sequence step details.
    """

    _fields = ('WFIndex', 'TxPolarization', 'index')
    _required = ('index', )
    _set_as_attribute = ('index', )
    # descriptors
    WFIndex = IntegerDescriptor(
        'WFIndex', _required, strict=DEFAULT_STRICT,
        docstring='The waveform number for this step.')  # type: int
    TxPolarization = StringEnumDescriptor(
        'TxPolarization', POLARIZATION1_VALUES, _required, strict=DEFAULT_STRICT,
        docstring='Transmit signal polarization for this step.')  # type: str
    index = IntegerDescriptor(
        'index', _required, strict=DEFAULT_STRICT,
        docstring='The step index')  # type: int

    def __init__(
            self,
            WFIndex: Optional[int] = None,
            TxPolarization: Optional[str] = None,
            index: int = None,
            **kwargs):
        """

        Parameters
        ----------
        WFIndex : int
        TxPolarization : str
        index : int
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.WFIndex = WFIndex
        self.TxPolarization = TxPolarization
        self.index = index
        super(TxStepType, self).__init__(**kwargs)


class ChanParametersType(Serializable):
    """
    Transmit receive sequence step details.
    """

    _fields = ('TxRcvPolarization', 'RcvAPCIndex', 'index')
    _required = ('TxRcvPolarization', 'index', )
    _set_as_attribute = ('index', )
    # descriptors
    TxRcvPolarization = StringEnumDescriptor(
        'TxRcvPolarization', DUAL_POLARIZATION_VALUES, _required, strict=DEFAULT_STRICT,
        docstring='Combined Transmit and Receive signal polarization for the channel.')  # type: str
    RcvAPCIndex = IntegerDescriptor(
        'RcvAPCIndex', _required, strict=DEFAULT_STRICT,
        docstring='Index of the Receive Aperture Phase Center (Rcv APC). Only include if Receive APC position '
                  'polynomial(s) are included.')  # type: int
    index = IntegerDescriptor(
        'index', _required, strict=DEFAULT_STRICT, docstring='The parameter index')  # type: int

    def __init__(
            self,
            TxRcvPolarization: Optional[str] = None,
            RcvAPCIndex: Optional[int] = None,
            index: int = None,
            **kwargs):
        """

        Parameters
        ----------
        TxRcvPolarization : str
        RcvAPCIndex : int
        index : int
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.TxRcvPolarization = TxRcvPolarization
        self.RcvAPCIndex = RcvAPCIndex
        self.index = index
        super(ChanParametersType, self).__init__(**kwargs)

    def get_transmit_polarization(self) -> Optional[str]:
        pass

    def version_required(self) -> Tuple[int, int, int]:
        """
        What SICD version is required?

        Returns
        -------
        tuple
        """
        pass


class ReferencePointType(Serializable):
    """The reference point definition"""
    _fields = ('ECF', 'Line', 'Sample', 'name')
    _required = ('ECF', 'Line', 'Sample')
    _set_as_attribute = ('name', )
    _numeric_format = {'Line': FLOAT_FORMAT, 'Sample': FLOAT_FORMAT}
    # descriptors
    ECF = SerializableDescriptor(
        'ECF', XYZType, _required, strict=DEFAULT_STRICT,
        docstring='The geographical coordinates for the reference point.')  # type: XYZType
    Line = FloatDescriptor(
        'Line', _required, strict=DEFAULT_STRICT,
        docstring='The reference point line index.')  # type: float
    Sample = FloatDescriptor(
        'Sample', _required, strict=DEFAULT_STRICT,
        docstring='The reference point sample index.')  # type: float
    name = StringDescriptor(
        'name', _required, strict=DEFAULT_STRICT,
        docstring='The reference point name.')  # type: str

    def __init__(
            self,
            ECF: Union[XYZType, numpy.ndarray, list, tuple] = None,
            Line: float = None,
            Sample: float = None,
            name: Optional[str] = None,
            **kwargs):
        """

        Parameters
        ----------
        ECF : XYZType|numpy.ndarray|list|tuple
        Line : float
        Sample : float
        name : str
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.ECF = ECF
        self.Line = Line
        self.Sample = Sample
        self.name = name
        super(ReferencePointType, self).__init__(**kwargs)


class XDirectionType(Serializable):
    """The X direction of the collect"""
    _fields = ('UVectECF', 'LineSpacing', 'NumLines', 'FirstLine')
    _required = _fields
    _numeric_format = {'LineSpacing': FLOAT_FORMAT, }
    # descriptors
    UVectECF = UnitVectorDescriptor(
        'UVectECF', XYZType, _required, strict=DEFAULT_STRICT,
        docstring='The unit vector in the X direction.')  # type: XYZType
    LineSpacing = FloatDescriptor(
        'LineSpacing', _required, strict=DEFAULT_STRICT,
        docstring='The collection line spacing in the X direction in meters.')  # type: float
    NumLines = IntegerDescriptor(
        'NumLines', _required, strict=DEFAULT_STRICT,
        docstring='The number of lines in the X direction.')  # type: int
    FirstLine = IntegerDescriptor(
        'FirstLine', _required, strict=DEFAULT_STRICT,
        docstring='The first line index.')  # type: int

    def __init__(
            self,
            UVectECF: Union[XYZType, numpy.ndarray, list, tuple] = None,
            LineSpacing: int = None,
            NumLines: int = None,
            FirstLine: int = None,
            **kwargs):
        """

        Parameters
        ----------
        UVectECF : XYZType|numpy.ndarray|list|tuple
        LineSpacing : float
        NumLines : int
        FirstLine : int
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.UVectECF = UVectECF
        self.LineSpacing = LineSpacing
        self.NumLines = NumLines
        self.FirstLine = FirstLine
        super(XDirectionType, self).__init__(**kwargs)


class YDirectionType(Serializable):
    """The Y direction of the collect"""
    _fields = ('UVectECF', 'SampleSpacing', 'NumSamples', 'FirstSample')
    _required = _fields
    _numeric_format = {'SampleSpacing': FLOAT_FORMAT, }
    # descriptors
    UVectECF = UnitVectorDescriptor(
        'UVectECF', XYZType, _required, strict=DEFAULT_STRICT,
        docstring='The unit vector in the Y direction.')  # type: XYZType
    SampleSpacing = FloatDescriptor(
        'SampleSpacing', _required, strict=DEFAULT_STRICT,
        docstring='The collection sample spacing in the Y direction in meters.')  # type: float
    NumSamples = IntegerDescriptor(
        'NumSamples', _required, strict=DEFAULT_STRICT,
        docstring='The number of samples in the Y direction.')  # type: int
    FirstSample = IntegerDescriptor(
        'FirstSample', _required, strict=DEFAULT_STRICT,
        docstring='The first sample index.')  # type: int

    def __init__(
            self,
            UVectECF: Union[XYZType, numpy.ndarray, list, tuple] = None,
            SampleSpacing: float = None,
            NumSamples: int = None,
            FirstSample: int = None,
            **kwargs):
        """

        Parameters
        ----------
        UVectECF : XYZType|numpy.ndarray|list|tuple
        SampleSpacing : float
        NumSamples : int
        FirstSample : int
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.UVectECF = UVectECF
        self.SampleSpacing = SampleSpacing
        self.NumSamples = NumSamples
        self.FirstSample = FirstSample
        super(YDirectionType, self).__init__(**kwargs)


class SegmentArrayElement(Serializable):
    """The reference point definition"""
    _fields = ('StartLine', 'StartSample', 'EndLine', 'EndSample', 'Identifier', 'index')
    _required = _fields
    _set_as_attribute = ('index', )
    # descriptors
    StartLine = IntegerDescriptor(
        'StartLine', _required, strict=DEFAULT_STRICT,
        docstring='The starting line number of the segment.')  # type: int
    StartSample = IntegerDescriptor(
        'StartSample', _required, strict=DEFAULT_STRICT,
        docstring='The starting sample number of the segment.')  # type: int
    EndLine = IntegerDescriptor(
        'EndLine', _required, strict=DEFAULT_STRICT,
        docstring='The ending line number of the segment.')  # type: int
    EndSample = IntegerDescriptor(
        'EndSample', _required, strict=DEFAULT_STRICT,
        docstring='The ending sample number of the segment.')  # type: int
    Identifier = StringDescriptor(
        'Identifier', _required, strict=DEFAULT_STRICT,
        docstring='Identifier for the segment data boundary.')
    index = IntegerDescriptor(
        'index', _required, strict=DEFAULT_STRICT,
        docstring='The array index.')  # type: int

    def __init__(
            self,
            StartLine: int = None,
            StartSample: int = None,
            EndLine: int = None,
            EndSample: int = None,
            Identifier: str = None,
            index: int = None,
            **kwargs):
        """

        Parameters
        ----------
        StartLine : int
        StartSample : int
        EndLine : int
        EndSample : int
        Identifier : str
        index : int
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.StartLine, self.EndLine = StartLine, EndLine
        self.StartSample, self.EndSample = StartSample, EndSample
        self.Identifier = Identifier
        self.index = index
        super(SegmentArrayElement, self).__init__(**kwargs)


class ReferencePlaneType(Serializable):
    """
    The reference plane.
    """

    _fields = ('RefPt', 'XDir', 'YDir', 'SegmentList', 'Orientation')
    _required = ('RefPt', 'XDir', 'YDir')
    _collections_tags = {'SegmentList': {'array': True, 'child_tag': 'Segment'}}
    # other class variable
    _ORIENTATION_VALUES = ('UP', 'DOWN', 'LEFT', 'RIGHT', 'ARBITRARY')
    # descriptors
    RefPt = SerializableDescriptor(
        'RefPt', ReferencePointType, _required, strict=DEFAULT_STRICT,
        docstring='The reference point.')  # type: ReferencePointType
    XDir = SerializableDescriptor(
        'XDir', XDirectionType, _required, strict=DEFAULT_STRICT,
        docstring='The X direction collection plane parameters.')  # type: XDirectionType
    YDir = SerializableDescriptor(
        'YDir', YDirectionType, _required, strict=DEFAULT_STRICT,
        docstring='The Y direction collection plane parameters.')  # type: YDirectionType
    SegmentList = SerializableArrayDescriptor(
        'SegmentList', SegmentArrayElement, _collections_tags, _required, strict=DEFAULT_STRICT,
        docstring='The segment array.')  # type: Union[SerializableArray, List[SegmentArrayElement]]
    Orientation = StringEnumDescriptor(
        'Orientation', _ORIENTATION_VALUES, _required, strict=DEFAULT_STRICT,
        docstring='Describes the shadow intent of the display plane.')  # type: str

    def __init__(
            self,
            RefPt: ReferencePointType = None,
            XDir: XDirectionType = None,
            YDir: YDirectionType = None,
            SegmentList: Union[SerializableArray, List[SegmentArrayElement]] = None,
            Orientation: Optional[str] = None,
            **kwargs):
        """

        Parameters
        ----------
        RefPt : ReferencePointType
        XDir : XDirectionType
        YDir : YDirectionType
        SegmentList : SerializableArray|List[SegmentArrayElement]
        Orientation : str
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.RefPt = RefPt
        self.XDir, self.YDir = XDir, YDir
        self.SegmentList = SegmentList
        self.Orientation = Orientation
        super(ReferencePlaneType, self).__init__(**kwargs)

    def get_ecf_corner_array(self) -> numpy.ndarray:
        """
        Use the XDir and YDir definitions to return the corner points in ECF coordinates as a `4x3` array.

        Returns
        -------
        numpy.ndarray
            The corner points of the collection area, with order following the AreaType order convention.
        """
        pass


class AreaType(Serializable):
    """
    The collection area.
    """

    _fields = ('Corner', 'Plane')
    _required = ('Corner', )
    _collections_tags = {
        'Corner': {'array': True, 'child_tag': 'ACP'}, }
    # descriptors
    Corner = SerializableCPArrayDescriptor(
        'Corner', LatLonHAECornerRestrictionType, _collections_tags, _required, strict=DEFAULT_STRICT,
        docstring='The collection area corner point definition array.'
    )  # type: Union[SerializableCPArray, List[LatLonHAECornerRestrictionType]]
    Plane = SerializableDescriptor(
        'Plane', ReferencePlaneType, _required, strict=DEFAULT_STRICT,
        docstring='A rectangular area in a geo-located display plane.')  # type: ReferencePlaneType

    def __init__(
            self,
            Corner: Union[SerializableCPArray, List[LatLonHAECornerRestrictionType], numpy.ndarray, list, tuple] = None,
            Plane: ReferencePlaneType = None,
            **kwargs):
        """

        Parameters
        ----------
        Corner : SerializableCPArray|List[LatLonHAECornerRestrictionType]|numpy.ndarray|list|tuple
        Plane : ReferencePlaneType
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.Corner = Corner
        self.Plane = Plane
        super(AreaType, self).__init__(**kwargs)
        self.derive()

    def _derive_corner_from_plane(self):
        # try to define the corner points - for SICD 0.5.
        pass

    def derive(self):
        """
        Derive the corner points from the plane, if necessary.

        Returns
        -------
        None
        """
        pass


class RadarCollectionType(Serializable):
    """The Radar Collection Type"""
    _fields = (
        'TxFrequency', 'RefFreqIndex', 'Waveform', 'TxPolarization', 'TxSequence', 'RcvChannels', 'Area', 'Parameters')
    _required = ('TxFrequency', 'TxPolarization', 'RcvChannels')
    _collections_tags = {
        'Waveform': {'array': True, 'child_tag': 'WFParameters'},
        'TxSequence': {'array': True, 'child_tag': 'TxStep'},
        'RcvChannels': {'array': True, 'child_tag': 'ChanParameters'},
        'Parameters': {'array': False, 'child_tag': 'Parameter'}}
    # descriptors
    TxFrequency = SerializableDescriptor(
        'TxFrequency', TxFrequencyType, _required, strict=DEFAULT_STRICT,
        docstring='The transmit frequency range.')  # type: TxFrequencyType
    RefFreqIndex = IntegerDescriptor(
        'RefFreqIndex', _required, strict=DEFAULT_STRICT,
        docstring='The reference frequency index, if applicable. If present and non-zero, '
                  'all (most) RF frequency values are expressed as offsets from a reference '
                  'frequency.')  # type: int
    Waveform = SerializableArrayDescriptor(
        'Waveform', WaveformParametersType, _collections_tags, _required,
        strict=DEFAULT_STRICT, minimum_length=1,
        docstring='Transmit and receive demodulation waveform parameters.'
    )  # type: Union[SerializableArray, List[WaveformParametersType]]
    TxPolarization = StringEnumDescriptor(
        'TxPolarization', POLARIZATION1_VALUES, _required, strict=DEFAULT_STRICT,
        docstring='The transmit polarization.')  # type: str
    TxSequence = SerializableArrayDescriptor(
        'TxSequence', TxStepType, _collections_tags, _required, strict=DEFAULT_STRICT, minimum_length=1,
        docstring='The transmit sequence parameters array. If present, indicates the transmit signal steps through '
                  'a repeating sequence of waveforms and/or polarizations. '
                  'One step per Inter-Pulse Period.')  # type: Union[None, SerializableArray, List[TxStepType]]
    RcvChannels = SerializableArrayDescriptor(
        'RcvChannels', ChanParametersType, _collections_tags,
        _required, strict=DEFAULT_STRICT, minimum_length=1,
        docstring='Receive data channel parameters.')  # type: Union[SerializableArray, List[ChanParametersType]]
    Area = SerializableDescriptor(
        'Area', AreaType, _required, strict=DEFAULT_STRICT,
        docstring='The imaged area covered by the collection.')  # type: AreaType
    Parameters = ParametersDescriptor(
        'Parameters', _collections_tags, _required, strict=DEFAULT_STRICT,
        docstring='A parameters collections.')  # type: ParametersCollection

    def __init__(
            self,
            TxFrequency: TxFrequencyType = None,
            RefFreqIndex: Optional[int] = None,
            Waveform: Union[None, SerializableArray, List[WaveformParametersType]] = None,
            TxPolarization: str = None,
            TxSequence: Union[None, SerializableArray, List[TxStepType]] = None,
            RcvChannels: Union[SerializableArray, List[ChanParametersType]] = None,
            Area: Optional[AreaType] = None,
            Parameters: Union[None, ParametersCollection, Dict] = None,
            **kwargs):
        """

        Parameters
        ----------
        TxFrequency : TxFrequencyType|numpy.ndarray|list|tuple
        RefFreqIndex : int
        Waveform : SerializableArray|List[WaveformParametersType]
        TxPolarization : str
        TxSequence : SerializableArray|List[TxStepType]
        RcvChannels : SerializableArray|List[ChanParametersType]
        Area : AreaType
        Parameters : ParametersCollection|dict
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.TxFrequency = TxFrequency
        self.RefFreqIndex = RefFreqIndex
        self.Waveform = Waveform
        self.TxPolarization = TxPolarization
        self.TxSequence = TxSequence
        self.RcvChannels = RcvChannels
        self.Area = Area
        self.Parameters = Parameters
        super(RadarCollectionType, self).__init__(**kwargs)

    def derive(self):
        """
        Populates derived data in RadarCollection. Expected to be called by `SICD` parent.

        Returns
        -------
        None
        """
        pass

    def _derive_tx_polarization(self):
        pass

    def _derive_tx_frequency(self):
        pass

    def _derive_wf_params(self):
        pass

    def _apply_reference_frequency(self, reference_frequency):
        """
        If the reference frequency is used, adjust the necessary fields accordingly.
        Expected to be called by `SICD` parent.

        Parameters
        ----------
        reference_frequency : float
            The reference frequency.

        Returns
        -------
        None
        """
        pass

    def get_polarization_abbreviation(self):
        """
        Gets the polarization collection abbreviation for the suggested name.

        Returns
        -------
        str
        """

        if self.RcvChannels is None:
            pol_count = 0
        else:
            pol_count = len(self.RcvChannels)
        if pol_count == 1:
            return 'S'
        elif pol_count == 2:
            return 'D'
        elif pol_count == 3:
            return 'T'
        elif pol_count > 3:
            return 'Q'
        else:
            return 'U'

    def _check_frequency(self):
        # type: () -> bool

        if self.RefFreqIndex is not None:
            return True

        if self.TxFrequency is not None and self.TxFrequency.Min is not None \
                and self.TxFrequency.Min <= 0:
            self.log_validity_error(
                'TxFrequency.Min is negative, but RefFreqIndex is not populated.')
            return False
        return True

    def _check_tx_sequence(self):
        # type: () -> bool

        cond = True
        if self.TxPolarization == 'SEQUENCE' and self.TxSequence is None:
            self.log_validity_error(
                'TxPolarization is populated as "SEQUENCE", but TxSequence is not populated.')
            cond = False
        if self.TxSequence is not None:
            if self.TxPolarization != 'SEQUENCE':
                self.log_validity_error(
                    'TxSequence is populated, but TxPolarization is populated as {}'.format(self.TxPolarization))
                cond = False
            tx_pols = list(set([entry.TxPolarization for entry in self.TxSequence]))
            if len(tx_pols) == 1:
                self.log_validity_error(
                    'TxSequence is populated, but the only unique TxPolarization '
                    'among the entries is {}'.format(tx_pols[0]))
                cond = False
        return cond

    def _check_waveform_parameters(self):
        """
        Validate the waveform parameters for consistency.

        Returns
        -------
        bool
        """

        def validate_entry(index, waveform):
            # type: (int, WaveformParametersType) -> bool
            this_cond = True
            try:
                if abs(waveform.TxRFBandwidth/(waveform.TxPulseLength*waveform.TxFMRate) - 1) > 1e-3:
                    self.log_validity_error(
                        'The TxRFBandwidth, TxPulseLength, and TxFMRate parameters of Waveform '
                        'entry {} are inconsistent'.format(index+1))
                    this_cond = False
            except (AttributeError, ValueError, TypeError):
                pass

            if waveform.RcvDemodType == 'CHIRP' and waveform.RcvFMRate != 0:
                self.log_validity_error(
                    'RcvDemodType == "CHIRP" and RcvFMRate != 0 in Waveform entry {}'.format(index+1))
                this_cond = False
            if waveform.RcvDemodType == 'STRETCH' and \
                    waveform.RcvFMRate is not None and waveform.TxFMRate is not None and \
                    abs(waveform.RcvFMRate/waveform.TxFMRate - 1) > 1e-3:
                self.log_validity_warning(
                    'RcvDemodType = "STRETCH", RcvFMRate = {}, and TxFMRate = {} in '
                    'Waveform entry {}. The RcvFMRate and TxFMRate should very likely '
                    'be the same.'.format(waveform.RcvFMRate, waveform.TxFMRate, index+1))

            if self.RefFreqIndex is None:
                if waveform.TxFreqStart is not None and waveform.TxFreqStart <= 0:
                    self.log_validity_error(
                        'TxFreqStart is negative in Waveform entry {}, but RefFreqIndex '
                        'is not populated.'.format(index+1))
                    this_cond = False
                if waveform.RcvFreqStart is not None and waveform.RcvFreqStart <= 0:
                    self.log_validity_error(
                        'RcvFreqStart is negative in Waveform entry {}, but RefFreqIndex '
                        'is not populated.'.format(index + 1))
                    this_cond = False
            if waveform.TxPulseLength is not None and waveform.RcvWindowLength is not None and \
                    waveform.TxPulseLength > waveform.RcvWindowLength:
                self.log_validity_error(
                    'TxPulseLength ({}) is longer than RcvWindowLength ({}) in '
                    'Waveform entry {}'.format(waveform.TxPulseLength, waveform.RcvWindowLength, index+1))
                this_cond = False
            if waveform.RcvIFBandwidth is not None and waveform.ADCSampleRate is not None and \
                    waveform.RcvIFBandwidth > waveform.ADCSampleRate:
                self.log_validity_error(
                    'RcvIFBandwidth ({}) is longer than ADCSampleRate ({}) in '
                    'Waveform entry {}'.format(waveform.RcvIFBandwidth, waveform.ADCSampleRate, index+1))
                this_cond = False
            if waveform.RcvDemodType is not None and waveform.RcvDemodType == 'CHIRP' \
                    and waveform.TxRFBandwidth is not None and waveform.ADCSampleRate is not None \
                    and (waveform.TxRFBandwidth > waveform.ADCSampleRate):
                self.log_validity_error(
                    'RcvDemodType is "CHIRP" and TxRFBandwidth ({}) is larger than ADCSampleRate ({}) '
                    'in Waveform entry {}'.format(waveform.TxRFBandwidth, waveform.ADCSampleRate, index+1))
                this_cond = False
            if waveform.RcvWindowLength is not None and waveform.TxPulseLength is not None and \
                    waveform.TxFMRate is not None and waveform.RcvFreqStart is not None and \
                    waveform.TxFreqStart is not None and waveform.TxRFBandwidth is not None:
                freq_tol = (waveform.RcvWindowLength - waveform.TxPulseLength)*waveform.TxFMRate
                if waveform.RcvFreqStart >= waveform.TxFreqStart + waveform.TxRFBandwidth + freq_tol:
                    self.log_validity_error(
                        'RcvFreqStart ({}), TxFreqStart ({}), and TxRfBandwidth ({}) parameters are inconsistent '
                        'in Waveform entry {}'.format(
                            waveform.RcvFreqStart, waveform.TxFreqStart, waveform.TxRFBandwidth, index + 1))
                    this_cond = False
                if waveform.RcvFreqStart <= waveform.TxFreqStart - freq_tol:
                    self.log_validity_error(
                        'RcvFreqStart ({}) and TxFreqStart ({}) parameters are inconsistent '
                        'in Waveform entry {}'.format(waveform.RcvFreqStart, waveform.TxFreqStart, index + 1))
                    this_cond = False

            return this_cond

        if self.Waveform is None or len(self.Waveform) < 1:
            return True

        cond = True
        # fetch min/max TxFreq observed
        wf_min_freq = None
        wf_max_freq = None
        for entry in self.Waveform:
            freq_start = entry.TxFreqStart
            freq_bw = entry.TxRFBandwidth
            if freq_start is not None:
                wf_min_freq = freq_start if wf_min_freq is None else \
                    min(wf_min_freq, freq_start)
                if entry.TxRFBandwidth is not None:
                    wf_max_freq = freq_start + freq_bw if wf_max_freq is None else \
                        max(wf_max_freq, freq_start + freq_bw)

        if wf_min_freq is not None and self.TxFrequency is not None and self.TxFrequency.Min is not None:
            if abs(self.TxFrequency.Min/wf_min_freq - 1) > 1e-3:
                self.log_validity_error(
                    'The stated TxFrequency.Min is {}, but the minimum populated in a '
                    'Waveform entry is {}'.format(self.TxFrequency.Min, wf_min_freq))
                cond = False
        if wf_max_freq is not None and self.TxFrequency is not None and self.TxFrequency.Max is not None:
            if abs(self.TxFrequency.Max/wf_max_freq - 1) > 1e-3:
                self.log_validity_error(
                    'The stated TxFrequency.Max is {}, but the maximum populated in a '
                    'Waveform entry is {}'.format(self.TxFrequency.Max, wf_max_freq))
                cond = False
        for t_index, t_waveform in enumerate(self.Waveform):
            cond &= validate_entry(t_index, t_waveform)
        return cond

    def _basic_validity_check(self):
        valid = super(RadarCollectionType, self)._basic_validity_check()
        valid &= self._check_frequency()
        valid &= self._check_tx_sequence()
        valid &= self._check_waveform_parameters()
        return valid

    def version_required(self):
        """
        What SICD version is required?

        Returns
        -------
        tuple
        """
        pass
