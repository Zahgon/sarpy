#
# Copyright 2020-2021 Valkyrie Systems Corporation
#
# Licensed under MIT License.  See LICENSE.
#

__classification__ = "UNCLASSIFIED"
__author__ = "Nathan Bombaci, Valkyrie"


import logging
import argparse
import collections
import copy
import functools
import itertools
import numbers
import os
import re
from typing import List

import numpy as np
import numpy.polynomial.polynomial as npp
import scipy.constants

from sarpy.geometry import geocoords

import sarpy.consistency.consistency as con
import sarpy.consistency.parsers as parsers
import sarpy.io.phase_history.cphd1_elements.CPHD
import sarpy.io.phase_history.cphd1_elements.utils as cphd1_utils
from sarpy.io.phase_history import cphd_schema

logger = logging.getLogger(__name__)

try:
    import pytest
except ImportError:
    pytest = None
    logger.critical(
        'Functionality for CPHD consistency testing cannot proceed WITHOUT the pytest '
        'package')

try:
    from lxml import etree
except ImportError:
    etree = None
    pytest = None
    logger.critical(
        'Functionality for CPHD consistency testing cannot proceed WITHOUT the lxml '
        'package')

try:
    import shapely.geometry as shg
    have_shapely = True
except ImportError:
    have_shapely = False

try:
    import networkx as nx
    have_networkx = True
except ImportError:
    have_networkx = False


INVALID_CHAR_REGEX = re.compile(r'\W')


def strip_namespace(root):
    """
    Returns a copy of the input etree with namespaces removed.

    Parameters
    ----------
    root : etree.ElementTree
        The element tree

    Returns
    -------
    etree.ElementTree
        The element tree
    """

    root_copy = copy.deepcopy(root)
    # strip namespace from each element
    for elem in root_copy.iter():
        try:
            elem.tag = elem.tag.split('}')[-1]
        except (AttributeError, TypeError):
            pass
    # remove default namespace
    nsmap = root_copy.nsmap
    nsmap.pop(None, None)
    new_root = etree.Element(root_copy.tag, nsmap)
    new_root[:] = root_copy[:]

    return new_root


def parse_pvp_elem(elem):
    """
    Reverse of `pvp_elem`.

    Parameters
    ----------
    elem : etree.ElementTree.Element
        Node for the specified PVP parameter.

    Returns
    -------
    Tuple
        Tuple (parameter_name, {``'offset'``:offset, ``'size'``:size, ``'dtype'``:dtype}). PVP element information.
    """

    if elem.tag == "AddedPVP":
        name = elem.find('Name').text
    else:
        name = elem.tag

    offset = int(elem.find('Offset').text)
    size = int(elem.find('Size').text)

    dtype = cphd1_utils.binary_format_string_to_dtype(elem.find('Format').text)

    return name, {"offset": offset,
                  "size": size,
                  "dtype": dtype}


def read_header(file_handle):
    """Reads a CPHD header from a file.

    Parameters
    ----------
    file_handle
    Readable File object, i.e., ``file_handle = open(filename, 'rb')``.

        Handle of the CPHD file that is to be read

    Returns
    -------
    Dict
        Dictionary containing CPHD header values.
    """

    file_handle.seek(0, 0)
    version = file_handle.readline().decode()
    assert version.startswith('CPHD/1.0') or version.startswith('CPHD/1.1')

    header = sarpy.io.phase_history.cphd1_elements.CPHD.CPHDHeader.from_file_object(file_handle)
    return {k: getattr(header, k) for k in header._fields if getattr(header, k) is not None}


def per_channel(method):
    """
    Decorator to mark check methods as being applicable to each CPHD channel

    Parameters
    ----------
    method : Callable
        Method to mark

    Returns
    -------
    Callable
        Marked input `method`
    """
    pass


def get_by_id(xml, path, identifier):
    """
    Matches the first element that has a child named Identifier whose text is `identifier`.

    Parameters
    ----------
    xml : etree.Element
        Root node of XPath expression
    path : str
        XPath expression relative to `xml`
    identifier : str
        Value of child Identifier node

    Returns
    -------
    None|etree.Element
        node found by path with an Identifier node with value of `identifier` or None if a match is not found
    """

    return xml.find(f'{path}[Identifier="{identifier}"]')


class CphdConsistency(con.ConsistencyChecker):
    """
    Check CPHD file structure and metadata for internal consistency

    Parameters
    ----------
    cphdroot : etree.Element
        root CPHD XML node
    pvps : None|Dict[str, np.ndarray]
        numpy structured array of PVPs
    header : Dict
        CPHD header key value pairs
    filename : None|str
        Path to CPHD file (or None if not available)
    schema : str
        Path to CPHD XML Schema. If None, tries to find a version-specific schema
    check_signal_data: bool
        Should the signal array be checked for invalid values
    """

    def __init__(self, cphdroot, pvps, header, filename, schema=None, check_signal_data=False):
        super(CphdConsistency, self).__init__()
        self.xml_with_ns = etree.fromstring(etree.tostring(cphdroot))  # handle element or tree -> element
        self.xml = strip_namespace(self.xml_with_ns)
        self.pvps = pvps
        self.filename = filename
        self.header = header
        self.version = self._version_lookup()
        if schema is None and self.version is not None:
            urn = {v['release']: k for k, v in cphd_schema.urn_mapping.items()}[self.version]
            self.schema = cphd_schema.get_schema_path(urn)
        else:
            self.schema = schema
        self.check_signal_data = check_signal_data
        channel_ids = [x.text for x in self.xml.findall('./Data/Channel/Identifier')]

        # process decorated methods to generate per-channel tests
        # reverse the enumerated list so that we don't disturb indices on later iterations as we insert into the list
        for index, func in reversed(list(enumerate(self.funcs))):
            if getattr(func, 'per_channel', False):
                subfuncs = []
                for channel_id in channel_ids:
                    channel_node = self.xml.xpath('./Channel/Parameters/Identifier[text()="{}"]/..'.format(
                        channel_id))[0]
                    subfunc = functools.partial(func, channel_id, channel_node)
                    this_doc = func.__doc__.strip()
                    if this_doc.endswith('.'):
                        this_doc = this_doc[:-1]
                    subfunc.__doc__ = f"{this_doc} for channel {channel_id}."
                    modified_channel_id = re.sub(INVALID_CHAR_REGEX, '_', channel_id)
                    subfunc.__name__ = "{name}_{chanid}".format(name=func.__name__, chanid=modified_channel_id)
                    subfuncs.append(subfunc)
                self.funcs[index:index+1] = subfuncs

    @classmethod
    def from_file(cls, filename, schema=None, check_signal_data=False):
        """
        Create a CphdConsistency object from a CPHD file.

        Parameters
        ----------
        filename : str
            Path to CPHD file
        schema : str
            Path to CPHD XML Schema. If None, tries to find a version-specific schema
        check_signal_data : bool
            Should the signal array be checked for invalid values

        Returns
        -------
        CphdConsistency
            new object
        """
        with open(filename, 'rb') as infile:
            try:
                header = None
                cphdroot = etree.parse(infile)
                pvp_block = None
            except etree.XMLSyntaxError:
                header = read_header(infile)
                infile.seek(header['XML_BLOCK_BYTE_OFFSET'], 0)
                xml_block = infile.read(header['XML_BLOCK_SIZE'])
                cphdroot = etree.fromstring(xml_block)
                infile.seek(header['PVP_BLOCK_BYTE_OFFSET'], 0)
                pvp_block = infile.read(header['PVP_BLOCK_SIZE'])

        cphdroot_no_ns = strip_namespace(etree.fromstring(etree.tostring(cphdroot)))
        fields = [parse_pvp_elem(field) for field in list(cphdroot_no_ns.findall('./PVP//Offset/..'))]
        dtype = np.dtype({'names': [name for name, _ in fields],
                          'formats': [info['dtype'] for _, info in fields],
                          'offsets': [info['offset']*8 for _, info in fields]}).newbyteorder('B')

        if pvp_block is None:
            pvps = None
        else:
            pvps = {}
            for channel_node in cphdroot_no_ns.findall('./Data/Channel'):
                channel_id = channel_node.findtext('./Identifier')
                channel_pvps = np.frombuffer(pvp_block, dtype=dtype,
                                             count=int(channel_node.findtext('./NumVectors')),
                                             offset=int(channel_node.findtext('./PVPArrayByteOffset')))
                pvps[channel_id] = channel_pvps
        return cls(cphdroot, pvps, header, filename, schema=schema, check_signal_data=check_signal_data)

    def _version_lookup(self):
        """
        Returns the version string associated with the XML instance or None if a match is not found.
        """
        pass

    def _get_channel_pvps(self, channel_id):
        """
        Returns the PVPs associated with the channel keyed by `channel_id` or raises an AssertionError.
        """
        pass

    def check_file_type_header(self):
        """
        Version in File Type Header matches the version in the XML.
        """
        pass

    def check_header_keys(self):
        """
        Asserts that the required keys are in the header.
        """
        pass

    def check_classification_and_release_info(self):
        """
        Asserts that the Classification and ReleaseInfo fields are the same in header and the xml.
        """
        pass

    def check_against_schema(self):
        """
        The XML matches the schema.
        """
        pass

    @per_channel
    def check_channel_dwell_exist(self, channel_id, channel_node):
        """
        The referenced Dwell and COD nodes exist.
        """
        pass

    @per_channel
    def check_channel_dwell_polys(self, channel_id, channel_node):
        """
        /Dwell/CODTime/CODTimePoly and /Dwell/DwellTime/DwellTimePoly are consistent with other metadata.
        """
        pass

    def check_antenna(self):
        """
        Check that antenna node is consistent.
        """
        pass

    @per_channel
    def check_channel_antenna_exist(self, channel_id, channel_node):
        """
        The antenna patterns and phase centers exist if declared.
        """
        pass

    @per_channel
    def check_channel_txrcv_exist(self, channel_id, channel_node):
        """
        The declared TxRcv nodes exist.
        """
        pass

    @per_channel
    def check_time_monotonic(self, channel_id, channel_node):
        """
        PVP times increase monotonically.
        """
        pass

    @per_channel
    def check_rcv_after_tx(self, channel_id, channel_node):
        """
        RcvTime is after TxTime.
        """
        pass

    @per_channel
    def check_rcv_finite(self, channel_id, channel_node):
        """
        RcvTime and Pos are finite.
        """
        pass

    @per_channel
    def check_channel_fxfixed(self, channel_id, channel_node):
        """
        PVP agrees with FXFixed.
        """
        pass

    @per_channel
    def check_channel_toafixed(self, channel_id, channel_node):
        """
        PVP agrees with TOAFixed.
        """
        pass

    @per_channel
    def check_channel_srpfixed(self, channel_id, channel_node):
        """
        PVP agrees with SRPFixed.
        """
        pass

    def check_file_fxfixed(self):
        """
        The FXFixedCPHD element matches the rest of the file.
        """
        pass

    def check_file_toafixed(self):
        """
        The TOAFixedCPHD element matches the rest of the file.
        """
        pass

    def check_file_srpfixed(self):
        """
        The SRPFixedCPHD element matches the rest of the file.
        """
        pass

    @per_channel
    def check_channel_signalnormal(self, channel_id, channel_node):
        """
        PVP agrees with SignalNormal.
        """
        pass

    @per_channel
    def check_channel_fxc(self, channel_id, channel_node):
        """
        PVP agrees with FxC.
        """
        pass

    @per_channel
    def check_channel_fxbw(self, channel_id, channel_node):
        """
        PVP agrees with FxBW.
        """
        pass

    @per_channel
    def check_channel_fxbwnoise(self, channel_id, channel_node):
        """
        PVP agrees with FxBWNoise.
        """
        pass

    @per_channel
    def check_channel_toasaved(self, channel_id, channel_node):
        """
        PVP agrees with TOASaved.
        """
        pass

    @per_channel
    def check_channel_toaextsaved(self, channel_id, channel_node):
        """
        PVP agrees with TOAExtSaved.
        """
        pass

    @per_channel
    def check_channel_fx_osr(self, channel_id, channel_node):
        """
        FX domain vectors are sufficiently sampled
        """
        pass

    @per_channel
    def check_channel_toa_osr(self, channel_id, channel_node):
        """
        TOA domain vectors are sufficiently sampled
        """
        pass

    @per_channel
    def check_channel_global_txtime(self, channel_id, channel_node):
        """
        PVP within global TxTime1 and TxTime2.
        """
        pass

    @per_channel
    def check_channel_global_fxminmax(self, channel_id, channel_node):
        """
        PVP within global FxMin and FxMax.
        """
        pass

    @per_channel
    def check_channel_global_toaswath(self, channel_id, channel_node):
        """
        PVP within global TOASwath.
        """
        pass

    @per_channel
    def check_channel_afdop(self, channel_id, channel_node):
        """
        aFDOP PVP is consistent with other PVPs.
        """
        pass

    @per_channel
    def check_channel_afrr1_afrr2_relative(self, channel_id, channel_node):
        """
        aFRR1 & aFRR2 PVPs are related by fx_C.
        """
        pass

    def _get_channel_tx_lfmrates(self, channel_node):
        pass

    @per_channel
    def check_channel_afrr1(self, channel_id, channel_node):
        """
        aFRR1 is consistent with /TxRcv/TxWFParameters/LFMRate.
        """
        pass

    @per_channel
    def check_channel_afrr2(self, channel_id, channel_node):
        """
        aFRR2 is consistent with /TxRcv/TxWFParameters/LFMRate(s).
        """
        pass

    @per_channel
    def check_channel_imagearea_polygon(self, channel_id, channel_node):
        """
        Image area polygon is simple and consistent with X1Y1 and X2Y2.
        """
        pass

    @per_channel
    def check_channel_identifier_uniqueness(self, channel_id, channel_node):
        """
        Identifier nodes within /Channel/Parameters are unique.
        """
        pass

    @per_channel
    def check_channel_rcv_sample_rate(self, channel_id, channel_node):
        """
        /TxRcv/RcvParameters/SampleRate sufficient to support saved TOA swath.
        """
        pass

    def check_global_imagearea_polygon(self):
        """
        Scene Image area polygon is simple and consistent with X1Y1 and X2Y2.
        """
        pass

    def get_polygon(self, polygon_node, check=False, reverse=False, parser=parsers.parse_xy):
        pass

    def check_geoinfo_polygons(self):
        """
        GeoInfo polygons are simple polygons in clockwise order.
        """
        pass

    def check_image_area_corner_points(self):
        """
        The corner points represent a simple quadrilateral in clockwise order.
        """
        pass

    def check_extended_imagearea_polygon(self):
        """
        Scene extended area polygon is simple and consistent with X1Y1 and X2Y2.
        """
        pass

    @per_channel
    def check_channel_imagearea_x1y1(self, channel_id, channel_node):
        """
        Image area X1Y1 and X2Y2 work with global X1Y1 and X2Y2.
        """
        pass

    def check_imagearea_x1y1_x2y2(self):
        """
        SceneCoordinates/ImageArea is self-consistent.
        """
        pass

    def check_extended_imagearea_x1y1_x2y2(self):
        """
        Extended image area contains the image area.
        """
        pass

    @per_channel
    def check_channel_signal_data(self, channel_id, channel_node):
        """
        Sample data is all finite.
        """
        pass

    @per_channel
    def check_channel_normal_signal_pvp(self, channel_id, channel_node):
        """SIGNAL PVP = 1 for at least half of the vectors."""
        pass

    def check_image_grid_exists(self):
        """
        Verify that the ImageGrid is defined
        """
        pass

    def check_pad_header_xml(self):
        """
        The pad between the header and XML is 0.
        """
        pass

    def check_pad_after_xml(self):
        """
        The pad after XML is 0.
        """
        pass

    def check_pad_after_support(self):
        """
        The pad after support arrays is 0.
        """
        pass

    def check_pad_after_pvp(self):
        """
        The pad after PVPs is 0.
        """
        pass

    def check_signal_at_end_of_file(self):
        """
        Signal is at the end of the file.
        """
        pass

    def check_scene_plane_axis_vectors(self):
        """
        Scene plane axis vectors are orthonormal.
        """
        pass

    def check_global_txtime_limits(self):
        """
        The Global TxTime1 and TxTime2 match the PVPs.
        """
        pass

    def check_global_fx_band(self):
        """
        The Global FXBand matches the PVPs.
        """
        pass

    def check_global_toaswath(self):
        """
        The Global TOASwath matches the PVPs.
        """
        pass

    def _check_ids_in_channel_for_optional_branch(self, branch_name):
        pass

    def check_antenna_ids_in_channel(self):
        """
        If the Antenna branch exists, then Antenna is also present in /Channel/Parameters
        """
        pass

    def check_txrcv_ids_in_channel(self):
        """
        If the TxRcv branch exists, then TxRcv is also present in /Channel/Parameters
        """
        pass

    def _check_refgeom_parameters(self, xml_node, expected_parameters):
        pass

    def check_refgeom_root(self):
        """
        The ReferenceGeometry branch root parameters match the PVPs/defined calculations
        """
        pass

    def check_refgeom_monostatic(self):
        """
        The ReferenceGeometry branch Monostatic parameters are present and match the PVPs/defined calculations
        """
        pass

    def check_refgeom_bistatic(self):
        """
        The ReferenceGeometry branch Bistatic parameters are present and match the PVPs/defined calculations
        """
        pass

    def check_unconnected_ids(self):
        """
        Check that all identifiers are connected back to the Data branch.
        """
        pass

    def check_identifier_uniqueness(self):
        """
        Identifier nodes are unique.
        """
        pass

    def check_polynomials(self):
        """
        Polynomial types are correctly specified.
        """
        pass

    def check_optional_pvps_fx(self):
        """
        FXN1 & FXN2 PVPs are included appropriately.
        """
        pass

    def check_optional_pvps_toa(self):
        """
        TOAE1 & TOAE2 PVPs are included appropriately.
        """
        pass


def _get_repeated_elements(items):
    pass


def unit(vec, axis=-1):
    pass


def calc_refgeom_parameters(xml, pvps):
    """
    Calculate expected reference geometry parameters given CPHD XML and PVPs (CPHD1.0.1, Sec 6.5)
    """
    pass


def make_id_graph(xml):
    """
    Make an undirected graph with CPHD identifiers as nodes and edges from correspondence and hierarchy.

    Nodes are named as {xml_path}<{id}, e.g. /Data/Channel/Identifier<Ch1
    There is a single "Data" node formed from the Data branch root that signifies data that can be read from the file

    Args
    ----
    xml: `lxml.etree.ElementTree.Element`
        Root CPHD XML node

    Returns
    -------
    id_graph: `networkx.Graph`
        Undirected graph

            * nodes: Data node, CPHD identifiers
            * edges: Parent identifiers to child identifiers; corresponding identifiers across XML branches

    """
    pass


def main(args=None):
    """
    CphdConsistency CLI tool. Print results to stdout.

    Parameters
    ----------
    args: None|List[str]
        List of CLI argument strings.  If None use sys.argv
    """
    parser = argparse.ArgumentParser(description="Analyze a CPHD and display inconsistencies")
    parser.add_argument('cphd_or_xml')
    parser.add_argument('-v', '--verbose', default=0,
                        action='count', help="Increase verbosity (can be specified more than once >4 doesn't help)")
    parser.add_argument('--schema', help="Use a supplied schema file (attempts version-specific schema if omitted)")
    parser.add_argument('--noschema', action='append_const', const='check_against_schema', dest='ignore',
                        help="Disable schema checks")
    parser.add_argument('--signal-data', action='store_true', help="Check the signal data for NaN and +/- Inf")
    parser.add_argument('--ignore', action='append', metavar='PATTERN',
                        help=("Skip any check matching PATTERN at the beginning of its name. Can be specified more than"
                              " once."))
    config = parser.parse_args(args)

    # Some questionable abuse of the pytest internals
    import ast
    import _pytest.assertion.rewrite
    base, ext = os.path.splitext(__file__)  # python2 can return the '*.pyc' file
    with open(base + '.py', 'r') as fd:
        source = fd.read()
    tree = ast.parse(source)
    try:
        _pytest.assertion.rewrite.rewrite_asserts(tree)
    except TypeError as e:
        _pytest.assertion.rewrite.rewrite_asserts(tree, source)

    co = compile(tree, __file__, 'exec', dont_inherit=True)
    ns = {}
    exec(co, ns)

    cphd_con = ns['CphdConsistency'].from_file(config.cphd_or_xml, config.schema, config.signal_data)
    cphd_con.check(ignore_patterns=config.ignore)
    failures = cphd_con.failures()
    cphd_con.print_result(fail_detail=config.verbose >= 1,
                          include_passed_asserts=config.verbose >= 2,
                          include_passed_checks=config.verbose >= 3,
                          skip_detail=config.verbose >= 4)

    return bool(failures)


if __name__ == "__main__":     # pragma: no cover
    import sys
    sys.exit(int(main()))
