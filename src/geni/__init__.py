from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("geni")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
