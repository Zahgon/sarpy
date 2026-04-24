"""
The PositionType definition.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


from typing import List, Union, Optional

import numpy

from sarpy.io.xml.base import Serializable, SerializableArray
from sarpy.io.xml.descriptors import SerializableDescriptor, SerializableArrayDescriptor

from .base import DEFAULT_STRICT
from .blocks import XYZType, XYZPolyType, XYZPolyAttributeType


class PositionType(Serializable):
    """The details for platform and ground reference positions as a function of time since collection start."""
    _fields = ('ARPPoly', 'GRPPoly', 'TxAPCPoly', 'RcvAPC')
    _required = ('ARPPoly',)
    _collections_tags = {'RcvAPC': {'array': True, 'child_tag': 'RcvAPCPoly'}}

    # descriptors
    ARPPoly = SerializableDescriptor(
        'ARPPoly', XYZPolyType, _required, strict=DEFAULT_STRICT,
        docstring='Aperture Reference Point (ARP) position polynomial in ECF as a function of elapsed '
                  'seconds since start of collection.')  # type: XYZPolyType
    GRPPoly = SerializableDescriptor(
        'GRPPoly', XYZPolyType, _required, strict=DEFAULT_STRICT,
        docstring='Ground Reference Point (GRP) position polynomial in ECF as a function of elapsed '
                  'seconds since start of collection.')  # type: XYZPolyType
    TxAPCPoly = SerializableDescriptor(
        'TxAPCPoly', XYZPolyType, _required, strict=DEFAULT_STRICT,
        docstring='Transmit Aperture Phase Center (APC) position polynomial in ECF as a function of '
                  'elapsed seconds since start of collection.')  # type: XYZPolyType
    RcvAPC = SerializableArrayDescriptor(
        'RcvAPC', XYZPolyAttributeType, _collections_tags, _required, strict=DEFAULT_STRICT,
        docstring='Receive Aperture Phase Center polynomials array. '
                  'Each polynomial has output in ECF, and represents a function of elapsed seconds since start of '
                  'collection.')  # type: Union[SerializableArray, List[XYZPolyAttributeType]]

    def __init__(
            self,
            ARPPoly: XYZPolyType = None,
            GRPPoly: Optional[XYZPolyType] = None,
            TxAPCPoly: Optional[XYZPolyType] = None,
            RcvAPC=None,
            **kwargs):
        """

        Parameters
        ----------
        ARPPoly : XYZPolyType
        GRPPoly : None|XYZPolyType
        TxAPCPoly : None|XYZPolyType
        RcvAPC : SerializableArray|List[XYZPolyAttributeType]|list|tuple
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.ARPPoly = ARPPoly
        self.GRPPoly = GRPPoly
        self.TxAPCPoly = TxAPCPoly
        self.RcvAPC = RcvAPC
        super(PositionType, self).__init__(**kwargs)

    def _derive_arp_poly(self, SCPCOA):
        """
        Expected to be called from SICD parent. Set the aperture position polynomial from position, time,
        acceleration at scptime, if necessary.

        .. Note::

            This assumes constant velocity and acceleration.

        Parameters
        ----------
        SCPCOA : sarpy.io.complex.sicd_elements.SCPCOA.SCPCOAType

        Returns
        -------
        None
        """
        pass

    def _basic_validity_check(self) -> bool:
        condition = super(PositionType, self)._basic_validity_check()
        if self.ARPPoly is not None and \
                (self.ARPPoly.X.order1 < 1 or self.ARPPoly.Y.order1 < 1 or self.ARPPoly.Z.order1 < 1):
            self.log_validity_error(
                'ARPPoly should be order at least 1 in each component. '
                'Got X.order1 = {}, Y.order1 = {}, and Z.order1 = {}'.format(self.ARPPoly.X.order1,
                                                                             self.ARPPoly.Y.order1,
                                                                             self.ARPPoly.Z.order1))
            condition = False
        return condition
