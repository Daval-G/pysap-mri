# -*- coding: utf-8 -*-
##########################################################################
# pySAP - Copyright (C) CEA, 2017 - 2018
# Distributed under the terms of the CeCILL-B license, as published by
# the CEA-CNRS-INRIA. Refer to the LICENSE file or to
# http://www.cecill.info/licences/Licence_CeCILL-B_V1-en.html
# for details.
##########################################################################

"""
This module contains linears operators classes.
"""


# Package import
import pysap
from pysap.base.utils import flatten
from pysap.base.utils import unflatten

# Third party import
import numpy as np
from modopt.signal.wavelet import get_mr_filters, filter_convolve

class WaveletN(object):
    """ The 2D and 3D wavelet transform class.
    """

    def __init__(self, wavelet_name, nb_scale=4, verbose=0, dim=2, **kwargs):
        """ Initialize the 'WaveletN' class.

        Parameters
        ----------
        wavelet_name: str
            the wavelet name to be used during the decomposition.
        nb_scales: int, default 4
            the number of scales in the decomposition.
        verbose: int, default 0
            the verbosity level.
        """
        self.nb_scale = nb_scale
        self.flatten = flatten
        self.unflatten = unflatten
        if wavelet_name not in pysap.AVAILABLE_TRANSFORMS:
            raise ValueError(
                "Unknown transformation '{0}'.".format(wavelet_name))
        transform_klass = pysap.load_transform(wavelet_name)
        self.transform = transform_klass(
            nb_scale=self.nb_scale, verbose=verbose, dim=dim, **kwargs)
        self.coeffs_shape = None

    def get_coeff(self):
        return self.transform.analysis_data

    def set_coeff(self, coeffs):
        self.transform.analysis_data = coeffs

    def op(self, data):
        """ Define the wavelet operator.

        This method returns the input data convolved with the wavelet filter.

        Parameters
        ----------
        data: ndarray or Image
            input 2D data array.

        Returns
        -------
        coeffs: ndarray
            the wavelet coefficients.
        """
        if isinstance(data, np.ndarray):
            data = pysap.Image(data=data)
        self.transform.data = data
        self.transform.analysis()
        coeffs, self.coeffs_shape = flatten(self.transform.analysis_data)
        return coeffs

    def adj_op(self, coeffs, dtype="array"):
        """ Define the wavelet adjoint operator.

        This method returns the reconsructed image.

        Parameters
        ----------
        coeffs: ndarray
            the wavelet coefficients.
        dtype: str, default 'array'
            if 'array' return the data as a ndarray, otherwise return a
            pysap.Image.

        Returns
        -------
        data: ndarray
            the reconstructed data.
        """
        self.transform.analysis_data = unflatten(coeffs, self.coeffs_shape)
        image = self.transform.synthesis()
        if dtype == "array":
            return image.data
        return image

    def l2norm(self, shape):
        """ Compute the L2 norm.

        Parameters
        ----------
        shape: uplet
            the data shape.

        Returns
        -------
        norm: float
            the L2 norm.
        """
        # Create fake data
        shape = np.asarray(shape)
        shape += shape % 2
        fake_data = np.zeros(shape)
        fake_data[tuple(zip(shape // 2))] = 1

        # Call mr_transform
        data = self.op(fake_data)

        # Compute the L2 norm
        return np.linalg.norm(data)


class WaveletUD2(object):
    """The wavelet undecimated operator using pysap wrapper.
    """
    def __init__(self, wavelet_id, nb_scale=4, verbose=0, multichannel=False):
        """Init function for Undecimated wavelet transform

        Parameters
        -----------
        wavelet_id: int
            ID of wavelet being used
        nb_scale: int, default 4
            the number of scales in the decomposition.

        Private Variables:
            _has_run: Checks if the get_mr_filters was called already
        """
        self.wavelet_id = wavelet_id
        self.multichannel = multichannel
        self.nb_scale = nb_scale
        self._opt = [
            '-t{}'.format(self.wavelet_id),
            '-n{}'.format(self.nb_scale),
        ]
        self._has_run = False
        self.coeffs_shape = None
        self.flatten = flatten
        self.unflatten = unflatten

    def _get_filters(self, shape):
        """Function to get the Wavelet coefficients of Delta[0][0].
        This function is called only once and later the
        wavelet coefficients are obtained by convolving these coefficients
        with input Data
        """
        self.transform = get_mr_filters(
            tuple(shape),
            opt=self._opt,
            coarse=True,
        )
        self._has_run = True

    def op(self, data):
        """ Define the wavelet operator.

        This method returns the input data convolved with the wavelet filter.

        Parameters
        ----------
        data: ndarray or Image
            input 2D data array.

        Returns
        -------
        coeffs: ndarray
            the wavelet coefficients.
        """
        if not self._has_run:
            if self.multichannel:
                self._get_filters(list(data.shape)[1:])
            else:
                self._get_filters(data.shape)
        if self.multichannel:
            coeffs = []
            self.coeffs_shape = []
            for channel in range(data.shape[0]):
                coefs_real, coeffs_shape = self.flatten(
                    filter_convolve(data[channel].real, self.transform))
                coefs_imag, coeffs_shape = self.flatten(
                    filter_convolve(data[channel].imag, self.transform))
                coeffs.append(coefs_real + 1j * coefs_imag)
                self.coeffs_shape.append(coeffs_shape)
            return np.asarray(coeffs)
        else:
            coefs_real = filter_convolve(data.real, self.transform)
            coefs_imag = filter_convolve(data.imag, self.transform)
            coeffs, self.coeffs_shape = self.flatten(
                coefs_real + 1j * coefs_imag)
        return coeffs

    def adj_op(self, coefs):
        """ Define the wavelet adjoint operator.

        This method returns the reconsructed image.

        Parameters
        ----------
        coeffs: ndarray
            the wavelet coefficients.
        dtype: str, default 'array'
            if 'array' return the data as a ndarray, otherwise return a
            pysap.Image.

        Returns
        -------
        data: ndarray
            the reconstructed data.
        """
        if not self._has_run:
            raise RuntimeError(
                "`op` must be run before `adj_op` to get the data shape",
            )
        if self.multichannel:
            images = []
            for channel, coeffs_shape in zip(range(coefs.shape[0]),
                                             self.coeffs_shape):
                data_real = filter_convolve(
                    np.squeeze(self.unflatten(coefs.real[channel],
                                              coeffs_shape)),
                    self.transform, filter_rot=True)
                data_imag = filter_convolve(
                    np.squeeze(self.unflatten(coefs.imag[channel],
                                              coeffs_shape)),
                    self.transform, filter_rot=True)
                images.append(data_real + 1j * data_imag)
            return np.asarray(images)
        else:
            data_real = filter_convolve(
                np.squeeze(self.unflatten(coefs.real, self.coeffs_shape)),
                self.transform, filter_rot=True)
            data_imag = filter_convolve(
                np.squeeze(self.unflatten(coefs.imag, self.coeffs_shape)),
                self.transform, filter_rot=True)
        return data_real + 1j * data_imag

    def l2norm(self, shape):
        """ Compute the L2 norm.
        Parameters
        ----------
        shape: uplet
            the data shape.
        Returns
        -------
        norm: float
            the L2 norm.
        """
        # Create fake data
        shape = np.asarray(shape)
        shape += shape % 2
        fake_data = np.zeros(shape)
        fake_data[tuple(zip(shape // 2))] = 1

        # Call mr_transform
        data = self.op(fake_data)

        # Compute the L2 norm
        return np.linalg.norm(data)
