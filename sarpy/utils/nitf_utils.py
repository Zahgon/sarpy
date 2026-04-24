"""
A utility for dumping a NITF header to the console. Contributed by Austin Lan of L3/Harris.

To dump NITF header information to a text file from the command-line

>>> python -m sarpy.utils.nitf_utils <path to nitf file>

For a basic help on the command-line, check

>>> python -m sarpy.utils.nitf_utils --help

"""

__classification__ = "UNCLASSIFIED"
__author__ = "Austin Lan, L3/Harris"


import argparse
import functools
import sys
from xml.dom import minidom
import os
from typing import Union, BinaryIO, TextIO, List, Dict
from io import StringIO

from sarpy.io.general.nitf import NITFDetails
from sarpy.io.general.nitf_elements.base import NITFElement, TRE, TREList, UserHeaderType
from sarpy.io.general.nitf_elements.des import DataExtensionHeader, DataExtensionHeader0, \
    DESUserHeader
from sarpy.io.general.nitf_elements.graphics import GraphicsSegmentHeader
from sarpy.io.general.nitf_elements.image import ImageSegmentHeader, ImageSegmentHeader0, MaskSubheader
from sarpy.io.general.nitf_elements.label import LabelSegmentHeader
from sarpy.io.general.nitf_elements.nitf_head import NITFHeader, NITFHeader0
from sarpy.io.general.nitf_elements.res import ReservedExtensionHeader, ReservedExtensionHeader0, \
    RESUserHeader
from sarpy.io.general.nitf_elements.symbol import SymbolSegmentHeader
from sarpy.io.general.nitf_elements.text import TextSegmentHeader, TextSegmentHeader0
from sarpy.io.general.nitf_elements.tres.tre_elements import TREElement


# Custom print function
print_func = print


############
# helper methods

def _filter_files(input_path):
    """
    Determine if a given input path corresponds to a NITF 2.1 or 2.0 file.

    Parameters
    ----------
    input_path : str

    Returns
    -------
    bool
    """
    pass


def _create_default_output_file(input_file, output_directory=None):
    pass


def _decode_effort(value):
    # type: (bytes) -> Union[bytes, str]

    # noinspection PyBroadException
    pass


############
# printing methods

def _print_element_field(elem, field, prefix=''):
    # type: (Union[None, NITFElement], Union[None, str], str) -> None
    pass


def _print_element(elem, prefix=''):
    # type: (Union[None, NITFElement], str) -> None
    pass


def _print_element_list(elem_list, prefix=''):
    # type: (Union[None, List[NITFElement]], str) -> None
    pass


def _print_tre_element(field, value, prefix=''):
    # type: (Union[None, str], Union[str, int, bytes], str) -> None
    pass


def _print_tre_list(elem_list, prefix=''):
    # type: (Union[None, List, TREList], str) -> None

    pass


def _print_tre_dict(elem_dict, prefix=''):
    # type: (Union[None, Dict], str) -> None
    pass


def _print_tres(tres):
    # type: (Union[TREList, List[TRE]]) -> None
    pass


def _print_file_header(hdr):
    # type: (Union[NITFHeader, NITFHeader0]) -> None

    # noinspection PyProtectedMember
    pass


def _print_mask_header(hdr):
    # type: (Union[None, MaskSubheader]) -> None
    pass


def _print_image_header(hdr):
    # type: (Union[ImageSegmentHeader, ImageSegmentHeader0]) -> None

    # noinspection PyProtectedMember
    pass


def _print_basic_header(hdr, prefix):
    # noinspection PyProtectedMember
    pass


def _print_graphics_header(hdr):
    # type: (GraphicsSegmentHeader) -> None
    pass


def _print_symbol_header(hdr):
    # type: (SymbolSegmentHeader) -> None
    pass


def _print_label_header(hdr):
    # type: (LabelSegmentHeader) -> None
    pass


def _print_text_header(hdr):
    # type: (Union[TextSegmentHeader, TextSegmentHeader0]) -> None
    pass


def _print_extension_header(hdr, prefix):
    # noinspection PyProtectedMember
    pass


def _print_des_header(hdr):
    # type: (Union[DataExtensionHeader, DataExtensionHeader0]) -> None
    pass


def _print_res_header(hdr):
    # type: (Union[ReservedExtensionHeader, ReservedExtensionHeader0]) -> None
    pass


def print_nitf(file_name, dest=sys.stdout):
    """
    Worker function to dump the NITF header and various subheader details to the
    provided destination.

    Parameters
    ----------
    file_name : str|BinaryIO
    dest : TextIO
    """
    pass


##########
# method for dumping file using the print method(s)

def dump_nitf_file(file_name, dest, over_write=True):
    """
    Utility to dump the NITF header and various subheader details to a configurable
    destination.

    Parameters
    ----------
    file_name : str|BinaryIO
        The path to or file-like object containing a NITF 2.1 or 2.0 file.
    dest : str
        'stdout', 'string', 'default' (will use `file_name+'.header_dump.txt'`),
        or the path to an output file.
    over_write : bool
        If `True`, then overwrite the destination file, otherwise append to the
        file.

    Returns
    -------
    None|str
        There is only a return value if `dest=='string'`.
    """
    pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Utility to dump NITF 2.1 or 2.0 headers.',
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        'input_file',
        help='The path to a nitf file, or directory to search for NITF files.')
    parser.add_argument(
        '-o', '--output', default='default',
        help="'default', 'stdout', or the path for an output file.\n"
             "* 'default', the output will be at '<input path>.header_dump.txt' \n"
             "   This will be overwritten, if it exists.\n"
             "* 'stdout' will print the information to standard out.\n"
             "* Otherwise, "
             "     if `input_file` is a directory, this is expected to be the path to\n"
             "       an output directory for the output following the default naming scheme.\n"
             "*    if `input_file` a file path, this is expected to be the path to a file \n"
             "       and output will be written there.\n"
             "  In either case, existing output files will be overwritten.")
    args = parser.parse_args()

    if os.path.isdir(args.input_file):
        entries = [os.path.join(args.input_file, part) for part in os.listdir(args.input_file)]
        for file_number, entry in enumerate(filter(_filter_files, entries)):
            if args.output == 'stdout':
                output = args.output
            elif args.output == 'default':
                output = _create_default_output_file(entry, output_directory=None)
            else:
                if not os.path.isdir(args.output):
                    raise IOError(
                        'Provided input is a directory, so provided output must '
                        'be a directory, `stdout`, or `default`.')
                output = _create_default_output_file(entry, output_directory=args.output)
            dump_nitf_file(entry, output)
    else:
        dump_nitf_file(args.input_file, args.output)
