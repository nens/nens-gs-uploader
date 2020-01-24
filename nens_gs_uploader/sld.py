# -*- coding: utf-8 -*-
"""#
Created on Wed Jul 24 08:24:31 2019

@author: chris.kerklaan - N&S
"""
# Third-party imports
import copy
from xml.dom import minidom


class wrap_sld:
    def __init__(self, sld_path, _type="path"):

        if _type == "path":
            self.root_copy = self.copy_root(minidom.parse(sld_path))
        elif _type == "body":
            self.root_copy = self.copy_root(minidom.parseString(sld_path))
        else:
            pass

    def get_root(self, xml):
        root = minidom.parse(xml)
        return root

    def get_all_property_names(self):
        self.items = self.root_copy.getElementsByTagName("ogc:PropertyName")
        self.property_names = [
            item.firstChild.nodeValue for item in self.items
        ]
        return self.property_names

    def _type(self):
        if len(self.get_all_property_names()) != 0:
            return ["single", "sld11"]  # with se
        else:
            return ["category", "sld10"]  # without se

    def property_name_generator(self):
        for item in self.root_copy.getElementsByTagName("ogc:PropertyName"):
            yield item.firstChild.nodeValue

    def replace_property_name(self, replacing_name, replacement_name):
        for item in self.root_copy.getElementsByTagName("ogc:PropertyName"):
            if item.firstChild.nodeValue == replacing_name:
                item.firstChild.nodeValue = replacement_name

    def lower_all_property_names(self):
        items = self.root_copy.getElementsByTagName("ogc:PropertyName")
        for item in items:
            original = item.firstChild.nodeValue
            item.firstChild.nodeValue = original.lower()

    def field_in_property_names(self, field_name):
        if field_name in self.get_all_property_names():
            return True
        else:
            return False

    def copy_root(self, root):
        return copy.deepcopy(root)

    def print_xml(self):
        return print(self.root_copy.toprettyxml())

    def get_xml(self):
        return self.root_copy.toxml()

    def write_xml(self, file_name):
        file_handle = open("{}".format(file_name), "w")
        self.root_copy.writexml(file_handle)
        file_handle.close()


def percentage_match(shape_field_name, sld_field_name):

    len_sld_field_name = len(sld_field_name)
    len_shape_field_name = len(shape_field_name)
    total = max(len_shape_field_name, len_sld_field_name)

    match_count = 0
    for letter1, letter2 in zip(shape_field_name, sld_field_name):
        if letter1 == letter2:
            match_count = match_count + 1

    if match_count == 0:
        match_count = -1
    return match_count / total


def sort_dictionary(dictionary, reverse=True):
    return sorted(dictionary.items(), key=lambda x: x[1], reverse=reverse)


def match_sld_fields(sld_field_name, shape_object):
    """ Returns the most matching sld field """

    matches = {}
    for shape_field_name in shape_object.get_all_field_names():
        matches[shape_field_name] = percentage_match(
            shape_field_name, sld_field_name
        )

    most_matching_field_name = sort_dictionary(matches)[0][0]
    most_matching_field_value = sort_dictionary(matches)[0][1]
    return most_matching_field_name, most_matching_field_value


def replace_sld_field_based_on_shape(shape_object, sld_object, sld_field_name):
    """ Replaces sld field with most matching fieldnames in shapefile. """

    print(
        """ apparently not a perfect match of sld in shape,  
          searching for a high percent match """
    )

    shape_field_name, match_value = match_sld_fields(
        sld_field_name, shape_object
    )
    if match_value < 0.8:
        print("warning, matching lower than 80%")

    sld_object.replace_property_name(sld_field_name, shape_field_name)


if __name__ == "__main__":
    # Testing sld checks
    pass
