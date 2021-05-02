#!/usr/bin/env python2
"""Container classes and utilities for containing data."""

import csv
import heapq
from copy import copy

import tabulate

from helper import SanitationUtils
from log import PKG_LOGGER

class XeroObjectGroup(object):
    @classmethod
    def dump_items_csv(cls, items, dump_path='items.csv', names=None, flatten_attr=None):
        try:
            with open(dump_path, 'w'):
                pass
        except IOError as exc:
            PKG_LOGGER.error("file " + dump_path + " could not be opened. Try closing the file. " + repr(exc))
            try:
                input("Press enter to continue")
            except SyntaxError:
                pass

        with open(dump_path, 'w') as dump_path:
            writer = csv.DictWriter(dump_path, names, extrasaction='ignore')
            writer.writeheader()
            for item in items:
                if flatten_attr:
                    item = getattr(item, flatten_attr)()
                elif hasattr(item, '_data'):
                    item = getattr(item, '_data')
                item = dict([
                    (
                        SanitationUtils.to_ascii(key, errors='ignore'),
                        SanitationUtils.to_ascii(value, errors='ignore')
                    ) for key, value in item.items()
                ])
                writer.writerow(item)

class XeroContactGroup(XeroObjectGroup):
    names_raw_csv = {
        'ContactID': 'ContactID',
        'ContactGroups': 'ContactGroups',
        'ContactNumber': 'ContactNumber',
        'ContactStatus': 'ContactStatus',
        'EmailAddress': 'EmailAddress',
        'Name': 'Name',
        'Address': 'Address',
        'Phone': 'Phone',
    }

    @classmethod
    def dump_contacts_raw_csv(cls, contacts, dump_path='contacts-raw.csv'):
        cls.dump_items_csv(
            contacts.flatten_raw, dump_path, cls.names_raw_csv, 'flatten_raw')

    @classmethod
    def dump_contacts_verbose_csv(cls, contacts, dump_path='contacts-verbose.csv'):
        names = copy(cls.names_raw_csv) 
        for key in ['Address', 'Phone']:
            del names[key]
        names.update({
            'MAIN Address': 'MAIN Address',
            'POBOX Address': 'POBOX Address',
            'STREET Address': 'STREET Address',
            'DELIVERY Address': 'DELIVERY Address',
            'MAIN Phone': 'Main Phone',
            'DEFAULT Phone': 'DEFAULT Phone',
            'DDI Phone': 'DDI Phone',
            'MOBILE Phone': 'MOBILE Phone',
            'FAX Phone': 'FAX Phone',
        })
        cls.dump_items_csv(contacts, dump_path, names, 'flatten_verbose')

    names_sanitized_csv = {
        'Name': 'Company Name',
        'AddressLine': 'Address',
        'AddressArea': 'Area',
        'AddressPostcode': 'Postcode',
        'AddressState': 'State',
        'AddressCountry': 'Country',
        'Phone': 'Phone',
        'EmailAddress': 'Email',
    }

    @classmethod
    def dump_contacts_sanitized_csv(cls, contacts, dump_path='contacts-sanitized.csv'):
        names = copy(cls.names_sanitized_csv)
        cls.dump_items_csv(contacts, dump_path, names, 'flatten_sanitized')

    @classmethod
    def dump_contacts_sanitized_table(cls, contacts):
        return tabulate.tabulate(
            [contact.flatten_sanitized() for contact in contacts],
            headers='keys'
        )

class XeroObject(object):
    def _primary_property(
            self, properties, type_key, type_priority, fn_empty, default=None):
        """ Abstract main_address and main_phone. """
        if not properties:
            return default
        if len(properties) == 1:
            return properties[0]
        nonempty_properties = []
        for property_ in properties:
            type_ = property_.get(type_key)
            try:
                priority = type_priority.index(type_)
            except ValueError:
                priority = len(type_priority)
            if not fn_empty(property_):
                heapq.heappush(nonempty_properties, (priority, property_))
        if nonempty_properties:
            _, primary_property = heapq.heappop(nonempty_properties)
            return primary_property
        return default


class XeroContact(XeroObject):
    def __init__(self, data):
        self.data = data

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        self._data = value
        self._main_address = {}
        self._main_phone = {}

    address_type_priority = [
        'STREET', 'POBOX', 'DELIVERY'
    ]

    @property
    def main_address(self):
        if getattr(self, '_main_address', None):
            return self._main_address

        def address_empty(address):
            return not any([
                value for key, value in address.items() \
                if key.startswith("AddressLine")
            ])

        self._main_address = self._primary_property(
            self.data.get('Addresses', []), 'AddressType',
            self.address_type_priority, address_empty, default={}
        )
        return self._main_address

    phone_type_priority = [
        'DEFAULT', 'DDI', 'MOBILE'
    ]

    @property
    def main_phone(self):
        if getattr(self, '_main_phone', None):
            return self._main_phone

        def phone_empty(phone):
            return 'PhoneNumber' not in phone

        self._main_phone = self._primary_property(
            self.data.get('Phones', []), 'PhoneType',
            self.phone_type_priority, phone_empty, default={}
        )
        return self._main_phone


    @property
    def company_name(self):
        if 'Name' in self.data and self.data.get('Name') :
            return self.data['Name']

    @property
    def main_address_lines(self):
        main_address = self.main_address
        lines = []
        for line in range(1, 5):
            key = "AddressLine%d" % line
            if key not in main_address:
                continue
            line = main_address[key]
            if line:
                lines.append(line)
        return ", ".join(lines)



    @property
    def main_address_area(self):
        main_address = self.main_address
        return main_address.get('City')

    @property
    def main_address_postcode(self):
        main_address = self.main_address
        return main_address.get('PostalCode')

    @property
    def main_address_state(self):
        main_address = self.main_address
        return main_address.get('Region')

    @classmethod
    def convert_country_code(cls, country_code):
        # TODO: complete this
        if country_code == 'AU':
            return 'Australia'
        return country_code

    @property
    def main_address_country(self):
        main_address = self.main_address
        country_code = main_address.get('Country', '') or 'AU'
        return self.convert_country_code(country_code)

    @property
    def phone(self):
        main_phone = self.main_phone
        response = None
        if not (main_phone and main_phone.get('PhoneNumber')):
            return response
        response = main_phone['PhoneNumber']
        if not main_phone.get('PhoneAreaCode'):
            return response
        response = "%s %s" % (
            main_phone['PhoneAreaCode'],
            response
        )
        if not main_phone.get('PhoneCountryCode'):
            return response
        response = "(%s) %s" % (
            main_phone['PhoneCountryCode'],
            response
        )
        return response

    @property
    def archived(self):
        return self.data.get('ContactStatus') == 'ARCHIVED'

    @property
    def active(self):
        return self.data.get('ContactStatus') == 'ACTIVE'

    @property
    def contact_id(self):
        return self.data.get('ContactID')

    def flatten_raw(self):
        flattened = dict()
        for key in [
            'ContactID', 'ContactGroups', 'ContactNumber',
            'ContactStatus', 'EmailAddress', 'Name'
        ]:
            flattened[key] = self.data.get(key)
        for data_key, data_type, type_default in [
            ('Addresses', 'Address', 'POBOX'),
            ('Phones', 'Phone', 'DEFAULT'),
        ]:
            type_key = '%sType' % data_type
            for property_ in self.data[data_key]:
                property_ = copy(property_)
                property_type = property_.pop(type_key, type_default)
                flat_key = '%s %s' % (data_type, property_type)
                assert flat_key not in flattened, "duplicate key %s being added to flat" % flat_key
                flattened[flat_key] = property_

        return flattened

    def flatten_verbose(self):
        flattened = self.flatten_raw()
        for flat_key, attribute in [
            ('MAIN Address', 'main_address'),
            ('MAIN Phone', 'main_phone')
        ]:
            flattened[flat_key] = getattr(self, attribute)
        return flattened

    def flatten_sanitized(self):
        flattened = dict()
        for key in [
            'ContactID', 'EmailAddress', 'Name'
        ]:
            flattened[key] = self.data.get(key)

        for flat_key, attribute in [
            ('AddressLine', 'main_address_lines'),
            ('AddressArea', 'main_address_area'),
            ('AddressPostcode', 'main_address_postcode'),
            ('AddressState', 'main_address_state'),
            ('AddressCountry', 'main_address_country'),
            ('Phone', 'phone'),
        ]:
            flattened[flat_key] = getattr(self, attribute)
        return flattened
