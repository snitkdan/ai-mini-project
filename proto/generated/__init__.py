import importlib
import sys

# The generated gemini_echo_pb2_grpc.py contains:
#   import gemini_echo_pb2
# instead of:
#   from . import gemini_echo_pb2
#
# We load the pb2 module via its fully-qualified package path and register it
# under its bare name so that broken import resolves at runtime.
_pb2 = importlib.import_module(".gemini_echo_pb2", package=__name__)
sys.modules.setdefault("gemini_echo_pb2", _pb2)