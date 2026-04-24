"""
Create kmz products based on SAR products.

For a basic help on the command-line, check

>>> python -m sarpy.utils.create_kmz --help

"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"

import argparse
import logging
import os
from deprecated import deprecated

import sarpy
from sarpy.io.complex.converter import open_complex
import sarpy.io.general.base
import sarpy.io.phase_history
import sarpy.io.received.converter
from sarpy.visualization.kmz_product_creation      import create_kmz_view
from sarpy.visualization.cphd_kmz_product_creation import cphd_create_kmz_view
from sarpy.visualization.crsd_kmz_product_creation import crsd_create_kmz_view


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Create KMZ product from a CRSD, CPHD or Complex Image.",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        'input_file', metavar='input_file',
        help='Path input data file, or directory for radarsat, RCM, or sentinel.\n'
             '* For radarsat or RCM, this can be the product.xml file, or parent directory\n'
             '  of product.xml or metadata/product.xml.\n'
             '* For sentinel, this can be the manifest.safe file, or parent directory of\n'
             '  manifest.safe.\n')
    parser.add_argument(
        'output_directory', metavar='output_directory',
        help='Path to the output directory where the product file(s) will be created.\n'
             'This directory MUST exist.\n'
             '* Depending on the input file, multiple product files may be produced.\n'
             '* The name for the output file(s) will be chosen based on CoreName and\n '
             '  transmit/collect polarization.\n')
    parser.add_argument(
        '-s', '--size', default=3072, type=int,
        help='(complex image only) Maximum # of thumbnail rows/columns, put -1 for full size')
    parser.add_argument(
        '--include-all', action='store_true', help='Include as much as possible in the KMZ')
    parser.add_argument(
        '-v', '--verbose', action='store_true', help='Verbose (level="INFO") logging?')

    args = parser.parse_args()

    level = 'INFO' if args.verbose else 'WARNING'
    logging.basicConfig(level=level)
    logger = logging.getLogger('sarpy')
    logger.setLevel(level)

    file_stem = 'View-' + os.path.splitext(os.path.split(args.input_file)[1])[0]

    def _cphd_kmz():
        pass

    @deprecated("sarpy's CRSD implementation is deprecated. Please use SARKit.")
    def _crsd_kmz():
        pass

    def _complex_image_kmz():
        pass

    for func in (_cphd_kmz, _crsd_kmz, _complex_image_kmz):
        try:
            func()
            break
        except sarpy.io.general.base.SarpyIOError:
            continue
    else:
        raise sarpy.io.general.base.SarpyIOError(f'A KMZ generator for {args.input_file} could not be found')
