"""
Methods for ortho-rectification
"""

__classification__ = "UNCLASSIFIED"
__author__ = "Thomas McCullough"


import logging
from typing import Union

import numpy
from scipy.interpolate import RectBivariateSpline

from sarpy.io.complex.sicd_elements.SICD import SICDType
from sarpy.io.complex.base import SICDTypeReader

from sarpy.io.complex.sicd_elements.blocks import Poly2DType
from sarpy.geometry.geometry_elements import GeometryObject

from .projection_helper import ProjectionHelper, PGProjection, PGRatPolyProjection
from ..rational_polynomial import SarpyRatPolyError

logger = logging.getLogger(__name__)


def _linear_fill(pixel_array, fill_interval=1):
    """
    This is to fill in linear features in pixel space at the given interval.
    When the first and last vertices are not identical, an implicit edge connecting them is also filled.

    Parameters
    ----------
    pixel_array : numpy.ndarray
    fill_interval : int|float

    Returns
    -------
    numpy.ndarray
    """

    if not isinstance(pixel_array, numpy.ndarray):
        raise TypeError('pixel_array must be a numpy array. Got type {}'.format(type(pixel_array)))
    if pixel_array.ndim < 2:
        # nothing to be done
        return pixel_array

    if pixel_array.ndim > 2:
        raise ValueError('pixel_array must be no more than two-dimensional. Got shape {}'.format(pixel_array.shape))
    if pixel_array.shape[1] != 2:
        raise ValueError(
            'pixel_array is two dimensional, and the final dimension must have length 2. '
            'Got shape {}'.format(pixel_array.shape))
    if pixel_array.shape[0] < 2:
        # nothing to be done
        return pixel_array

    def make_segment(start_point, end_point):
        segment_length = numpy.linalg.norm(end_point - start_point)
        segment_count = max(2, int(numpy.ceil(segment_length/float(fill_interval) + 1)))
        segment = numpy.zeros((segment_count, 2), dtype=numpy.float64)
        # NB: it's ok if start == end in linspace
        segment[:, 0] = numpy.linspace(start_point[0], end_point[0], segment_count)
        segment[:, 1] = numpy.linspace(start_point[1], end_point[1], segment_count)
        return segment

    segments = []
    for i in range(pixel_array.shape[0]-1):
        start_segment = pixel_array[i, :]
        end_segment = pixel_array[i+1, :]
        segments.append(make_segment(start_segment, end_segment))
    if not numpy.array_equal(pixel_array[0], pixel_array[-1]):
        # include line connecting  first and last points if they are not the same
        segments.append(make_segment(pixel_array[0], pixel_array[-1]))
    return numpy.vstack(segments)


class OrthorectificationHelper(object):
    """
    Abstract helper class which defines ortho-rectification process for a sicd-type
    reader object.
    """

    __slots__ = (
        '_reader', '_index', '_sicd', '_proj_helper', '_out_dtype', '_complex_valued',
        '_pad_value', '_apply_radiometric', '_subtract_radiometric_noise',
        '_rad_poly', '_noise_poly', '_default_physical_bounds')

    def __init__(self, reader, index=0, proj_helper=None, complex_valued=False,
                 pad_value=None, apply_radiometric=None, subtract_radiometric_noise=False):
        """

        Parameters
        ----------
        reader : SICDTypeReader
        index : int
        proj_helper : None|ProjectionHelper
            If `None`, this will default to `PGRatPolyProjection(<sicd>)` unless there is
            a SarpyRatPolyError, when it will fall back to `PGProjection(<sicd>)`,
            where `<sicd>` will be the sicd from `reader` at `index`. Otherwise,
            it is the user's responsibility to ensure that `reader`, `index` and
            `proj_helper` are in sync.
        complex_valued : bool
            Do we want complex values returned? If `False`, the magnitude values
            will be used.
        pad_value : None|Any
            Value to use for any out-of-range pixels. Defaults to `0` if not provided.
        apply_radiometric : None|str
            If provided, must be one of `['RCS', 'Sigma0', 'Gamma0', 'Beta0']`
            (not case-sensitive). This will apply the given radiometric scale factor
            to calculated pixel power, with noise subtracted if `subtract_radiometric_noise = True`.
            **Only valid if `complex_valued=False`**.
        subtract_radiometric_noise : bool
            This indicates whether the radiometric noise should be subtracted from
            the pixel amplitude. **Only valid if `complex_valued=False`**.
        """

        self._index = None
        self._sicd = None
        self._proj_helper = None
        self._apply_radiometric = None
        self._subtract_radiometric_noise = None
        self._rad_poly = None  # type: [None, Poly2DType]
        self._noise_poly = None  # type: [None, Poly2DType]
        self._default_physical_bounds = None

        self._pad_value = pad_value
        self._complex_valued = complex_valued
        if self._complex_valued:
            self._out_dtype = numpy.dtype('complex64')
        else:
            self._out_dtype = numpy.dtype('float32')
        if not isinstance(reader, SICDTypeReader):
            raise TypeError('Got unexpected type {} for reader'.format(type(reader)))
        self._reader = reader
        self.apply_radiometric = apply_radiometric
        self.subtract_radiometric_noise = subtract_radiometric_noise
        self.set_index_and_proj_helper(index, proj_helper=proj_helper)

    @property
    def reader(self):
        # type: () -> SICDTypeReader
        """
        SICDTypeReader: The reader instance.
        """
        pass

    @property
    def index(self):
        # type: () -> int
        """
        int: The index for the desired sicd element.
        """
        return self._index

    @property
    def sicd(self):
        # type: () -> SICDType
        """
        SICDType: The sicd structure.
        """
        pass

    @property
    def proj_helper(self):
        # type: () -> ProjectionHelper
        """
        ProjectionHelper: The projection helper instance.
        """
        pass

    @property
    def out_dtype(self):
        # type: () -> numpy.dtype
        """
        numpy.dtype: The output data type.
        """
        pass

    @property
    def pad_value(self):
        """
        The value to use for any portions of the array which extend beyond the range
        of where the reader has data.
        """
        pass

    @pad_value.setter
    def pad_value(self, value):
        pass

    def set_index_and_proj_helper(self, index, proj_helper=None):
        """
        Sets the index and proj_helper objects.

        Parameters
        ----------
        index : int
        proj_helper : ProjectionHelper

        Returns
        -------
        None
        """
        pass

    @property
    def apply_radiometric(self):
        # type: () -> Union[None, str]
        """
        None|str: This indicates which, if any, of the radiometric scale factors
        to apply in the result. If not `None`, this must be one of ('RCS', 'SIGMA0', 'GAMMA0', 'BETA0').

        Setting to a value other than `None` will result in an error if 1.) `complex_valued` is `True`, or
        2.) the appropriate corresponding element `sicd.Radiometric.RCSSFPoly`,
        `sicd.Radiometric.SigmaZeroSFPoly`, `sicd.Radiometric.GammaZeroSFPoly`, or
        `sicd.Radiometric.BetaZeroSFPoly` is not populated with a valid polynomial.
        """
        pass

    @apply_radiometric.setter
    def apply_radiometric(self, value):
        pass

    @property
    def subtract_radiometric_noise(self):
        """
        bool: This indicates whether the radiometric noise should be subtracted from
        the pixel amplitude. If `apply_radiometric` is not `None`, then this subtraction
        will happen applying the corresponding scaling.

        Setting this to `True` will **result in an error** unless the given sicd structure has
        `sicd.Radiometric.NoiseLevel.NoisePoly` populated with a viable polynomial and
        `sicd.Radiometric.NoiseLevel.NoiseLevelType == 'ABSOLUTE'`.
        """
        pass

    @subtract_radiometric_noise.setter
    def subtract_radiometric_noise(self, value):
        pass

    def _is_radiometric_valid(self):
        """
        Checks whether the apply radiometric settings are valid.

        Returns
        -------
        None
        """
        pass

    def _is_radiometric_noise_valid(self):
        """
        Checks whether the subtract_radiometric_noise setting is valid.

        Returns
        -------
        None
        """
        pass

    def get_full_ortho_bounds(self):
        """
        Gets the bounds for the ortho-rectified coordinates for the full sicd image.

        Returns
        -------
        numpy.ndarray
            Of the form `[min row, max row, min column, max column]`.
        """

        if self._default_physical_bounds is not None:
            ortho_rectangle = self.proj_helper.ecf_to_ortho(self._default_physical_bounds)
            return self.proj_helper.get_pixel_array_bounds(ortho_rectangle)

        full_coords = self.sicd.ImageData.get_full_vertex_data()
        full_line = _linear_fill(full_coords, fill_interval=1)
        return self.get_orthorectification_bounds_from_pixel_object(full_line)

    def get_valid_ortho_bounds(self):
        """
        Gets the bounds for the ortho-rectified coordinates for the valid portion
        of the sicd image. This is the outer bounds of the valid portion, so may contain
        some portion which is not itself valid.

        If sicd.ImageData.ValidData is not defined, then the full image bounds will
        be returned.

        Returns
        -------
        numpy.ndarray
            Of the form `[min row, max row, min column, max column]`.
        """
        pass

    def get_orthorectification_bounds_from_pixel_object(self, coordinates):
        """
        Determine the ortho-rectified (coordinate-system aligned) rectangular bounding
        region which contains the provided coordinates in pixel space.

        Parameters
        ----------
        coordinates : GeometryObject|numpy.ndarray|list|tuple
            The coordinate system of the input will be assumed to be pixel space.
            When the first and last vertices are not identical, an implicit edge connecting them is assumed.

        Returns
        -------
        numpy.ndarray
            Of the form `(row_min, row_max, col_min, col_max)`.
        """

        if isinstance(coordinates, GeometryObject):
            # pixel_bounds.shape is (min/max, coordinate-dimensionality)
            pixel_bounds = numpy.array(coordinates.get_bbox()).reshape((2, -1))
            # assume first two coordinate dims are row/col and ignore the rest
            (minrow, mincol), (maxrow, maxcol) = pixel_bounds[:, :2]
            coordinates = numpy.array(
                [[minrow, mincol],
                 [maxrow, mincol],
                 [maxrow, maxcol],
                 [minrow, maxcol]], dtype=numpy.float64)
        filled_coordinates = _linear_fill(coordinates, fill_interval=1)
        ortho = self.proj_helper.pixel_to_ortho(filled_coordinates)
        return self.proj_helper.get_pixel_array_bounds(ortho)

    def get_orthorectification_bounds_from_latlon_object(self, coordinates):
        """
        Determine the ortho-rectified (coordinate-system aligned) rectangular bounding
        region which contains the provided coordinates in lat/lon space.

        Parameters
        ----------
        coordinates : GeometryObject|numpy.ndarray|list|tuple
            The coordinate system of the input will be assumed to be lat/lon space.
            **Note** a GeometryObject is expected to follow lon/lat ordering paradigm,
            by convention.

        Returns
        -------
        numpy.ndarray
            Of the form `(row_min, row_max, col_min, col_max)`.
        """
        pass

    @staticmethod
    def validate_bounds(bounds):
        """
        Validate a pixel type bounds array.

        Parameters
        ----------
        bounds : numpy.ndarray|list|tuple

        Returns
        -------
        numpy.ndarray
        """

        if not isinstance(bounds, numpy.ndarray):
            bounds = numpy.asarray(bounds)

        if bounds.ndim != 1 or bounds.size != 4:
            raise ValueError(
                'bounds is required to be one-dimensional and size 4. '
                'Got input shape {}'.format(bounds.shape))
        if bounds[0] >= bounds[1] or bounds[2] >= bounds[3]:
            raise ValueError(
                'bounds is required to be of the form (min row, max row, min col, max col), '
                'got {}'.format(bounds))

        if issubclass(bounds.dtype.type, numpy.integer):
            return bounds
        else:
            out = numpy.zeros((4,), dtype=numpy.int32)
            out[0:3:2] = (numpy.floor(bounds[0]), numpy.floor(bounds[2]))
            out[1:4:2] = (numpy.ceil(bounds[1]), numpy.ceil(bounds[3]))
            return out

    @staticmethod
    def _get_ortho_mesh(ortho_bounds):
        """
        Fetch a the grid of rows/columns coordinates for the desired rectangle.

        Parameters
        ----------
        ortho_bounds : numpy.ndarray
            Of the form `(min row, max row, min col, max col)`.

        Returns
        -------
        numpy.ndarray
        """
        pass

    @staticmethod
    def _get_mask(pixel_rows, pixel_cols, row_array, col_array):
        """
        Construct the valid mask. This is a helper function, and no error checking
        will be performed for any issues.

        Parameters
        ----------
        pixel_rows : numpy.ndarray
            The array of pixel rows. Must be the same shape as `pixel_cols`.
        pixel_cols : numpy.ndarray
            The array of pixel columns. Must be the same shape as `pixel_rows'.
        row_array : numpy.ndarray
            The rows array used for bounds, must be one dimensional and monotonic.
        col_array : numpy.ndarray
            The columns array used for bounds, must be one dimensional and monotonic.

        Returns
        -------
        numpy.ndarray
        """

        mask = (numpy.isfinite(pixel_rows) &
                numpy.isfinite(pixel_cols) &
                (pixel_rows >= row_array[0]) & (pixel_rows < row_array[-1]) &
                (pixel_cols >= col_array[0]) & (pixel_cols < col_array[-1]))
        return mask

    def bounds_to_rectangle(self, bounds):
        """
        From a bounds style array, construct the four corner coordinate array.
        This follows the SICD convention of going CLOCKWISE around the corners.

        Parameters
        ----------
        bounds : numpy.ndarray|list|tuple
            Of the form `(row min, row max, col min, col max)`.

        Returns
        -------
        (numpy.ndarray, numpy.ndarray)
            The (integer valued) bounds and rectangular coordinates.
        """

        bounds = self.validate_bounds(bounds)
        coords = numpy.zeros((4, 2), dtype=numpy.int32)
        coords[0, :] = (bounds[0], bounds[2])  # row min, col min
        coords[1, :] = (bounds[0], bounds[3])  # row min, col max
        coords[2, :] = (bounds[1], bounds[3])  # row max, col max
        coords[3, :] = (bounds[1], bounds[2])  # row max, col min
        return bounds, coords

    def extract_pixel_bounds(self, bounds):
        """
        Validate the bounds array of orthorectified pixel coordinates, and determine
        the required bounds in reader pixel coordinates. If the

        Parameters
        ----------
        bounds : numpy.ndarray|list|tuple

        Returns
        -------
        (numpy.ndarray, numpy.ndarray)
            The integer valued orthorectified and reader pixel coordinate bounds.
        """

        bounds, coords = self.bounds_to_rectangle(bounds)
        filled_coords = _linear_fill(coords, fill_interval=1)
        pixel_coords = self.proj_helper.ortho_to_pixel(filled_coords)
        pixel_bounds = self.proj_helper.get_pixel_array_bounds(pixel_coords)
        return bounds, self.validate_bounds(pixel_bounds)

    def _initialize_workspace(self, ortho_bounds, final_dimension=0):
        """
        Initialize the orthorectification array workspace.

        Parameters
        ----------
        ortho_bounds : numpy.ndarray
            Of the form `(min row, max row, min col, max col)`.
        final_dimension : int
            The size of the third dimension. If `0`, then it will be omitted.

        Returns
        -------
        numpy.ndarray
        """

        if final_dimension > 0:
            out_shape = (
                int(ortho_bounds[1] - ortho_bounds[0]),
                int(ortho_bounds[3] - ortho_bounds[2]),
                int(final_dimension))
        else:
            out_shape = (
                int(ortho_bounds[1]-ortho_bounds[0]),
                int(ortho_bounds[3]-ortho_bounds[2]))
        return numpy.zeros(out_shape, dtype=self.out_dtype) if self._pad_value is None else \
            numpy.full(out_shape, self._pad_value, dtype=self.out_dtype)

    def get_real_pixel_bounds(self, pixel_bounds):
        """
        Fetch the real pixel limit from the nominal pixel limits - this just
        factors in the image reader extent.

        Parameters
        ----------
        pixel_bounds : numpy.ndarray

        Returns
        -------
        numpy.ndarray
        """

        if pixel_bounds[0] > pixel_bounds[1] or pixel_bounds[2] > pixel_bounds[3]:
            raise ValueError('Got unexpected and invalid pixel_bounds array {}'.format(pixel_bounds))

        pixel_limits = self.reader.get_data_size_as_tuple()[self.index]
        if (pixel_bounds[0] >= pixel_limits[0]) or (pixel_bounds[1] < 0) or \
                (pixel_bounds[2] >= pixel_limits[1]) or (pixel_bounds[3] < 0):
            # this entirely misses the whole region
            return numpy.array([0, 0, 0, 0], dtype=numpy.int32)

        real_pix_bounds = numpy.array([
            max(0, pixel_bounds[0]), min(pixel_limits[0], pixel_bounds[1]),
            max(0, pixel_bounds[2]), min(pixel_limits[1], pixel_bounds[3])], dtype=numpy.int32)
        return real_pix_bounds

    def _apply_radiometric_params(self, pixel_rows, pixel_cols, value_array):
        """
        Apply the radiometric parameters to the solution array.

        Parameters
        ----------
        pixel_rows : numpy.ndarray
        pixel_cols : numpy.ndarray
        value_array : numpy.ndarray

        Returns
        -------
        numpy.ndarray
        """

        if self._rad_poly is None and self._noise_poly is None:
            # nothing to be done.
            return value_array

        if pixel_rows.shape == value_array.shape and pixel_cols.shape == value_array.shape:
            rows_meters = (pixel_rows - self.sicd.ImageData.SCPPixel.Row)*self.sicd.Grid.Row.SS
            cols_meters = (pixel_cols - self.sicd.ImageData.SCPPixel.Col)*self.sicd.Grid.Col.SS
        elif value_array.ndim == 2 and \
            (pixel_rows.ndim == 1 and pixel_rows.size == value_array.shape[0]) and \
                (pixel_cols.ndim == 1 and pixel_cols.size == value_array.shape[1]):
            cols_meters, rows_meters = numpy.meshgrid(
                (pixel_cols - self.sicd.ImageData.SCPPixel.Col)*self.sicd.Grid.Col.SS,
                (pixel_rows - self.sicd.ImageData.SCPPixel.Row) * self.sicd.Grid.Row.SS)
        else:
            raise ValueError(
                'Either pixel_rows, pixel_cols, and value_array must all have the same shape, '
                'or pixel_rows/pixel_cols are one dimensional and '
                'value_array.shape = (pixel_rows.size, pixel_cols.size). Got shapes {}, {}, and '
                '{}'.format(pixel_rows.shape, pixel_cols.shape, value_array.shape))

        # calculate pixel power, with noise subtracted if necessary
        if self._noise_poly is not None:
            noise = numpy.exp(10 * self._noise_poly(rows_meters, cols_meters))  # convert from db to power
            pixel_power = value_array*value_array - noise
            del noise
        else:
            pixel_power = value_array*value_array

        if self._rad_poly is None:
            return numpy.sqrt(pixel_power)
        else:
            return pixel_power*self._rad_poly(rows_meters, cols_meters)

    def _validate_row_col_values(self, row_array, col_array, value_array, value_is_flat=False):
        """
        Helper method for validating the types and shapes.

        Parameters
        ----------
        row_array : numpy.ndarray
            The rows of the pixel array. Must be one-dimensional, monotonically
            increasing, and have `row_array.size = value_array.shape[0]`.
        col_array : numpy.ndarray
            The columns of the pixel array. Must be one-dimensional, monotonically
            increasing, and have and have `col_array.size = value_array.shape[1]`.
        value_array : numpy.ndarray
            The values array, whihc must be two or three dimensional. If this has
            complex dtype and `complex_valued=False`, then the :func:`numpy.abs`
            will be applied.
        value_is_flat : bool
            If `True`, then `value_array` must be exactly two-dimensional.

        Returns
        -------
        numpy.ndarray
        """

        # verify numpy arrays
        if not isinstance(value_array, numpy.ndarray):
            raise TypeError('value_array must be numpy.ndarray, got type {}'.format(type(value_array)))
        if not isinstance(row_array, numpy.ndarray):
            raise TypeError('row_array must be numpy.ndarray, got type {}'.format(type(row_array)))
        if not isinstance(col_array, numpy.ndarray):
            raise TypeError('col_array must be numpy.ndarray, got type {}'.format(type(col_array)))

        # verify array shapes make sense
        if value_array.ndim not in (2, 3):
            raise ValueError('value_array must be two or three dimensional')
        if row_array.ndim != 1 or row_array.size != value_array.shape[0]:
            raise ValueError(
                'We must have row_array is one dimensional and row_array.size = value.array.shape[0]. '
                'Got row_array.shape = {}, and value_array = {}'.format(row_array.shape, value_array.shape))
        if col_array.ndim != 1 or col_array.size != value_array.shape[1]:
            raise ValueError(
                'We must have col_array is one dimensional and col_array.size = value.array.shape[1]. '
                'Got col_array.shape = {}, and value_array = {}'.format(col_array.shape, value_array.shape))
        if value_is_flat and len(value_array.shape) != 2:
            raise ValueError('value_array must be two-dimensional. Got shape {}'.format(value_array.shape))

        # verify row_array/col_array are monotonically increasing
        if numpy.any(numpy.diff(row_array.astype('float64')) <= 0):
            raise ValueError('row_array must be monotonically increasing.')
        if numpy.any(numpy.diff(col_array.astype('float64')) <= 0):
            raise ValueError('col_array must be monotonically increasing.')

        # address the dtype of value_array
        if (not self._complex_valued) and numpy.iscomplexobj(value_array):
            return numpy.abs(value_array)

        return value_array

    def get_orthorectified_from_array(self, ortho_bounds, row_array, col_array, value_array):
        """
        Construct the orthorectified array covering the orthorectified region given by
        `ortho_bounds` based on the `values_array`, which spans the pixel region defined by
        `row_array` and `col_array`.

        This is mainly a helper method, and should only be called directly for specific and
        directed reasons.

        Parameters
        ----------
        ortho_bounds : numpy.ndarray
            Determines the orthorectified bounds region, of the form
            `(min row, max row, min column, max column)`.
        row_array : numpy.ndarray
            The rows of the pixel array. Must be one-dimensional, monotonically increasing,
            and have `row_array.size = value_array.shape[0]`.
        col_array
            The columns of the pixel array. Must be one-dimensional, monotonically increasing,
            and have `col_array.size = value_array.shape[1]`.
        value_array
            The values array. If this has complex dtype and `complex_valued=False`, then
            the :func:`numpy.abs` will be applied.

        Returns
        -------
        numpy.ndarray
        """

        # validate our inputs
        value_array = self._validate_row_col_values(row_array, col_array, value_array, value_is_flat=False)
        if value_array.size == 0:
            if value_array.ndim == 3:
                return self._initialize_workspace(ortho_bounds, final_dimension=value_array.shape[2])
            else:
                return self._initialize_workspace(ortho_bounds)
        if value_array.ndim == 2:
            return self._get_orthrectified_from_array_flat(ortho_bounds, row_array, col_array, value_array)
        else:  # it must be three dimensional, as checked by _validate_row_col_values()
            ortho_array = self._initialize_workspace(ortho_bounds, final_dimension=value_array.shape[2])
            for i in range(value_array.shape[2]):
                ortho_array[:, :, i] = self._get_orthrectified_from_array_flat(
                    ortho_bounds, row_array, col_array, value_array[:, :, i])
            return ortho_array

    def get_orthorectified_for_ortho_bounds(self, bounds):
        """
        Determine the array corresponding to the array of bounds given in
        ortho-rectified pixel coordinates.

        Parameters
        ----------
        bounds : numpy.ndarray|list|tuple
            Of the form `(row_min, row_max, col_min, col_max)`. Note that non-integer
            values will be expanded outwards (floor of minimum and ceil at maximum).
            Following Python convention, this will be inclusive at the minimum and
            exclusive at the maximum.

        Returns
        -------
        numpy.ndarray
        """
        pass

    def get_orthorectified_for_pixel_bounds(self, pixel_bounds):
        """
        Determine the array corresponding to the given array bounds given in reader
        pixel coordinates.

        Parameters
        ----------
        pixel_bounds : numpy.ndarray|list|tuple
            Of the form `(row_min, row_max, col_min, col_max)`.

        Returns
        -------
        numpy.ndarray
        """
        pass

    def get_orthorectified_for_pixel_object(self, coordinates):
        """
        Determine the ortho-rectified rectangular array values, which will bound
        the given object - with coordinates expressed in pixel space.

        Parameters
        ----------
        coordinates : GeometryObject|numpy.ndarray|list|tuple
            The coordinate system of the input will be assumed to be pixel space.

        Returns
        -------
        numpy.ndarray
        """
        pass

    def get_orthorectified_for_latlon_object(self, ll_coordinates):
        """
        Determine the ortho-rectified rectangular array values, which will bound
        the given object - with coordinates expressed in lat/lon space.

        Parameters
        ----------
        ll_coordinates : GeometryObject|numpy.ndarray|list|tuple
            The coordinate system of the input will be assumed to be pixel space.
            **Note** a GeometryObject is expected to follow lon/lat ordering paradigm,
            by convention.

        Returns
        -------
        numpy.ndarray
        """
        pass

    def _setup_flat_workspace(self, ortho_bounds, row_array, col_array, value_array):
        """
        Helper method for setting up the flat workspace.

        Parameters
        ----------
        ortho_bounds : numpy.ndarray
            Determines the orthorectified bounds region, of the form
            `(min row, max row, min column, max column)`.
        row_array : numpy.ndarray
            The rows of the pixel array. Must be one-dimensional, monotonically
            increasing, and have `row_array.size = value_array.shape[0]`.
        col_array : numpy.ndarray
            The columns of the pixel array. Must be one-dimensional, monotonically
            increasing, and have `col_array.size = value_array.shape[1]`.
        value_array : numpy.ndarray
            The values array. If this has complex dtype and `complex_valued=False`,
            then the :func:`numpy.abs` will be applied.

        Returns
        -------
        (numpy.ndarray, numpy.ndarray, numpy.ndarray, numpy.ndarray)
        """

        value_array = self._validate_row_col_values(row_array, col_array, value_array, value_is_flat=True)
        # set up the results workspace
        ortho_array = self._initialize_workspace(ortho_bounds)
        # determine the pixel coordinates for the ortho coordinates meshgrid
        ortho_mesh = self._get_ortho_mesh(ortho_bounds)
        # determine the nearest neighbor pixel coordinates
        pixel_mesh = self.proj_helper.ortho_to_pixel(ortho_mesh)
        pixel_rows = pixel_mesh[:, :, 0]
        pixel_cols = pixel_mesh[:, :, 1]
        return value_array, pixel_rows, pixel_cols, ortho_array

    def _get_orthrectified_from_array_flat(self, ortho_bounds, row_array, col_array, value_array):
        """
        Construct the orthorecitified array covering the orthorectified region given by
        `ortho_bounds` based on the `values_array`, which spans the pixel region defined by
        `row_array` and `col_array`.

        Parameters
        ----------
        ortho_bounds : numpy.ndarray
            Determines the orthorectified bounds region, of the form
            `(min row, max row, min column, max column)`.
        row_array : numpy.ndarray
            The rows of the pixel array. Must be one-dimensional, monotonically
            increasing, and have `row_array.size = value_array.shape[0]`.
        col_array
            The columns of the pixel array. Must be one-dimensional, monotonically
            increasing, and have `col_array.size = value_array.shape[1]`.
        value_array
            The values array. If this has complex dtype and `complex_valued=False`,
            then the :func:`numpy.abs` will be applied.

        Returns
        -------
        numpy.ndarray
        """

        raise NotImplementedError


class NearestNeighborMethod(OrthorectificationHelper):
    """
    Nearest neighbor ortho-rectification method.

    .. warning::
        Modification of the proj_helper parameters when the default full image
        bounds have been defained (i.e. sicd.RadarCollection.Area is defined) may
        result in unintended results.
    """

    def __init__(self, reader, index=0, proj_helper=None, complex_valued=False,
                 pad_value=None, apply_radiometric=None, subtract_radiometric_noise=False):
        """

        Parameters
        ----------
        reader : SICDTypeReader
        index : int
        proj_helper : None|ProjectionHelper
            If `None`, this will default to `PGRatPolyProjection(<sicd>)` unless there is
            a SarpyRatPolyError, when it will fall back to `PGProjection(<sicd>)`,
            where `<sicd>` will be the sicd from `reader` at `index`. Otherwise,
            it is the user's responsibility to ensure that `reader`, `index` and
            `proj_helper` are in sync.
        complex_valued : bool
            Do we want complex values returned? If `False`, the magnitude values
            will be used.
        pad_value : None|Any
            Value to use for any out-of-range pixels. Defaults to `0` if not provided.
        apply_radiometric : None|str
            **Only valid if `complex_valued=False`**. If provided, must be one of
            `['RCS', 'Sigma0', 'Gamma0', 'Beta0']` (not case-sensitive). This will
            apply the given radiometric scale factor to the array values.
        subtract_radiometric_noise : bool
            **Only has any effect if `apply_radiometric` is provided.** This indicates that
            the radiometric noise should be subtracted prior to applying the given
            radiometric scale factor.
        """

        super(NearestNeighborMethod, self).__init__(
            reader, index=index, proj_helper=proj_helper, complex_valued=complex_valued,
            pad_value=pad_value, apply_radiometric=apply_radiometric,
            subtract_radiometric_noise=subtract_radiometric_noise)

    def _get_orthrectified_from_array_flat(self, ortho_bounds, row_array, col_array, value_array):
        # setup the result workspace
        value_array, pixel_rows, pixel_cols, ortho_array = self._setup_flat_workspace(
            ortho_bounds, row_array, col_array, value_array)
        # potentially apply the radiometric parameters to the value array
        value_array = self._apply_radiometric_params(row_array, col_array, value_array)
        if value_array.size > 0:
            # determine the in bounds points
            mask = self._get_mask(pixel_rows, pixel_cols, row_array, col_array)
            # determine the nearest neighbors for our row/column indices
            row_inds = numpy.digitize(pixel_rows[mask], row_array)
            col_inds = numpy.digitize(pixel_cols[mask], col_array)
            ortho_array[mask] = value_array[row_inds, col_inds]
        return ortho_array


class BivariateSplineMethod(OrthorectificationHelper):
    """
    Bivariate spline interpolation ortho-rectification method.

    .. warning::
        Modification of the proj_helper parameters when the default full image
        bounds have been defained (i.e. sicd.RadarCollection.Area is defined) may
        result in unintended results.
    """

    __slots__ = ('_row_order', '_col_order')

    def __init__(self, reader, index=0, proj_helper=None, complex_valued=False,
                 pad_value=None, apply_radiometric=None, subtract_radiometric_noise=False,
                 row_order=1, col_order=1):
        """

        Parameters
        ----------
        reader : SICDTypeReader
        index : int
        proj_helper : None|ProjectionHelper
            If `None`, this will default to `PGRatPolyProjection(<sicd>)` unless there is
            a SarpyRatPolyError, when it will fall back to `PGProjection(<sicd>)`,
            where `<sicd>` will be the sicd from `reader` at `index`. Otherwise,
            it is the user's responsibility to ensure that `reader`, `index` and
            `proj_helper` are in sync.
        complex_valued : bool
            Do we want complex values returned? If `False`, the magnitude values
            will be used.
        pad_value : None|Any
            Value to use for any out-of-range pixels. Defaults to `0` if not provided.
        apply_radiometric : None|str
            **Only valid if `complex_valued=False`**. If provided, must be one of
            `['RCS', 'Sigma0', 'Gamma0', 'Beta0']` (not case-sensitive). This will
            apply the given radiometric scale factor to the array values.
        subtract_radiometric_noise : bool
            **Only has any effect if `apply_radiometric` is provided.** This indicates that
            the radiometric noise should be subtracted prior to applying the given
            radiometric scale factor.
        row_order : int
            The row degree for the spline.
        col_order : int
            The column degree for the spline.
        """

        self._row_order = None
        self._col_order = None
        if complex_valued:
            raise ValueError('BivariateSpline only supports real valued results for now.')
        super(BivariateSplineMethod, self).__init__(
            reader, index=index, proj_helper=proj_helper, complex_valued=complex_valued,
            pad_value=pad_value, apply_radiometric=apply_radiometric,
            subtract_radiometric_noise=subtract_radiometric_noise)
        self.row_order = row_order
        self.col_order = col_order

    @property
    def row_order(self):
        """
        int : The spline order for the x/row coordinate, where `1 <= row_order <= 5`.
        """
        pass

    @row_order.setter
    def row_order(self, value):
        pass

    @property
    def col_order(self):
        """
        int : The spline order for the y/col coordinate, where `1 <= col_order <= 5`.
        """
        pass

    @col_order.setter
    def col_order(self, value):
        pass

    def _get_orthrectified_from_array_flat(self, ortho_bounds, row_array, col_array, value_array):
        # setup the result workspace
        value_array, pixel_rows, pixel_cols, ortho_array = self._setup_flat_workspace(
            ortho_bounds, row_array, col_array, value_array)
        value_array = self._apply_radiometric_params(row_array, col_array, value_array)

        if value_array.size > 0:
            # set up our spline
            sp = RectBivariateSpline(row_array, col_array, value_array, kx=self.row_order, ky=self.col_order, s=0)
            # determine the in bounds points
            mask = self._get_mask(pixel_rows, pixel_cols, row_array, col_array)
            result = sp.ev(pixel_rows[mask], pixel_cols[mask])
            # potentially apply the radiometric parameters
            ortho_array[mask] = result
        return ortho_array
