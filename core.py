import os
import pprint
import sys

from config import load_config
from transport import XeroApiWrapper
from log import setup_logging, PKG_LOGGER
from contain import XeroContactGroup
from helper import expand_relative_path

def sanitize_filter_term(term):
    return term.upper().lstrip(' ').rstrip(' ')

def get_map_contacts(contactGroups,credentials,states=None):
    xero = XeroApiWrapper(credentials)
    # map_contact_groups = contactGroups
    #conf.FilterConfig.get('contact_groups', '').split('|')
    #PKG_LOGGER.debug("map contact groups: %s", map_contact_groups)
    #contact_limit = conf.BaseConfig.contact_limit or None
    #PKG_LOGGER.debug("contact limit: %s", contact_limit)
    map_contacts = xero.get_contacts_in_group_names(names=contactGroups, limit=None)
    for filter_attr, contact_attr in [
        ('states', 'main_address_state'),
        ('countries', 'main_address_country'),
    ]:
        bad_contacts = set()

        # if filter_attr not in conf.FilterConfig:
        #     continue
        #filter_values = [sanitize_filter_term(value) for value in getattr(conf.FilterConfig, filter_attr).split('|')]
        filtered_contacts = []
        for contact in map_contacts:
            # contact_value = getattr(contact,contact_attr)
            # if not contact_value:
            #     PKG_LOGGER.warn("Contact has no value for %s filter: %s" % (
            #         filter_attr,
            #         pprint.pformat(contact.contact_id)
            #     ))
            #     bad_contacts.add(contact)
            # if sanitize_filter_term(contact_value) in filter_values:
            filtered_contacts.append(contact)
        if not filtered_contacts:
            PKG_LOGGER.error("No contacts matching %s filter" % filter_attr)
        map_contacts = filtered_contacts

        if bad_contacts:
            bad_contact_urls = [
                "https://go.xero.com/Contacts/View/" + contact.contact_id
                for contact in bad_contacts
            ]
            warning = "The following contacts are missing " + contact_attr + ", please fix! "
            PKG_LOGGER.warn(warning + repr(bad_contact_urls))
            with open('warnings.txt', 'w+') as warnings:
                warnings.write(warning + '\r\n') 
                for url in bad_contact_urls:
                    warnings.write( " -> " + url + '\r\n' )

    # TODO: validate addresses
    PKG_LOGGER.info("map contacts: \n%s", XeroContactGroup.dump_contacts_sanitized_table(map_contacts))
    return map_contacts

def dump_map_contacts(map_contacts,dump_path):
    #dump_path = conf.BaseConfig.get('dump_path')
    # if dump_path:
    #     dump_path = expand_relative_path(dump_path, conf.BaseConfig.get('dump_dir'))
    
    XeroContactGroup.dump_contacts_sanitized_csv(map_contacts, dump_path=dump_path)

    PKG_LOGGER.warning("saved %d contacts to %s" % (len(map_contacts), dump_path))

def main(argv=None):
    """ main. """
    #setup_logging() # Setup proto logging
    conf = load_config(argv)
    setup_logging(**dict(conf.LogConfig))
    map_contacts = get_map_contacts(conf)
    dump_map_contacts(conf, map_contacts)
    
if __name__ == '__main__':
    main()
