"""
Configuration.

Classes for parsing configuration files and command line arguments.

wishlist:
- config auto loaded from static locations on disk like:
    - ROOT: /etc/xmg/
    - USER: ~/.xmg.json
    - LOCAL: ./.xmg.json
- local override with --config-file cli arg

"""

import logging
import os
import pprint
import re
from builtins import super
import argparse
from copy import copy

from six import integer_types, string_types, text_type
from traitlets import (Any, Bool, Float, Integer, List, TraitType, Type,
                       Unicode, Union, getmembers, validate)
from traitlets.config.configurable import Configurable
from traitlets.config.loader import (ArgumentError, Config, ConfigFileNotFound,
                                     JSONFileConfigLoader,
                                     KVArgParseConfigLoader, LazyConfigValue,
                                     PyFileConfigLoader)


from helper import TraitValidation, expand_relative_path
from log import PKG_LOGGER, ROOT_LOGGER, log_level_quiet, setup_logging
from rich_traitlets import RichConfigurable, RichKVArgParseConfigLoader, RichConfig

# from . import DESCRIPTION , PKG_NAME
DESCRIPTION = "Generates a Google Maps import file from a Contact Group in Xero"
PKG_NAME = os.path.basename(os.path.dirname(__file__))
class ConfigException(UserWarning):
    pass

class XeroApiConfig(RichConfigurable):
    rsa_key_path = Unicode(
        help='The path to the Xero API RSA key file',
        switch="xero-key-path", metavar='PATH'
    )
    consumer_key = Unicode(
        help='The Xero API Consumer Key',
        switch="xero-consumer-key", metavar='KEY'
    )

    @validate('rsa_key_path')
    def _valid_rsa_key_path(self, proposal):
        TraitValidation.path_exists(proposal['rsa_key_path'])
        return proposal['rsa_key_path']

    @validate('consumer_key')
    def _valid_consumer_key(self, proposal):
        TraitValidation.not_falsey(
            proposal['consumer_key'],
            "%s.%s" % (self.__class__, 'consumer_key')
        )

class LogConfig(RichConfigurable):
    stream_log_level = Unicode(
        "WARNING",
        help="Set custom message output level",
        switch="verbosity", metavar='LEVEL'
    )
    file_log_level = Unicode(
        "DEBUG",
        help=argparse.SUPPRESS,
        metavar='LEVEL'
    )
    log_dir = Unicode(
        help="Directory containing log files",
        metavar='PATH'
    )
    log_path = Unicode(
        '%s.log' % PKG_NAME,
        help=argparse.SUPPRESS,
        metavar='PATH'
    )

class BaseConfig(RichConfigurable):
    contact_limit = Integer(
        help="Limit the number of contacts downloaded from the API",
        metavar='LIMIT'
    )

    config_dir = Unicode(
        help="Directory containing config files",
        metavar="PATH"
    )

    config_path = Unicode(
        help="Load extra config from file relative to config_dir if provided",
        metavar='PATH'
    )

    data_dir = Unicode(
        help="Directory to dump data",
        metavar='PATH'
    )

    dump_path = Unicode(
        default_value="contacts.csv",
        help="Location where CSV data is dumped relative to data_dir if provided",
        metavar='PATH'
    )

class FilterConfig(RichConfigurable):
    contact_groups = Unicode(
        help="Filter by Xero contact group names separated by '|'",
        switch="filter-contact-groups", metavar='"GROUP1|GROUP2"'
    )

    states = Unicode(
        help="Filter by main address state. Separate states with '|'",
        switch="filter-states", metavar='"STATE1|STATE2"'
    )

    countries = Unicode(
        help="Filter by main address country. Separate countries with '|'",
        switch="filter-countries", metavar='"COUNTRY1|COUNTRY2"'
    )

def get_argparse_loader():
    # TODO: argparse loader args
    aliases = {}
    for config_class in [
        XeroApiConfig,
        LogConfig,
        BaseConfig,
        FilterConfig,
    ]:
        aliases.update(config_class.trait_argparse_aliases())
    return RichKVArgParseConfigLoader(
        # TODO: generate alias argparse data from Configurable object directly
        aliases=aliases,
        flags={
            'debug': {
                'value': ({'LogConfig': {'stream_log_level':'DEBUG'}}, 'display debug messages'),
                'add_args': ['-d', '--debug'],
                'section': 'logging',
            },
            'verbose': {
                'value': ({'LogConfig': {'stream_log_level':'INFO'}}, 'display extra information messages'),
                'add_args': ['-v', '--verbose'],
                'section': 'logging',
            },
            'quiet': {
                'value': ({'LogConfig': {'stream_log_level':'ERROR'}}, 'suppress warning messages'),
                'add_args': ['-q', '--quiet'],
                'section': 'logging',
            },
        },
        description=DESCRIPTION,
    )

def config_quiet(config):
    return log_level_quiet(config.LogConfig.get('stream_log_level', logging.WARNING))

def config_runtime_exception(exc, config):
    print(exc.args[0])
    ROOT_LOGGER.critical(exc.args[0])
    if not config_quiet(config) and 'argparse_loader' in config:
        config.argparse_loader.parser.print_usage()
    exit()

def load_cli_config(argv=None, config=None):
    if config is None:
        config = Config()
    config.argparse_loader = get_argparse_loader()
    try:
        cli_config = config.argparse_loader.load_config(argv)
    except ArgumentError as exc:
        config_runtime_exception(exc, config)
    setup_logging(**cli_config.LogConfig)
    ROOT_LOGGER.info("cli config is \n%s", pprint.pformat(cli_config))
    return cli_config

def load_single_file_config(config_path, config):
    extension_loaders = {
        '.py': PyFileConfigLoader,
        '.json': JSONFileConfigLoader
    }
    _, extension = os.path.splitext(config_path)
    loader_class = extension_loaders.get(extension, None)
    if not loader_class:
        raise ConfigException(
            "invalid config file extension (must be in %s) in file %s" % (
                str(extension_loaders.keys()),
                config_path
            )
        )
    loader = loader_class(config_path, path=config_path)
    return loader.load_config()

def validate_config_path(config_path, config=None):
    """
    Return an expanded config path relative to config_dir if provided in config.BaseConfig
    """
    if not config_path:
        return
    if config is None:
        config = Config()
    config_dir = config.BaseConfig.get('config_dir')
    config_path = expand_relative_path(config_path, config_dir)
    if not os.path.exists(config_path):
        raise ConfigFileNotFound(
            "config_path %s does not exist under config_dir %s" % (
                config_path, config_dir
            )
        )
    return config_path

def load_file_config(config=None):
    if config is None:
        config = Config()
    file_config = Config()
    return file_config

def validate_config(config):
    pass


def load_config(argv=None, proto_config=None):
    """
    Successively merge config files from different sources, overriding the previous.

    Config merge order:
    - proto config          (config provided initially to load_config)
    - local config          (config file specified after analysing proto and cli config)
    - cli config            (command line arguments)
    """
    if proto_config is None:
        proto_config = Config()
    config = RichConfig()
    config.merge_source('proto', proto_config)
    setup_logging(**config.LogConfig)
    cli_config = load_cli_config(argv, config)
    for trait, group in [
        ('config_path', 'BaseConfig'),
        ('config_dir', 'BaseConfig'),
        ('stream_log_level', 'LogConfig')
    ]:
        if trait in getattr(cli_config, group):
            setattr(
                getattr(config, group), trait,
                getattr(getattr(cli_config, group), trait)
            )
    # if 'config_dir' in cli_config.BaseConfig:
    #     config.BaseConfig.config_dir = cli_config.BaseConfig.config_dir
    # if 'stream_log_level' in cli_config.LogConfig:
    #     config.LogConfig.stream_log_level = cli_config.LogConfig.stream_log_level
    # TODO: replace this wiht custom traitlet subclass "immediate" where settings are applied as soon as they are loaded
    # TODO: implement partial merge like this
    # config.partial_merge(
    #     cli_config, [
    #         ('BaseConfig', ['config_path', 'config_dir']),
    #         ('LogConfig', ['stream_log_level']),
    #     ]
    # )
    file_config = load_file_config(config)
    config.merge_source('file', file_config)
    config.merge_source('cli', cli_config)
    try:
        validate_config(config)
    except ConfigException as exc:
        config_runtime_exception(exc, config)
    if not config_quiet(config):
        ROOT_LOGGER.info("config is \n%s", pprint.pformat(config))
    return config
