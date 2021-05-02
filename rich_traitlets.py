
import re
from copy import copy
from six import text_type
from traitlets import (Any, Bool, Float, Integer, List, TraitType, Type,
                       Unicode, Union, getmembers, validate)
from traitlets.config.configurable import Configurable
from traitlets.config.loader import (ArgumentError, Config, ConfigFileNotFound,
                                     JSONFileConfigLoader,
                                     KVArgParseConfigLoader, LazyConfigValue,
                                     PyFileConfigLoader)
from builtins import super

class RichKVArgParseConfigLoader(KVArgParseConfigLoader):
    """ Extension of KVArgParseConfigLoader to handle complex argument parsing. """

    def __init__(self, aliases=None, flags=None, *super_args, **super_kwargs):
        """
        Create Rich KVArgParseConfigLoader object.

        Parameters
        ----------
        aliases : dict
            A dict of aliases for configurable traits.
            Keys are the short aliases, Values are a dict which contains the
            resolved trait and any extra arguments that should be passed to
            `argparse.add_argument`.
            Of the form:
            ```python
            {
                'alias' : {
                    'trait': 'Configurable.trait'
                    'add_args': ['extra_arguments'],
                    'add_kwargs': {
                        'keyword': 'extra_keyword_argument',
                    }
                }
            }`
            ```
        flags : dict
            A dict of flags, keyed by str name. Values are a dict which contains
            the flag value, and any extra arguments that should be passed to
            `argparse.add_argument`. The flag values can be Config objects,
            dicts, or "key=value" strings.  If Config or dict, when the flag
            is triggered, The flag is loaded as `self.config.update(m)`.
            Of the form:
            ```python
            {
                'flag' : {
                    'value': Config(trait='trait_value'),
                    'add_args': ['extra_arguments'],
                    'add_kwargs': {
                        'keyword': 'extra_keyword_argument',
                    }
                }
            }
            ```
        """
        def process_super_extensions(things, name_singular, value_key):
            setattr(self, "%s_extensions" % name_singular, {})
            if not things:
                return
            super_things = {}
            for thing, values in things.items():
                assert value_key in values, "%s values must contain a %s" % (
                    name_singular, value_key
                )
                super_things[thing] = values.pop(value_key)
                if values:
                    getattr(self, "%s_extensions" % name_singular)[thing] = values
            return super_things

        super_kwargs.update(
            aliases=process_super_extensions(aliases, 'alias', 'trait'),
            flags=process_super_extensions(flags, 'flag', 'value')
        )

        super().__init__(*super_args, **super_kwargs)

    def _get_add_args_kwargs(self, thing_extensions, key, default_add_kwargs):
        add_args = thing_extensions.get(key, {}).get('add_args', [])
        if not add_args:
            add_args = ['-'+key] if len(key) is 1 else ['--'+key]
        add_kwargs = copy(default_add_kwargs)
        add_kwargs.update(
            thing_extensions.get(key, {}).get('add_kwargs', {})
        )
        return add_args, add_kwargs

    def _add_alias_arguments(self, aliases, flags):
        for key,value in aliases.items():
            default_add_kwargs = {
                'dest': value,
                'type': text_type
            }
            add_args, add_kwargs = self._get_add_args_kwargs(
                self.alias_extensions, key, default_add_kwargs
            )
            if key in flags:
                # flags
                add_kwargs['nargs'] = '?'
            self.parser.add_argument(*add_args, **add_kwargs)

    def _add_flag_arguments(self, flags):
        for key, (value, help) in flags.items():
            if key in self.aliases:
                #
                self.alias_flags[self.aliases[key]] = value
                continue
            default_add_kwargs = {
                'dest': '_flags',
                'action': 'append_const',
                'const': value,
                'help': help
            }
            add_args, add_kwargs = self._get_add_args_kwargs(
                self.flag_extensions, key, default_add_kwargs
            )
            self.parser.add_argument(*add_args, **add_kwargs)

    def _add_arguments(self, aliases=None, flags=None):
        """ Override _add_arguments with alias and flag extensions. """
        self.alias_flags = {}

        if aliases is None:
            aliases = self.aliases
        if flags is None:
            flags = self.flags
        self._add_alias_arguments(aliases, flags)
        self._add_flag_arguments(flags)


class RichConfigurable(Configurable):
    # TODO: extra methods for auto generating add_args
    @classmethod
    def trait_argparse_aliases(cls):
        traits = dict([memb for memb in getmembers(cls) if
                     isinstance(memb[1], TraitType)])
        aliases = {}
        for key, trait_obj in traits.items():
            if key in ['config', 'parent']:
                continue
            alias_dict = {}
            trait_meta = copy(trait_obj.metadata)
            alias_key = trait_meta.pop('switch', re.sub('_', '-', key))
            alias_dict['add_kwargs'] = trait_meta
            # if hasattr(trait_obj, 'default_value'):
            if trait_obj.default_value != '':
                alias_dict['add_kwargs'].update({
                    'default':text_type(trait_obj.default_value)
                })
            alias_dict['trait'] = "%s.%s" % (cls.__name__, key)
            alias_dict['section'] = cls.__name__.lower()

            aliases[alias_key] = alias_dict
        return aliases

class RichConfig(Config):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sources = {}

    def merge_source(self, name, other):
        self._sources[name] = other
        self.merge(other)
