#
# Copyright 2020-2021 Valkyrie Systems Corporation
#
# Licensed under MIT License.  See LICENSE.
#

__classification__ = "UNCLASSIFIED"
__author__ = "Nathan Bombaci, Valkyrie"


from typing import List
import numpy as np


def parse_text(elem):
    """
    Reverse of `xml.make_elem` by converting an element's text string to
    an int, float, bool, or str, as appropriate.

    Parameters
    ----------
    elem: lxml.etree.ElementTree.Element
        Element to convert to the most restrictive python type possible.

    Returns
    -------
    val: int|float|bool|str
        Converted value.
    """
    pass


def parse_bool_text(text):
    """
    Gets a boolean from a string.

    Parameters
    ----------
    text: str
        One of `'true', '1', 'false', '0'`.

    Returns
    -------
    val: bool
        Boolean value converted from `text`.

    Raises
    ------
    ValueError
        The text string is not either ``'true'`` or ``'false'``.
    """

    text = text.lower()
    if text in ['true', '1']:
        return True
    if text in ['false', '0']:
        return False
    raise ValueError("Cannot parse bool from {}".format(text))


def parse_bool(elem):
    """
    Gets a boolean from an element.

    Parameters
    ----------
    elem : lxml.etree.ElementTree.Element
        Element to convert.

    Returns
    -------
    val : bool
        Boolean value of the `elem`'s text.
    """

    return parse_bool_text(elem.text)


def parse_sequence(node, keys, conversion=parse_text):
    """
    Reverse of `sequence_node`.

    Parameters
    ----------
    node : lxml.etree.ElementTree.Element
        Element containing a sequence node.
    keys : List
        List of element names to parse.
    conversion : Callable
        Conversion function. (Default: `parse_text`)

    Returns
    ------
    List
        List of parsed values, one for each element of `keys`.
    """
    pass


def parse_xyz(node):
    """
    Parse a node with ``'X'``, ``'Y'``, and ``'Z'`` children

    Parameters
    ----------
    node : lxml.etree.ElementTree.Element
        Element containing an XYZ sequence node.

    Returns
    -------
    List
        List [X, Y, Z]. Parsed values.
    """
    pass


def parse_xy(node):
    """
    Parse a node with ``'X'`` and ``'Y'`` children.

    Parameters
    ----------
    node: lxml.etree.ElementTree.Element
        Element containing an XY sequence node.

    Returns
    -------
    List
        List [X, Y]. Parsed values.
    """
    pass


def parse_ll(node):
    """
    Parse a node with ``'Lat'`` and ``'Lon'`` children.

    Parameters
    ----------
    node: lxml.etree.ElementTree.Element
        Element containing a Lat/Lon sequence node.

    Returns
    -------
    List
        List [Lon, Lat]. Parsed values as radians.
    """
    pass


def parse_llh(node):
    """
    Parse a node with ``'Lat'``, ``'Lon'``, ``'HAE'`` children.
    Parameters
    ----------
    node: lxml.etree.ElementTree.Element
        Element containing a Lat/Lon/HAE sequence node.
    Returns
    -------
    List
        List [Lon, Lat, HAE]. Parsed Lon, Lat values as radians, HAE value as meters.
    """
    pass


def parse_poly2d(node):
    """
    Parse a node with ``'exponent1'`` and ``'exponent2'`` children.

    Args
    ----
    node: `lxml.etree.ElementTree.Element`
        Element containing a poly2d node.

    Returns
    -------
    result: list of list, shape=(:, :)
        A list of coefficient values.

    """
    pass
