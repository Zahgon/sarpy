"""
Functionality for reading a GFF file into a SICD model.

Note: This has been tested on files of version 1.8 and 2.5, but hopefully works for others.
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"

import logging
import os
import struct
from typing import Tuple, Union, BinaryIO, Optional
from datetime import datetime
from tempfile import mkstemp
import zlib

import numpy
from scipy.constants import speed_of_light

from sarpy.io.general.base import SarpyIOError
from sarpy.io.general.format_function import ComplexFormatFunction
from sarpy.io.general.data_segment import DataSegment, NumpyMemmapSegment
from sarpy.io.general.utils import is_file_like, MemMap
from sarpy.geometry.geocoords import geodetic_to_ecf, wgs_84_norm, ned_to_ecf

from sarpy.io.complex.base import SICDTypeReader
from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.sicd_elements.CollectionInfo import CollectionInfoType, \
    RadarModeType
from sarpy.io.complex.sicd_elements.ImageCreation import ImageCreationType
from sarpy.io.complex.sicd_elements.ImageData import ImageDataType
from sarpy.io.complex.sicd_elements.GeoData import GeoDataType, SCPType
from sarpy.io.complex.sicd_elements.Grid import GridType, DirParamType, \
    WgtTypeType
from sarpy.io.complex.sicd_elements.SCPCOA import SCPCOAType
from sarpy.io.complex.sicd_elements.Timeline import TimelineType, IPPSetType
from sarpy.io.complex.sicd_elements.RadarCollection import RadarCollectionType, \
    WaveformParametersType, ChanParametersType
from sarpy.io.complex.sicd_elements.ImageFormation import ImageFormationType, \
    RcvChanProcType
from sarpy.io.complex.sicd_elements.Radiometric import RadiometricType, \
    NoiseLevelType_

try:
    import PIL
except ImportError:
    PIL = None

logger = logging.getLogger(__name__)

_requires_array_text = 'Requires numpy.ndarray, got `{}`'
_requires_3darray_text = 'Requires a three-dimensional numpy.ndarray\n\t' \
                         '(with band in the last dimension), got shape {}'


####################
# utility functions

def _get_string(bytes_in):
    pass


def _rescale_float(int_in, scale):
    pass


####################
# version 1 specific header parsing

class _GFFHeader_1_6(object):
    """
    Interpreter for the GFF version 1.6 header
    """

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        self.file_object = fi
        self.estr = estr

        self.version = '1.6'
        fi.seek(12, os.SEEK_SET)
        # starting at line 3 of def
        self.header_length = struct.unpack(estr+'I', fi.read(4))[0]
        if self.header_length < 952:
            raise ValueError(
                'The provided header is apparently too short to be a version 1.6 GFF header')

        fi.read(2)  # redundant
        self.creator = _get_string(fi.read(24))
        self.date_time = struct.unpack(estr+'6H', fi.read(6*2))  # year,month, day, hour, minute, second
        fi.read(2)  # endian, already parsed
        self.bytes_per_pixel, self.frame_count, self.image_type, \
            self.row_major, self.range_count, self.azimuth_count = \
            struct.unpack(estr+'6I', fi.read(6*4))
        self.scale_exponent, self.scale_mantissa, self.offset_exponent, self.offset_mantissa = \
            struct.unpack(estr+'4i', fi.read(4*4))
        # at line 17 of def

        fi.read(2)  # redundant
        self.comment = _get_string(fi.read(166))
        self.image_plane = struct.unpack(estr+'I', fi.read(4))[0]
        range_pixel_size, azimuth_pixel_size, azimuth_overlap = struct.unpack(estr+'3I', fi.read(3*4))
        self.range_pixel_size = _rescale_float(range_pixel_size, 1 << 16)
        self.azimuth_pixel_size = _rescale_float(azimuth_pixel_size, 1 << 16)
        self.azimuth_overlap = _rescale_float(azimuth_overlap, 1 << 16)

        srp_lat, srp_lon, srp_alt, rfoa, x_to_srp = struct.unpack(estr+'5i', fi.read(5*4))
        self.srp_lat = _rescale_float(srp_lat, 1 << 23)
        self.srp_lon = _rescale_float(srp_lon, 1 << 23)
        self.srp_alt = _rescale_float(srp_alt, 1 << 16)
        self.rfoa = _rescale_float(rfoa, 1 << 23)
        self.x_to_srp = _rescale_float(x_to_srp, 1 << 16)

        fi.read(2)
        self.phase_name = _get_string(fi.read(128))
        fi.read(2)
        self.image_name = _get_string(fi.read(128))
        # at line 32 of def

        self.look_count, self.param_ref_ap, self.param_ref_pos = \
            struct.unpack(estr+'3I', fi.read(3*4))

        graze_angle, squint, gta, range_beam_ctr, flight_time = \
            struct.unpack(estr + 'I2i2I', fi.read(5*4))
        self.graze_angle = _rescale_float(graze_angle, 1 << 23)
        self.squint = _rescale_float(squint, 1 << 23)
        self.gta = _rescale_float(gta, 1 << 23)
        self.range_beam_ctr = _rescale_float(range_beam_ctr, 1 << 8)
        self.flight_time = _rescale_float(flight_time, 1000)

        self.range_chirp_rate, x_to_start, self.mo_comp_mode, v_x = \
            struct.unpack(estr+'fi2I', fi.read(4*4))
        self.x_to_start = _rescale_float(x_to_start, 1 << 16)
        self.v_x = _rescale_float(v_x, 1 << 16)
        # at line 44 of def

        apc_lat, apc_lon, apc_alt = struct.unpack(estr+'3i', fi.read(3*4))
        self.apc_lat = _rescale_float(apc_lat, 1 << 23)
        self.apc_lon = _rescale_float(apc_lon, 1 << 23)
        self.apc_alt = _rescale_float(apc_alt, 1 << 16)

        cal_parm, self.logical_block_address = struct.unpack(estr+'2I', fi.read(2*4))
        self.cal_parm = _rescale_float(cal_parm, 1 << 24)
        az_resolution, range_resolution = struct.unpack(estr+'2I', fi.read(2*4))
        self.az_resolution = _rescale_float(az_resolution, 1 << 16)
        self.range_resolution = _rescale_float(range_resolution, 1 << 16)

        des_sigma_n, des_graze, des_squint, des_range, scene_track_angle = \
            struct.unpack(estr+'iIiIi', fi.read(5*4))
        self.des_sigma_n = _rescale_float(des_sigma_n, 1 << 23)
        self.des_graze = _rescale_float(des_graze, 1 << 23)
        self.des_squint = _rescale_float(des_squint, 1 << 23)
        self.des_range = _rescale_float(des_range, 1 << 8)
        self.scene_track_angle = _rescale_float(scene_track_angle, 1 << 23)
        # at line 56 of def

        self.user_param = fi.read(48)  # leave uninterpreted

        self.coarse_snr, self.coarse_azimuth_sub, self.coarse_range_sub, \
            self.max_azimuth_shift, self.max_range_shift, \
            self.coarse_delta_azimuth, self.coarse_delta_range = \
            struct.unpack(estr+'7i', fi.read(7*4))

        self.tot_procs, self.tpt_box_cmode, self.snr_thresh, self.range_size, \
            self.map_box_size, self.box_size, self.box_spc, self.tot_tpts, \
            self.good_tpts, self.range_seed, self.range_shift, self.azimuth_shift = \
            struct.unpack(estr+'12i', fi.read(12*4))
        # at line 76 of def

        self.sum_x_ramp, self.sum_y_ramp = struct.unpack(estr+'2i', fi.read(2*4))
        self.cy9k_tape_block, self.nominal_center_frequency = struct.unpack(estr+'If', fi.read(2*4))
        self.image_flags, self.line_number, self.patch_number = struct.unpack(estr+'3I', fi.read(3*4))
        self.lambda0, self.srange_pix_space = struct.unpack(estr+'2f', fi.read(2*4))
        self.dopp_pix_space, self.dopp_offset, self.dopp_range_scale, self.mux_time_delay = \
            struct.unpack(estr+'4f', fi.read(4*4))
        # at line 89 of def

        self.apc_ecef = struct.unpack(estr+'3d', fi.read(3*8))
        self.vel_ecef = struct.unpack(estr+'3f', fi.read(3*4))
        self.phase_cal = struct.unpack(estr+'f', fi.read(4))[0]
        self.srp_ecef = struct.unpack(estr+'3d', fi.read(3*8))
        self.res5 = fi.read(64)  # leave uninterpreted


class _Radar_1_8(object):
    """
    The radar details, for version 1.8
    """

    def __init__(self, the_bytes, estr):
        """

        Parameters
        ----------
        the_bytes : bytes
            This will be required to have length 76
        estr : str
            The endianness format string
        """

        if not (isinstance(the_bytes, bytes) and len(the_bytes) == 76):
            raise ValueError('Incorrect length input')

        self.platform = _get_string(the_bytes[:24])
        self.proc_id = _get_string(the_bytes[24:36])
        self.radar_model = _get_string(the_bytes[36:48])
        self.radar_id = struct.unpack(estr+'I', the_bytes[48:52])[0]
        self.swid = _get_string(the_bytes[52:76])


class _GFFHeader_1_8(object):
    """
    Interpreter for the GFF version 1.8 header
    """

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        self.file_object = fi
        self.estr = estr

        self.version = '1.8'
        fi.seek(12, os.SEEK_SET)
        # starting at line 3 of def
        self.header_length = struct.unpack(estr+'I', fi.read(4))[0]
        if self.header_length < 2040:
            raise ValueError(
                'The provided header is apparently too short to be a version 1.8 GFF header')

        fi.read(2)  # redundant
        self.creator = _get_string(fi.read(24))
        self.date_time = struct.unpack(estr+'6H', fi.read(6*2))  # year, month, day, hour, minute, second
        fi.read(2)  # endian, already parsed
        self.bytes_per_pixel = int(struct.unpack(estr+'f', fi.read(4))[0])
        self.frame_count, self.image_type, self.row_major, self.range_count, \
            self.azimuth_count = struct.unpack(estr+'5I', fi.read(5*4))
        self.scale_exponent, self.scale_mantissa, self.offset_exponent, self.offset_mantissa = \
            struct.unpack(estr+'4i', fi.read(4*4))
        # at line 17 of def

        self.res1 = fi.read(32)  # leave uninterpreted

        fi.read(2)  # redundant
        self.comment = _get_string(fi.read(166))
        self.image_plane = struct.unpack(estr+'I', fi.read(4))[0]
        range_pixel_size, azimuth_pixel_size, azimuth_overlap = struct.unpack(estr+'3I', fi.read(3*4))
        self.range_pixel_size = _rescale_float(range_pixel_size, 1 << 16)
        self.azimuth_pixel_size = _rescale_float(azimuth_pixel_size, 1 << 16)
        self.azimuth_overlap = _rescale_float(azimuth_overlap, 1 << 16)

        srp_lat, srp_lon, srp_alt, rfoa, x_to_srp = struct.unpack(estr+'5i', fi.read(5*4))
        self.srp_lat = _rescale_float(srp_lat, 1 << 23)
        self.srp_lon = _rescale_float(srp_lon, 1 << 23)
        self.srp_alt = _rescale_float(srp_alt, 1 << 16)
        self.rfoa = _rescale_float(rfoa, 1 << 23)
        self.x_to_srp = _rescale_float(x_to_srp, 1 << 16)

        self.res2 = fi.read(32)  # leave uninterpreted

        fi.read(2)
        self.phase_name = _get_string(fi.read(128))
        fi.read(2)
        self.image_name = _get_string(fi.read(128))
        # at line 34 of def

        self.look_count, self.param_ref_ap, self.param_ref_pos = \
            struct.unpack(estr + '3I', fi.read(3*4))

        graze_angle, squint, gta, range_beam_ctr, flight_time = \
            struct.unpack(estr + 'I2i2I', fi.read(5*4))
        self.graze_angle = _rescale_float(graze_angle, 1 << 23)
        self.squint = _rescale_float(squint, 1 << 23)
        self.gta = _rescale_float(gta, 1 << 23)
        self.range_beam_ctr = _rescale_float(range_beam_ctr, 1 << 8)
        self.flight_time = _rescale_float(flight_time, 1000)

        self.range_chirp_rate, x_to_start, self.mo_comp_mode, v_x = \
            struct.unpack(estr + 'fi2I', fi.read(4*4))
        self.x_to_start = _rescale_float(x_to_start, 1 << 16)
        self.v_x = _rescale_float(v_x, 1 << 16)
        # at line 46 of def

        apc_lat, apc_lon, apc_alt = struct.unpack(estr + '3i', fi.read(3*4))
        self.apc_lat = _rescale_float(apc_lat, 1 << 23)
        self.apc_lon = _rescale_float(apc_lon, 1 << 23)
        self.apc_alt = _rescale_float(apc_alt, 1 << 16)

        cal_parm, self.logical_block_address = struct.unpack(estr + '2I', fi.read(2*4))
        self.cal_parm = _rescale_float(cal_parm, 1 << 24)
        az_resolution, range_resolution = struct.unpack(estr + '2I', fi.read(2*4))
        self.az_resolution = _rescale_float(az_resolution, 1 << 16)
        self.range_resolution = _rescale_float(range_resolution, 1 << 16)

        des_sigma_n, des_graze, des_squint, des_range, scene_track_angle = \
            struct.unpack(estr + 'iIiIi', fi.read(5*4))
        self.des_sigma_n = _rescale_float(des_sigma_n, 1 << 23)
        self.des_graze = _rescale_float(des_graze, 1 << 23)
        self.des_squint = _rescale_float(des_squint, 1 << 23)
        self.des_range = _rescale_float(des_range, 1 << 8)
        self.scene_track_angle = _rescale_float(scene_track_angle, 1 << 23)
        # at line 58 of def

        self.user_param = fi.read(48)  # leave uninterpreted

        self.coarse_snr, self.coarse_azimuth_sub, self.coarse_range_sub, \
        self.max_azimuth_shift, self.max_range_shift, \
        self.coarse_delta_azimuth, self.coarse_delta_range = \
            struct.unpack(estr + '7i', fi.read(7*4))

        self.tot_procs, self.tpt_box_cmode, self.snr_thresh, self.range_size, \
        self.map_box_size, self.box_size, self.box_spc, self.tot_tpts, \
        self.good_tpts, self.range_seed, self.range_shift, self.azimuth_shift = \
            struct.unpack(estr + '12i', fi.read(12*4))
        # at line 78 of def

        self.sum_x_ramp, self.sum_y_ramp = struct.unpack(estr + '2i', fi.read(2*4))
        self.cy9k_tape_block, self.nominal_center_frequency = struct.unpack(estr + 'If', fi.read(2*4))
        self.image_flags, self.line_number, self.patch_number = struct.unpack(estr + '3I', fi.read(3*4))
        self.lambda0, self.srange_pix_space = struct.unpack(estr + '2f', fi.read(2*4))
        self.dopp_pix_space, self.dopp_offset, self.dopp_range_scale, self.mux_time_delay = \
            struct.unpack(estr + '4f', fi.read(4*4))
        # at line 91 of def

        self.apc_ecef = struct.unpack(estr+'3d', fi.read(3*8))
        self.vel_ecef = struct.unpack(estr+'3f', fi.read(3*4))
        self.phase_cal = struct.unpack(estr+'f', fi.read(4))[0]
        self.srp_ecef = struct.unpack(estr+'3d', fi.read(3*8))

        self.res5 = fi.read(64)  # leave uninterpreted
        # at line 102

        self.header_length1 = struct.unpack(estr+'I', fi.read(4))[0]
        self.image_date = struct.unpack(estr+'6H', fi.read(6*2))  # year,month, day, hour, minute, second
        self.comp_file_name = _get_string(fi.read(128))
        self.ref_file_name = _get_string(fi.read(128))

        self.IE = _Radar_1_8(fi.read(76), estr)
        self.IF = _Radar_1_8(fi.read(76), estr)
        self.if_algo = _get_string(fi.read(8))
        self.PH = _Radar_1_8(fi.read(76), estr)
        # at line 122 of def

        self.ph_data_rcd, self.proc_product = struct.unpack(estr+'2i', fi.read(2*4))
        self.mission_text = _get_string(fi.read(8))
        self.ph_source, self.gps_week = struct.unpack(estr+'iI', fi.read(2*4))
        self.data_collect_reqh = _get_string(fi.read(14))
        self.res6 = fi.read(2)  # leave uninterpreted
        # at line 129

        self.grid_name = _get_string(fi.read(24))
        self.pix_val_linearity, self.complex_or_real, self.bits_per_magnitude, \
            self.bits_per_phase = struct.unpack(estr+'2i2H', fi.read(2*4+2*2))
        self.complex_order_type, self.pix_data_type, self.image_length, \
            self.image_cmp_scheme = struct.unpack(estr+'4i', fi.read(4*4))
        # at line 138

        self.apbo, self.asa_pitch, self.asa_squint, self.dsa_pitch, self.ira = \
            struct.unpack(estr+'5f', fi.read(5*4))
        self.rx_polarization = struct.unpack(estr+'2f', fi.read(2*4))
        self.tx_polarization = struct.unpack(estr+'2f', fi.read(2*4))
        self.v_avg = struct.unpack(estr+'3f', fi.read(3*4))
        self.apc_avg = struct.unpack(estr+'3f', fi.read(3*4))
        self.averaging_time, self.dgta = struct.unpack(estr+'2f', fi.read(2*4))
        # at line 153

        velocity_y, velocity_z = struct.unpack(estr+'2I', fi.read(2*4))
        self.velocity_y = _rescale_float(velocity_y, 1 << 16)
        self.velocity_z = _rescale_float(velocity_z, 1 << 16)

        self.ba, self.be = struct.unpack(estr+'2f', fi.read(2*4))
        self.az_geom_corr, self.range_geom_corr, self.az_win_fac_bw, \
            self.range_win_fac_bw = struct.unpack(estr+'2i2f', fi.read(4*4))
        self.az_win_id = _get_string(fi.read(48))
        self.range_win_id = _get_string(fi.read(48))
        # at line 163

        self.keep_out_viol_prcnt = struct.unpack(estr+'f', fi.read(4))[0]
        self.az_coeff = struct.unpack(estr+'6f', fi.read(6*4))
        self.pos_uncert = struct.unpack(estr+'3f', fi.read(3*4))
        self.nav_aiding_type = struct.unpack(estr+'i', fi.read(4))[0]
        self.two_dnl_phase_coeffs = struct.unpack(estr+'10f', fi.read(10*4))
        self.clutter_snr_thresh = struct.unpack(estr+'f', fi.read(4))[0]
        # at line 171

        self.elevation_coeff = struct.unpack(estr+'9f', fi.read(9*4))
        self.monopulse_coeff = struct.unpack(estr+'12f', fi.read(12*4))
        self.twist_pt_err_prcnt, self.tilt_pt_err_prcnt, self.az_pt_err_prcnt = \
            struct.unpack(estr+'3f', fi.read(3*4))
        sigma_n, self.take_num = struct.unpack(estr+'Ii', fi.read(2*4))
        self.sigma_n = _rescale_float(sigma_n, 1 << 23)

        self.if_sar_flags = struct.unpack(estr+'5i', fi.read(5*4))
        self.mu_threshold, self.gff_app_type = struct.unpack(estr+'fi', fi.read(2*4))
        self.res7 = fi.read(8)  # leave uninterpreted


#####################
# version 2 specific header parsing

# NB: I am only parsing the GSATIMG, APINFO, IFINFO, and GEOINFO blocks
#   because those are the only blocks referenced in the matlab that I
#   am mirroring


class _BlockHeader_2(object):
    """
    Read and interpret a block "sub"-header. This generically precedes every version
    2 data block, including the main file header
    """

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        self.name = _get_string(fi.read(16))
        self.major_version, self.minor_version = struct.unpack(estr+'HH', fi.read(2*2))
        what0 = fi.read(4)  # not sure what this is from looking at the matlab.
        self.size = struct.unpack(estr+'I', fi.read(4))[0]
        what1 = fi.read(4)  # not sure what this is from looking at the matlab.
        if (self.version == '2.0' and self.size == 64) or (self.version == '1.0' and self.size == 52):
            self.name = 'RADARINFO'  # fix known issue for some early version 2 GFF files

    @property
    def version(self):
        """
        str: The version
        """
        pass


# APINFO definitions
class _APInfo_1_0(object):
    """
    The APINFO block
    """
    serialized_length = 314

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        self.missionText = _get_string(fi.read(8))
        self.swVerNum = _get_string(fi.read(8))
        self.radarSerNum, self.phSource = struct.unpack(estr+'2I', fi.read(2*4))
        fi.read(2)
        self.phName = _get_string(fi.read(128))
        self.ctrFreq, self.wavelength = struct.unpack(estr+'2f', fi.read(2*4))
        self.rxPolarization, self.txPolarization = struct.unpack(estr+'2I', fi.read(2*4))
        self.azBeamWidth, self.elBeamWidth = struct.unpack(estr+'2f', fi.read(2*4))
        self.grazingAngle, self.squintAngle, self.gta, self.rngToBeamCtr = \
            struct.unpack(estr+'4f', fi.read(4*4))
        # line 16

        self.desSquint, self.desRng, self.desGTA, self.antPhaseCtrBear = \
            struct.unpack(estr+'4f', fi.read(4*4))
        self.ApTimeUTC = struct.unpack(estr+'6H', fi.read(6*2))
        self.flightTime, self.flightWeek = struct.unpack(estr+'2I', fi.read(2*4))
        self.chirpRate, self.xDistToStart = struct.unpack(estr+'2f', fi.read(2*4))
        self.momeasMode, self.radarMode = struct.unpack(estr+'2I', fi.read(2*4))
        # line 32

        self.rfoa = struct.unpack(estr+'f', fi.read(4))[0]
        self.apcVel = struct.unpack(estr+'3d', fi.read(3*8))
        self.apcLLH = struct.unpack(estr+'3d', fi.read(3*8))
        self.keepOutViol, self.gimStopTwist, self.gimStopTilt, self.gimStopAz = \
            struct.unpack(estr+'4f', fi.read(4*4))


class _APInfo_2_0(_APInfo_1_0):
    """
    The APINFO block
    """
    serialized_length = 318

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        _APInfo_1_0.__init__(self, fi, estr)
        self.apfdFactor = struct.unpack(estr+'i', fi.read(4))[0]


class _APInfo_3_0(_APInfo_2_0):
    """
    The APINFO block
    """
    serialized_length = 334

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        _APInfo_2_0.__init__(self, fi, estr)
        self.fastTimeSamples, self.adSampleFreq, self.apertureTime, \
            self.numPhaseHistories = struct.unpack(estr+'I2fI', fi.read(4*4))


class _APInfo_4_0(object):
    """
    The APINFO block
    """
    serialized_length = 418

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        # essentially the same as version 3, except the first two fields are longer
        self.missionText = _get_string(fi.read(50))
        self.swVerNum = _get_string(fi.read(50))
        self.radarSerNum, self.phSource = struct.unpack(estr+'2I', fi.read(2*4))
        fi.read(2)
        self.phName = _get_string(fi.read(128))
        self.ctrFreq, self.wavelength = struct.unpack(estr+'2f', fi.read(2*4))
        self.rxPolarization, self.txPolarization = struct.unpack(estr+'2I', fi.read(2*4))
        self.azBeamWidth, self.elBeamWidth = struct.unpack(estr+'2f', fi.read(2*4))
        self.grazingAngle, self.squintAngle, self.gta, self.rngToBeamCtr = \
            struct.unpack(estr+'4f', fi.read(4*4))
        # line 16

        self.desSquint, self.desRng, self.desGTA, self.antPhaseCtrBear = \
            struct.unpack(estr+'4f', fi.read(4*4))
        self.ApTimeUTC = struct.unpack(estr+'6H', fi.read(6*2))
        self.flightTime, self.flightWeek = struct.unpack(estr+'2I', fi.read(2*4))
        self.chirpRate, self.xDistToStart = struct.unpack(estr+'2f', fi.read(2*4))
        self.momeasMode, self.radarMode = struct.unpack(estr+'2I', fi.read(2*4))
        # line 32

        self.rfoa = struct.unpack(estr+'f', fi.read(4))[0]
        self.apcVel = struct.unpack(estr+'3d', fi.read(3*8))
        self.apcLLH = struct.unpack(estr+'3d', fi.read(3*8))
        self.keepOutViol, self.gimStopTwist, self.gimStopTilt, self.gimStopAz = \
            struct.unpack(estr+'4f', fi.read(4*4))

        self.apfdFactor = struct.unpack(estr+'i', fi.read(4))[0]
        self.fastTimeSamples, self.adSampleFreq, self.apertureTime, \
            self.numPhaseHistories = struct.unpack(estr+'I2fI', fi.read(4*4))


class _APInfo_5_0(_APInfo_4_0):
    """
    The APINFO block
    """
    serialized_length = 426

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        _APInfo_4_0.__init__(self, fi, estr)
        self.lightSpeed = struct.unpack(estr+'d', fi.read(8))[0]  # really?


class _APInfo_5_1(_APInfo_5_0):
    """
    The APINFO block
    """
    serialized_length = 430

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        _APInfo_5_0.__init__(self, fi, estr)
        self.delTanApAngle = struct.unpack(estr+'f', fi.read(4))[0]


class _APInfo_5_2(_APInfo_5_1):
    """
    The APINFO block
    """
    serialized_length = 434

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        _APInfo_5_1.__init__(self, fi, estr)
        self.metersInSampledDoppler = struct.unpack(estr+'f', fi.read(4))[0]


# IFINFO definitions
class _IFInfo_1_0(object):
    """
    Interpreter for IFInfo object
    """
    serialized_length = 514

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        self.procProduct = struct.unpack(estr+'I', fi.read(4))[0]
        fi.read(2)
        self.imgFileName = _get_string(fi.read(128))
        self.azResolution, self.rngResolution = struct.unpack(estr+'2f', fi.read(2*4))
        self.imgCalParam, self.sigmaN = struct.unpack(estr+'2f', fi.read(2*4))
        self.sampLocDCRow, self.sampLocDCCol = struct.unpack(estr+'2i', fi.read(2*4))
        self.ifAlgo = _get_string(fi.read(8))
        self.imgFlag = struct.unpack(estr+'i', fi.read(4))[0]
        self.azCoeff = struct.unpack(estr+'6f', fi.read(6*4))
        self.elCoeff = struct.unpack(estr+'9f', fi.read(9*4))
        self.azGeoCorrect, self.rngGeoCorrect = struct.unpack(estr+'2i', fi.read(2*4))
        self.wndBwFactAz, self.wndBwFactRng = struct.unpack(estr+'2f', fi.read(2*4))
        self.wndFncIdAz = _get_string(fi.read(48))
        self.wndFncIdRng = _get_string(fi.read(48))
        fi.read(2)
        self.cmtText = _get_string(fi.read(166))
        self.autoFocusInfo = struct.unpack(estr+'i', fi.read(4))[0]


class _IFInfo_2_0(_IFInfo_1_0):
    """
    Interpreter for IFInfo object - identical with version 2.1 and 2.2
    """
    serialized_length = 582

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        _IFInfo_1_0.__init__(self, fi, estr)
        self.rngFFTSize = struct.unpack(estr+'i', fi.read(4))[0]
        self.RangePaneFilterCoeff = struct.unpack(estr+'11f', fi.read(11*4))
        self.AzPreFilterCoeff = struct.unpack(estr+'5f', fi.read(5*4))


class _IFInfo_3_0(_IFInfo_2_0):
    """
    Interpreter for IFInfo object
    """
    serialized_length = 586

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        _IFInfo_2_0.__init__(self, fi, estr)
        self.afPeakQuadComp = struct.unpack(estr+'f', fi.read(4))[0]


# GEOINFO definitions
class _GeoInfo_1(object):
    """
    Interpreter for GeoInfo object - note that versions 1.0 and 1.1 are identical
    """
    serialized_length = 52

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        self.imagePlane = struct.unpack(estr+'i', fi.read(4))[0]
        self.rangePixSpacing, self.desiredGrazAng, self.azPixSpacing = \
            struct.unpack(estr+'3f', fi.read(3*4))
        self.patchCtrLLH = struct.unpack(estr+'3d', fi.read(3*8))
        self.pixLocImCtrRow, self.pixLocImCtrCol = struct.unpack(estr+'2I', fi.read(2*4))
        self.imgRotAngle = struct.unpack(estr+'f', fi.read(4))[0]


# GSATIMG definition

def _get_complex_domain_code(code_int):
    # type: (int) -> str
    pass


def _get_band_order(code_int):
    # type: (int) -> str
    pass


class _PixelFormat(object):
    """
    Interpreter for pixel format object
    """

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        self.comp0_bitSize, self.comp0_dataType = struct.unpack(estr+'HI', fi.read(2+4))
        self.comp1_bitSize, self.comp1_dataType = struct.unpack(estr+'HI', fi.read(2+4))
        self.cmplxDomain, self.numComponents = struct.unpack(estr+'Ii', fi.read(2*4))


class _GSATIMG_2(object):
    """
    Interpreter for the GSATIMG object
    """
    serialized_length = 82

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        self.endian = struct.unpack(estr+'I', fi.read(4))[0]
        fi.read(2)
        self.imageCreator = _get_string(fi.read(24))
        self.rangePixels, self.azPixels = struct.unpack(estr+'2I', fi.read(2*4))
        self.pixOrder, self.imageLengthBytes, self.imageCompressionScheme, \
            self.pixDataType = struct.unpack(estr+'4I', fi.read(4*4))
        self.pixelFormat = _PixelFormat(fi, estr)
        self.pixValLin, self.autoScaleFac = struct.unpack(estr+'if', fi.read(2*4))

        complex_domain = _get_complex_domain_code(self.pixelFormat.cmplxDomain)
        if complex_domain not in ['IQ', 'QI', 'MP', 'PM']:
            raise ValueError('We got unsupported complex domain `{}`'.format(complex_domain))


# combined GFF version 2 header collection
def _check_serialization(
        block_header: _BlockHeader_2,
        expected_length: int) -> None:
    pass


class _GFFHeader_2(object):
    """
    Interpreter for the GFF version 2.* header
    """

    __slots__ = (
        'file_object', 'estr', '_gsat_img', '_ap_info', '_if_info', '_geo_info',
        '_image_header', '_image_offset')

    def __init__(self, fi, estr):
        """

        Parameters
        ----------
        fi : BinaryIO
        estr : str
            The endianness string for format interpretation, one of `['<', '>']`
        """

        self._gsat_img = None
        self._ap_info = None
        self._if_info = None
        self._geo_info = None
        self._image_header = None
        self._image_offset = None
        self.file_object = fi
        self.estr = estr

        # extract the initial file location
        init_location = fi.tell()

        # go to the begining of the file
        fi.seek(0, os.SEEK_SET)
        gsat_header = _BlockHeader_2(fi, estr)
        self._gsat_img = _GSATIMG_2(fi, estr)

        while True:
            block_header = _BlockHeader_2(fi, estr)
            if block_header.name == 'IMAGEDATA':
                self._image_header = block_header
                self._image_offset = fi.tell()
                break
            elif block_header.name == 'APINFO':
                self._parse_apinfo(fi, estr, block_header)
            elif block_header.name == 'IFINFO':
                self._parse_ifinfo(fi, estr, block_header)
            elif block_header.name == 'GEOINFO':
                self._parse_geoinfo(fi, estr, block_header)
            else:
                # we are not parsing this block, so just skip it
                fi.seek(block_header.size, os.SEEK_CUR)

        # return to the initial file location
        fi.seek(init_location, os.SEEK_SET)
        self._check_valid(gsat_header)

    @property
    def gsat_img(self) -> _GSATIMG_2:
        pass

    @property
    def ap_info(self) -> Union[_APInfo_1_0, _APInfo_2_0, _APInfo_3_0, _APInfo_4_0, _APInfo_5_0, _APInfo_5_1, _APInfo_5_2]:
        pass

    @property
    def if_info(self) -> Union[_IFInfo_1_0, _IFInfo_2_0, _IFInfo_3_0]:
        pass

    @property
    def geo_info(self) -> _GeoInfo_1:
        pass

    @property
    def image_header(self) -> _BlockHeader_2:
        pass

    @property
    def image_offset(self) -> int:
        pass

    def _parse_apinfo(self, fi, estr, block_header) -> None:
        pass

    def _parse_ifinfo(self, fi, estr, block_header) -> None:
        pass

    def _parse_geoinfo(self, fi, estr, block_header) -> None:
        pass

    def _check_valid(self, gsat_header) -> None:
        # ensure that the required elements are all set
        pass

    def get_arp_vel(self) -> numpy.ndarray:
        """
        Gets the aperture velocity in ECF coordinates

        Returns
        -------
        numpy.ndarray
        """
        pass


####################
# object for creation of sicd structure from GFF header object

def _get_wgt(str_in: str) -> Optional[WgtTypeType]:
    pass


def _get_polarization_string(int_value: int) -> Optional[str]:
    pass


def _get_tx_rcv_polarization(tx_pol_int: int, rcv_pol_int: int) -> Tuple[str, str]:
    pass


class _GFFInterpreter(object):
    """
    Extractor for the sicd details
    """

    def get_sicd(self) -> SICDType:
        """
        Gets the SICD structure.

        Returns
        -------
        SICDType
        """

        raise NotImplementedError

    def get_data_segment(self) -> DataSegment:
        """
        Gets the chipper for reading the data.

        Returns
        -------
        DataSegment
        """

        raise NotImplementedError

    def clean_up(self) -> None:
        return


class _GFFInterpreter1(_GFFInterpreter):
    """
    Extractor of SICD structure and parameters from gff_header_1*
    object
    """

    def __init__(self, header: Union[_GFFHeader_1_6, _GFFHeader_1_8]):
        """

        Parameters
        ----------
        header : _GFFHeader_1_6|_GFFHeader_1_8
        """

        self.header = header
        if self.header.image_type == 0:
            raise ValueError(
                'ImageType indicates a magnitude only image, which is incompatible with SICD')

    def get_sicd(self) -> SICDType:
        pass

    def get_data_segment(self) -> DataSegment:
        pass


def _get_numpy_dtype(data_type_int: int) -> str:
    pass


class _GFFInterpreter2(_GFFInterpreter):
    """
    Extractor of SICD structure and parameters from GFFHeader_2 object
    """

    def __init__(self, header: _GFFHeader_2):
        """

        Parameters
        ----------
        header : _GFFHeader_2
        """

        self.header = header
        self._cached_files = []
        if self.header.gsat_img.pixelFormat.numComponents != 2:
            raise ValueError(
                'The pixel format indicates that the number of components is `{}`, '
                'which is not supported for a complex image'.format(
                    self.header.gsat_img.pixelFormat.numComponents))

    def get_sicd(self) -> SICDType:
        pass

    def _get_size_and_symmetry(self) -> Tuple[Tuple[int, int], Tuple[int, ...], bool]:
        pass

    def _check_image_validity(self, band_order: str) -> None:
        pass

    def _extract_zlib_image(self) -> str:
        pass

    def _extract_pil_image(
            self,
            band_order: str,
            data_size: Tuple[int, int]) -> str:
        pass

    def _get_interleaved_segment(self) -> DataSegment:
        pass

    def _get_sequential_segment(self) -> DataSegment:
        pass

    def get_data_segment(self) -> DataSegment:
        pass

    def clean_up(self) -> None:
        try:
            if self._cached_files is not None:
                for fil in self._cached_files:
                    if os.path.exists(fil):
                        # noinspection PyBroadException
                        try:
                            os.remove(fil)
                            logger.info('Deleted cached file {}'.format(fil))
                        except Exception:
                            logger.error(
                                'Error in attempt to delete cached file {}.\n\t'
                                'Manually delete this file'.format(fil), exc_info=True)
            self._cached_files = None
        except AttributeError:
            return

    def __del__(self):
        """
        Clean up any cached files.

        Returns
        -------
        None
        """

        self.clean_up()


####################
# the actual reader implementation

class GFFDetails(object):
    __slots__ = (
        '_file_name', '_file_object', '_close_after',
        '_endianness', '_major_version', '_minor_version',
        '_header', '_interpreter')

    def __init__(self, file_name: str):
        """

        Parameters
        ----------
        file_name : str
        """

        self._endianness = None
        self._major_version = None
        self._minor_version = None
        self._header = None
        self._close_after = True
        self._interpreter = None

        if not os.path.isfile(file_name):
            raise SarpyIOError('Path {} is not a file'.format(file_name))
        self._file_name = file_name
        self._file_object = open(self._file_name, 'rb')

        check = self._file_object.read(7)
        if check != b'GSATIMG':
            self._file_object.close()
            self._close_after = False
            raise SarpyIOError('file {} is not a GFF file'.format(self._file_name))

        # initialize things
        self._initialize()

    @property
    def file_name(self) -> str:
        """
        str: the file name
        """
        pass

    @property
    def endianness(self) -> str:
        """
        str: The endian format of the GFF storage. Returns '<' if little-endian
        or '>' if big endian.
        """
        pass

    @property
    def major_version(self) -> int:
        """
        int: The major GFF version number
        """
        pass

    @property
    def minor_version(self) -> int:
        """
        int: The minor GFF version number
        """
        pass

    @property
    def version(self) -> str:
        """
        str: The GFF version number
        """
        pass

    @property
    def header(self) -> Union[_GFFHeader_1_6, _GFFHeader_1_8, _GFFHeader_2]:
        """
        The GFF header object.

        Returns
        -------
        _GFFHeader_1_6|_GFFHeader_1_8|_GFFHeader_2
        """
        pass

    @property
    def interpreter(self) -> _GFFInterpreter:
        """
        The GFF interpreter object.

        Returns
        -------
        _GFFInterpreter
        """
        pass

    def _initialize(self) -> None:
        """
        Initialize the various elements
        """
        pass

    def get_sicd(self) -> SICDType:
        """
        Gets the sicd structure.

        Returns
        -------
        SICDType
        """
        pass

    def get_data_segment(self) -> DataSegment:
        """
        Gets the data segment.

        Returns
        -------
        DataSegment
        """
        pass

    def close(self):
        try:
            if self._close_after:
                self._file_object.close()
            if self._interpreter is not None:
                self._interpreter.clean_up()
            self._interpreter = None
        except AttributeError:
            pass

    def __del__(self):
        self.close()


class GFFReader(SICDTypeReader):
    """
    A GFF (Sandia format) reader implementation.

    **Changed in version 1.3.0** for reading changes.
    """

    __slots__ = ('_gff_details', )

    def __init__(self, gff_details: Union[str, GFFDetails]):
        """

        Parameters
        ----------
        gff_details : str|GFFDetails
            file name or GFFDetails object
        """

        if isinstance(gff_details, str):
            gff_details = GFFDetails(gff_details)
        if not isinstance(gff_details, GFFDetails):
            raise TypeError('The input argument for a GFFReader must be a '
                            'filename or GFFDetails object')
        self._gff_details = gff_details

        sicd = gff_details.get_sicd()
        data_segment = gff_details.get_data_segment()
        SICDTypeReader.__init__(self, data_segment, sicd, close_segments=True)
        self._check_sizes()

    @property
    def gff_details(self) -> GFFDetails:
        """
        GFFDetails: The details object.
        """
        pass

    @property
    def file_name(self):
        pass

    def close(self) -> None:
        SICDTypeReader.close(self)
        if self._gff_details is not None:
            self._gff_details.close()
        self._gff_details = None

    def __del__(self):
        self.close()


########
# base expected functionality for a module with an implemented Reader

def is_a(file_name: str) -> Optional[GFFReader]:
    """
    Tests whether a given file_name corresponds to a Cosmo Skymed file. Returns a reader instance, if so.

    Parameters
    ----------
    file_name : str|BinaryIO
        the file_name to check

    Returns
    -------
    CSKReader|None
        `CSKReader` instance if Cosmo Skymed file, `None` otherwise
    """
    pass
