"""
The RgAzCompType definition.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import logging
from typing import Union

import numpy
from numpy.linalg import norm

from sarpy.io.xml.base import Serializable
from sarpy.io.xml.descriptors import FloatDescriptor, SerializableDescriptor

from .base import DEFAULT_STRICT, FLOAT_FORMAT
from .blocks import Poly1DType


logger = logging.getLogger(__name__)


class RgAzCompType(Serializable):
    """
    Parameters included for a Range, Doppler image.
    """

    _fields = ('AzSF', 'KazPoly')
    _required = _fields
    _numeric_format = {'AzSF': FLOAT_FORMAT}
    # descriptors
    AzSF = FloatDescriptor(
        'AzSF', _required, strict=DEFAULT_STRICT,
        docstring='Scale factor that scales image coordinate az = ycol (meters) to a delta cosine of the '
                  'Doppler Cone Angle at COA, *(in 1/m)*')  # type: float
    KazPoly = SerializableDescriptor(
        'KazPoly', Poly1DType, _required, strict=DEFAULT_STRICT,
        docstring='Polynomial function that yields azimuth spatial frequency *(Kaz = Kcol)* as a function of '
                  'slow time ``(variable 1)``. That is '
                  r':math:`\text{Slow Time (sec)} \to \text{Azimuth spatial frequency (cycles/meter)}`. '
                  'Time relative to collection start.')  # type: Poly1DType

    def __init__(
            self,
            AzSF: float = None,
            KazPoly: Union[Poly1DType, numpy.ndarray, list, tuple] = None,
            **kwargs):
        """

        Parameters
        ----------
        AzSF : float
        KazPoly : Poly1DType|numpy.ndarray|list|tuple
        kwargs
        """

        if '_xml_ns' in kwargs:
            self._xml_ns = kwargs['_xml_ns']
        if '_xml_ns_key' in kwargs:
            self._xml_ns_key = kwargs['_xml_ns_key']
        self.AzSF = AzSF
        self.KazPoly = KazPoly
        super(RgAzCompType, self).__init__(**kwargs)

    def _derive_parameters(self, Grid, Timeline, SCPCOA):
        """
        Expected to be called by the SICD object.

        Parameters
        ----------
        Grid : sarpy.io.complex.sicd_elements.GridType
        Timeline : sarpy.io.complex.sicd_elements.TimelineType
        SCPCOA : sarpy.io.complex.sicd_elements.SCPCOA.SCPCOAType

        Returns
        -------
        None
        """
        pass
