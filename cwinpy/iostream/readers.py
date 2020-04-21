import os

from gwpy.io import hdf5 as io_hdf5
from gwpy.io import registry as io_registry
from gwpy.io.utils import identify_factory
from gwpy.types.io.hdf5 import write_hdf5_series as gwpy_write_hdf5_series
from numpy import column_stack, loadtxt, savetxt

from ..data import HeterodynedData

# -- read ---------------------------------------------------------------------


def read_ascii_series(input_, array_type=HeterodynedData, **kwargs):
    """
    Read a `Series` from an ASCII text file.

    Parameters
    ----------
    input_: str, file
        The ascii text file to read
    array_type: type
        The desired return type. Defaults to :class:`cwinpy.data.HeterodynedData`.
    """

    data = loadtxt(input_, **kwargs)

    # get any comment lines from the file
    commentstrs = list(kwargs.get("comments", ["%", "#"]))  # delimiters
    comments = ""

    if input_.endswith(".gz"):
        import gzip

        openfunc = gzip.open
    else:
        openfunc = open

    with openfunc(input_, "r") as fp:
        for line in fp.readlines():
            firstchar = line.strip()[0]  # remove any proceeding whitespace
            if firstchar in commentstrs:
                # strip the comment delimiter and any leading whitespace
                comments += line.strip(firstchar).strip()

    if data.shape[1] < 2:
        raise IOError("Problem reading in data")

    return array_type(data[:, 1:], times=data[:, 0], comments=comments)


@io_hdf5.with_read_hdf5
def read_hdf5_series(
    source, array_type=HeterodynedData, path="HeterodynedData", **kwargs
):
    """
    Read a `Series` from an HDF5 file.

    Parameters
    ----------
    source: str
        The HDF5 file to be read.
    array_type: type
        The desired return type. Defaults to :class:`cwinpy.data.HeterodynedData`.
    """

    dataset = io_hdf5.find_dataset(source, path=path)
    kwargs = dict(dataset.attrs)

    parfiles = {}
    for par in ["par", "injpar"]:
        if par in kwargs:
            # convert parameter file string to file
            import tempfile

            parfiles[par] = tempfile.mkstemp(suffix=".par")[1]
            with open(parfiles[par], "w") as fp:
                fp.write(kwargs[par])
            kwargs[par] = parfiles[par]

    # make sure window is an integer
    if "window" in kwargs:
        kwargs["window"] = int(kwargs["window"])

    # complex time series data
    data = dataset[()]

    array = array_type(data, **kwargs)

    for par in ["par", "injpar"]:
        if par in parfiles:
            # remove temporary parameter file
            os.remove(parfiles[par])

    return array


# -- write --------------------------------------------------------------------


def write_ascii_series(series, output, **kwargs):
    """Write a `Series` to a file in ASCII format
    Parameters
    ----------
    series : :class:`~gwpy.data.Series`
        data series to write
    output : `str`, `file`
        file to write to
    See also
    --------
    numpy.savetxt
        for documentation of keyword arguments
    """

    xarr = series.xindex.value
    yarrr = series.value.real
    yarri = series.value.imag

    try:
        comments = series.comments
    except AttributeError:
        comments = ""

    return savetxt(
        output, column_stack((xarr, yarrr, yarri)), header=comments, **kwargs
    )


def write_hdf5_series(series, output, path="HeterodynedData", **kwargs):
    """Write a `Series` to a file in ASCII format
    Parameters
    ----------
    series : :class:`~gwpy.data.Series`
        data series to write
    output : `str`, `file`
        file to write to
    See also
    --------
    numpy.savetxt
        for documentation of keyword arguments
    """

    # set additional attributes to save
    attrs = kwargs.pop("attrs", {})

    if hasattr(series, "detector"):
        attrs["detector"] = series.detector

    for par in ["par", "injpar"]:
        import tempfile

        if hasattr(series, par):
            # output pulsar parameter data to temporary file
            # Note: a better option would be to add a __str__ method to the PulsarParametersPy object
            tempf = tempfile.mkstemp(suffix=".par")[1]
            series.par.pp_to_par(tempf)
            with open(tempf, "r") as fp:
                pardata = fp.readlines()
            os.remove(tempf)

            attrs[par] = "".join(pardata)

    # add times as extra attribute
    attrs["times"] = series.times

    # remove metadata slots that can't/shouldn't be written as attributes
    slots = tuple()
    origslots = tuple(series._metadata_slots)
    for slot in series._metadata_slots:
        if slot not in ["par", "injpar", "laldetector", "running_median", "vars"]:
            slots += (slot,)
    series._metadata_slots = slots

    outseries = gwpy_write_hdf5_series(series, output, path=path, attrs=attrs, **kwargs)
    series._metadata_slots = origslots

    return outseries


# -- register -----------------------------------------------------------------


def register_ascii_series_io(array_type, format="txt", identify=True, **defaults):
    """
    Register ASCII read/write/identify methods for the given array
    """

    def _read(filepath, **kwargs):
        kwgs = defaults.copy()
        kwgs.update(kwargs)
        if "comments" not in kwgs:
            kwgs.update({"comments": ["%", "#"]})
        return read_ascii_series(filepath, array_type=array_type, **kwgs)

    def _write(series, output, **kwargs):
        kwgs = defaults.copy()
        kwgs.update(kwargs)
        return write_ascii_series(series, output, **kwgs)

    io_registry.register_reader(format, array_type, _read)
    io_registry.register_writer(format, array_type, _write)
    if identify:
        io_registry.register_identifier(format, array_type, identify_factory(format))


def register_hdf_series_io(array_type, format="hdf5", identify=True, **defaults):
    """
    Register HDF5 read/write/identify methods for the given array
    """

    def _read(filepath, **kwargs):
        kwgs = defaults.copy()
        kwgs.update(kwargs)
        if "comments" not in kwgs:
            kwgs.update({"comments": ["%", "#"]})
        return read_hdf5_series(filepath, array_type=array_type, **kwgs)

    def _write(series, output, **kwargs):
        kwgs = defaults.copy()
        kwgs.update(kwargs)
        return write_hdf5_series(series, output, **kwgs)

    io_registry.register_reader(format, array_type, _read)
    io_registry.register_writer(format, array_type, _write)
    if identify:
        io_registry.register_identifier(format, array_type, identify_factory(format))
