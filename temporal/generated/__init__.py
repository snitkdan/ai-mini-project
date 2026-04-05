# generated/__init__.py
from importlib import import_module
import sys

_mod = import_module(".greeter_pb2", package=__name__)
sys.modules.setdefault("greeter_pb2", _mod)