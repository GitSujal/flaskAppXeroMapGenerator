import csv
import os
from copy import copy

from traitlets import TraitError

from six import b, binary_type, byte2int, iterbytes, text_type, u, unichr


class TraitValidation(object):
    @classmethod
    def path_exists(cls, path, name=None):
        if not os.path.exists(path):
            raise TraitError('%spath %s does not exist' % (
                (' %s' % name) if name else "",
                path
            ))

    @classmethod
    def not_none(cls, value, name=None):
        if value is None:
            raise TraitError('value %sis None' % (
                (" %s" % name) if name else "")
            )

    @classmethod
    def not_falsey(cls, value, name=None):
        if not value:
            raise TraitError('value %sis empty' % (
                (" %s" % name) if name else "")
            )

def expand_relative_path(path, dir):
    path = os.path.expandvars(path)
    path = os.path.normpath(path)
    path = os.path.expanduser(path)
    if not path.startswith('/') and dir:
        dir = os.path.expandvars(dir)
        dir = os.path.normpath(dir)
        dir = os.path.expanduser(dir)
        path = os.path.join(dir, path)
    return os.path.abspath(path)

class SanitationUtils(object):
    @classmethod
    def to_ascii(cls, thing, errors=None):
        """Take a stringable object of any type, returns a safe ASCII byte str."""
        if errors is None:
            errors = 'backslashreplace'
        if isinstance(thing, binary_type):
            thing = u"".join([
                (unichr(c) if (c in range(0x7f)) else "\\x%02x" % (c,))\
                for c in iterbytes(thing)
            ])
            # thing = thing.decode('ascii', errors=errors)
        elif not isinstance(thing, text_type):
            thing = text_type(thing)
        return thing.encode('ascii', errors=errors).decode('ascii')
