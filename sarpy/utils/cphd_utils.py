"""
Extract information from the CPHD header for review.

From the command-line

>>> python -m sarpy.utils.cphd_utils <path to cphd file>

For a basic help on the command-line, check

>>> python -m sarpy.utils.cphd_utils --help

"""

from __future__ import print_function
import argparse
import sys
import functools
from xml.dom import minidom
from typing import Union, TextIO, BinaryIO
import os
from io import StringIO

from sarpy.io.phase_history.cphd import CPHDDetails

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"

# Custom print function
print_func = print


def _define_print_function(destination):
    """
    Define the print_func as necessary.

    Parameters
    ----------
    destination : TextIO
    """
    pass


def _print_header(input_file):
    # type: (Union[str, BinaryIO]) -> None

    pass


def _create_default_output_file(input_file):
    # type: (Union[str, BinaryIO]) -> str
    pass


def _print_structure(input_file):
    # type: (Union[str, BinaryIO]) -> None
    pass


def print_cphd_metadata(input_file, destination=sys.stdout):
    """
    Prints the full CPHD metadata (both header and CPHD structure) to the
    given destination.

    Parameters
    ----------
    input_file : str|BinaryIO
    destination : TextIO
    """
    pass


def print_cphd_header(input_file, destination=sys.stdout):
    """
    Prints the full CPHD header to the given destination.

    Parameters
    ----------
    input_file : str|BinaryIO
    destination : TextIO
    """
    pass


def print_cphd_xml(input_file, destination=sys.stdout):
    """
    Prints the full CPHD header to the given destination.

    Parameters
    ----------
    input_file : str|BinaryIO
    destination : TextIO
    """
    pass


def _dump_pattern(input_file, destination, call_method):
    # type: (Union[str, BinaryIO], str, Callable) -> Union[None, str]
    pass


def dump_cphd_metadata(input_file, destination):
    """
    Dump the CPHD metadata (both header and CPHD structure) to the given
    destination.

    Parameters
    ----------
    input_file : str|BinaryIO
        Path to or binary file-like object containing a CPHD file.
    destination : str
        'stdout', 'string', 'default' (will use `file_name+'.meta_dump.txt'`),
        or the path to an output file.

    Returns
    -------
    None|str
        There is only a return value if `destination=='string'`.
    """
    pass


def dump_cphd_header(input_file, destination):
    """
    Dump the CPHD header to the given destination.

    Parameters
    ----------
    input_file : str|BinaryIO
        Path to or binary file-like object containing a CPHD file.
    destination : str
        'stdout', 'string', 'default' (will use `file_name+'.meta_dump.txt'`),
        or the path to an output file.

    Returns
    -------
    None|str
        There is only a return value if `destination=='string'`.
    """
    pass


def dump_cphd_xml(input_file, destination):
    """
    Dump the CPHD structure to the given destination.

    Parameters
    ----------
    input_file : str|BinaryIO
        Path to or binary file-like object containing a CPHD file.
    destination : str
        'stdout', 'string', 'default' (will use `file_name+'.meta_dump.txt'`),
        or the path to an output file.

    Returns
    -------
    None|str
        There is only a return value if `destination=='string'`.
    """
    pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Create extract metadata information from a CPHD file.",
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        'input_file', metavar='input_file', help='Path input CPHD file.')
    parser.add_argument(
        '-o', '--output', default='default',
        help="'default', 'stdout', or the path for an output file.\n"
             "* If not provided (`default`), the output will be at '<input path>.txt' \n"
             "* 'stdout' will print the information to standard out.\n"
             "* Otherwise, this is expected to be the path to a file \n"
             "       and output will be written there.\n"
             "  NOTE: existing output files will be overwritten.")
    parser.add_argument(
        '-d', '--data', default='both', choices=['both', 'header', 'xml'],
        help='Which information should be printed?')
    args = parser.parse_args()

    if args.data == 'both':
        dump_cphd_metadata(args.input_file, args.output)
    elif args.data == 'header':
        dump_cphd_header(args.input_file, args.output)
    elif args.data == 'xml':
        dump_cphd_xml(args.input_file, args.output)
    else:
        raise ValueError('Got unhandled data option {}'.format(args.data))
