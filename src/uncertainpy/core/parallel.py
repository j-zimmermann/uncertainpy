import traceback
import warnings

import numpy as np
import scipy.interpolate as scpi

from .base import Base
from ..utils.utility import none_to_nan, contains_none_or_nan, is_regular

class Parallel(Base):
    """
    Calculates the model and features of the model for one set of
    model parameters. Is the class that is run in parallel.

    Parameters
    ----------
    model : {None, Model or Model subclass instance, model function}, optional
        Model to perform uncertainty quantification on. For requirements see
        Model.run.
        Default is None.
    features : {None, Features or Features subclass instance, list of feature functions}, optional
        Features to calculate from the model result.
        If None, no features are calculated.
        If list of feature functions, all will be calculated.
        Default is None.
    verbose_level : {"info", "debug", "warning", "error", "critical"}, optional
        Set the threshold for the logging level.
        Logging messages less severe than this level is ignored.
        Default is `"info"`.
    verbose_filename : {None, str}, optional
        Sets logging to a file with name `verbose_filename`.
        No logging to screen if a filename is given.
        Default is None.

    Attributes
    ----------
    model : uncertainpy.Parallel.model
    features : uncertainpy.Parallel.features
    logger : logging.Logger
        Logger object responsible for logging to screen or file.

    See Also
    --------
    uncertainpy.features.Features
    uncertainpy.models.Model
    uncertainpy.models.Model.run : Requirements for the model run function.
    """
    def create_interpolations(self, result):
        """
        Create an interpolation for adaptive model and features `result`.

        Adaptive model or feature `result`, meaning they have a varying number
        of time steps, are interpolated. Interpolation is only performed for one
        dimensional `result`. Zero dimensional `result` does not need to be
        interpolated, and support for interpolating two dimensional and above
        `result` have currently not been implemented.
        Adds a `"interpolation"` key-value pair to `result`.

        Parameters
        ----------
        result : dict
            The model and feature results. The model and each feature each has
            a dictionary with the time values, ``"time"``,  and model/feature
            results, ``"values"``.
            An example:

            .. code-block:: Python

                result = {model.name: {"values": array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
                                       "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature1d": {"values": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
                                        "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature0d": {"values": 1,
                                        "time": np.nan},
                          "feature2d": {"values": array([[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                                                         [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]]),
                                        "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature_adaptive": {"values": array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
                                               "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature_invalid": {"values": np.nan,
                                              "time": np.nan}}

        Returns
        -------
        result : dict
            If an interpolation has been created, those features/model have
            "interpolation" and the corresponding interpolation object added to
            each features/model dictionary.
            An example:

            .. code-block:: Python

                result = {self.model.name: {"values": array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
                                            "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature1d": {"values": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
                                        "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature0d": {"values": 1,
                                        "time": np.nan},
                          "feature2d": {"values": array([[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                                                    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]]),
                                        "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature_adaptive": {"values": array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
                                               "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
                                              "interpolation": scipy interpolation object},
                          "feature_invalid": {"values": np.nan,
                                              "time": np.nan}}


        Notes
        -----
        If either model or feature results are adaptive, the results must be
        interpolated for Chaospy to be able to create the polynomial
        approximation. For 1D results this is done with scipy:
        ``InterpolatedUnivariateSpline(time, U, k=3)``.
        """
        for feature in result:
            if feature in self.features.adaptive or \
                (feature == self.model.name and self.model.adaptive and not self.model.ignore):

                # TODO: Find out how many tests should be performed on the
                # results here.
                # Find out how a model result should be validated.

                if not is_regular(result[feature]["values"]):
                     raise ValueError("{}: values within one evaluation is irregular,".format(feature) +
                                      " unable to perform interpolation.")

                if not is_regular(result[feature]["time"]):
                    raise ValueError("{}: times within one evaluation is irregular,".format(feature) +
                                     " unable to perform interpolation.")


                if np.ndim(result[feature]["values"]) == 0:
                        # raise AttributeError("{} is 0D,".format(feature)
                        #                     + " interpolation makes no sense.")
                        self.logger.warning("{feature} ".format(feature=feature) +
                                            "gives a 0D result. No interpolation performed")


                elif np.ndim(result[feature]["values"]) == 1:
                    result[feature]["interpolation"] = self.interpolation_1d(result, feature)



                elif np.ndim(result[feature]["values"]) >= 2:
                    # TODO implement interpolation of >= 2d data, part 1
                    raise NotImplementedError("{feature}: ".format(feature=feature)
                                            + " no support for >= 2D interpolation")

        return result


    def interpolation_1d(self, result, feature):
        """
        Create an interpolation for an 1D result.

        Parameters
        ----------
        result : dict
            The model and feature results. The model and each feature each has
            a dictionary with the time values, ``"time"``,  and model/feature
            results, ``"values"``.
            An example:

            .. code-block:: Python

                result = {model.name: {"values": array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
                                       "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature1d": {"values": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
                                        "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature0d": {"values": 1,
                                        "time": np.nan},
                          "feature2d": {"values": array([[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                                                         [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]]),
                                        "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature_adaptive": {"values": array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
                                               "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature_invalid": {"values": np.nan,
                                              "time": np.nan}}

        Returns
        -------
        interpolation : {scipy.interpolate.fitpack2.InterpolatedUnivariateSpline, None}
            The result of the interpolation. If either the time or values contain
            None or numpy.nan, None is returned.

        Raises
        ------
        ValueError
            If the values of the feature are not 1D.
        ValueError
            If the time of the feature is not 1D.


        Notes
        -----
        The interpolation is performed using scipy:
        ``InterpolatedUnivariateSpline(time, values, k=3)``.
        """
        if np.ndim(result[feature]["values"]) != 1:
            raise ValueError("Cannot create 1D interpolation as the values of {} are not 1D".format(feature))

        if np.ndim(result[feature]["time"]) != 1:
            raise ValueError("Cannot create 1D interpolation as the time of {} is not 1D".format(feature))


        interpolation = None

        if contains_none_or_nan(result[feature]["values"]):
            interpolation = None
            msg = "{} values contains np.nan or None values, unable to perform interpolation.".format(feature)
            self.logger.warning(msg)
            # raise ValueError(msg)

        elif contains_none_or_nan(result[feature]["time"]):
            interpolation = None
            msg = "{}: time contains np.nan or None values, unable to perform interpolation.".format(feature)
            self.logger.warning(msg)
            # raise ValueError(msg)

        else:
            try:
                interpolation = scpi.InterpolatedUnivariateSpline(result[feature]["time"],
                                                                  result[feature]["values"],
                                                                  k=3)
            except Exception as error:
                msg = "{}: unable to interpolate using scipy.interpolate.InterpolatedUnivariateSpline(time, values, k=3)".format(feature)
                if not error.args:
                    error.args = ("",)
                error.args = error.args + (msg,)
                raise

        return interpolation




    def run(self, model_parameters):
        """
        Run a model and calculate features from the model output,
        return the results.

        The model is run and each feature of the model is calculated from the model output,
        `time` (time values) and `values` (model result).
        The results are interpolated if they are adaptive, meaning they return a varying number of steps,
        An interpolation is created and added to results for the model/features that are adaptive.
        Each instance of None is converted to an
        array of ``numpy.nan`` of the correct shape, which makes the array regular.

        Parameters
        ----------
        model_parameters : dictionary
            All model parameters as a dictionary.
            These parameters are sent to model.run().

        Returns
        -------
        result : dictionary
            The model and feature results. The model and each feature each has
            a dictionary with the time values, ``"time"``,  and model/feature results, ``"values"``.
            If an interpolation has been created, those features/model also has
            ``"interpolation"`` added. An example:

            .. code-block:: Python

                result = {self.model.name: {"values": array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
                                            "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature1d": {"values": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
                                        "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature0d": {"values": 1,
                                        "time": np.nan},
                          "feature2d": {"values": array([[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                                                         [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]]),
                                        "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])},
                          "feature_adaptive": {"values": array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
                                               "time": array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
                                               "interpolation": scipy interpolation object},
                          "feature_invalid": {"values": np.nan,
                                              "time": np.nan}}

        Notes
        -----
        Time `time` and result `values` are calculated from the model. Then sent to
        model.postprocess, and the postprocessed result from model.postprocess
        is added to result.
        `time` and `values` are sent to features.preprocess and the preprocessed results
        is used to calculate each feature.

        See also
        --------
        uncertainpy.utils.utility.none_to_nan : Method for converting from None to NaN
        uncertainpy.features.Features.preprocess : preprocessing model results before features are calculated
        uncertainpy.models.Model.postprocess : posteprocessing of model results
        """
        # Try-except to catch exceptions and print stack trace
        try:
            model_result = self.model.run(**model_parameters)

            self.model.validate_run_result(model_result)

            results = {}


            postprocess_result = self.model.postprocess(*model_result)

            try:
                time_postprocess, values_postprocess = postprocess_result
            except (ValueError, TypeError) as error:
                msg = "model.postprocess() must return time and values (return time, values | return None, values)"
                if not error.args:
                    error.args = ("",)
                error.args = error.args + (msg,)
                raise

            values_postprocess = none_to_nan(values_postprocess)
            time_postprocess = none_to_nan(time_postprocess)

            results[self.model.name] = {"time": time_postprocess,
                                        "values": values_postprocess}


            # Calculate features from the model results
            feature_preprocess = self.features.preprocess(*model_result)
            feature_results = self.features.calculate_features(*feature_preprocess)

            for feature in feature_results:
                time_feature = feature_results[feature]["time"]
                values_feature = feature_results[feature]["values"]

                time_feature = none_to_nan(time_feature)
                values_feature = none_to_nan(values_feature)

                results[feature] = {"values": values_feature,
                                    "time": time_feature}

            # Create interpolations
            results = self.create_interpolations(results)

            return results


        except Exception as error:
            print("Caught exception in parallel run of model:")
            print("")
            traceback.print_exc()
            print("")
            raise error


