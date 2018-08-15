#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright 2018 D. de Vries and I. van Gent

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

This file contains the definition of the `CMDOWSObject` class.
"""
from __future__ import absolute_import, division, print_function

import os

from lxml import etree
from lxml.etree import _Element
from typing import Any, Optional, Dict, Set, List, Union

from openlego.utils.cmdows_utils import get_loop_nesting_obj, get_element_by_uid
from openlego.utils.general_utils import CachedProperty


class InvalidCMDOWSFileError(ValueError):

    def __init__(self, reason=None):
        msg = 'Invalid CMDOWS file'
        if reason is not None:
            msg += ': {}'.format(reason)
        super(InvalidCMDOWSFileError, self).__init__(msg)


class CMDOWSObject(object):
    """A class that depends on a CMDOWS file and a Knowledge Base.

    This class is used as a mixin for the `LEGOModel` and `LEGOProblem` classes to avoid code dependency.

    Attributes
    ----------
        cmdows_path
        kb_path
        driver_uid

        data_folder : str, optional
            Path to the folder in which to store all data generated during the `Problem`'s execution.

        base_xml_file : str, optional
            Path to an XML file which should be kept up-to-date with the latest data describing the problem.
    """

    def __init__(self, cmdows_path=None, kb_path='', driver_uid=None, data_folder=None, base_xml_file=None, **kwargs):
        # type: (Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]) -> None
        """Initialize a CMDOWS dependent class from a given CMDOWS file and knowledge base.

        It is also possible to specify where (temporary) data should be stored, and if a base XML
        file should be kept up-to-data.

        Parameters
        ----------
            cmdows_path : str, optional
                Path to the CMDOWS file.

            kb_path : str, optional
                Path to the knowledge base.

            data_folder : str, optional
                Path to the data folder in which to store all files and output from the problem.

            base_xml_file : str, optional
                Path to a base XML file to update with the problem data.
        """
        self._cmdows_path = cmdows_path
        self._kb_path = kb_path
        self._driver_uid = driver_uid
        self.data_folder = data_folder
        self.base_xml_file = base_xml_file

        super(CMDOWSObject, self).__init__()

        if self._driver_uid is None:
            super_drivers = self.__check_for_super_driver()
            if len(super_drivers) == 1:
                self._driver_uid = super_drivers[0]
            elif len(super_drivers) > 1:
                raise AssertionError('Multiple super drivers (found: {}) are not (yet) supported by OpenLEGO.'
                                     .format(super_drivers))

    def __getattribute__(self, name):
        # type: (str) -> Any
        """Check the integrity before returning any of the cached variables.

        Parameters
        ----------
        name : str
            Name of the attribute to read.

        Returns
        -------
            any
                The value of the requested attribute.
        """
        if name != '__class__' and name != '__dict__':
            if name in [_name for _name, value in self.__class__.__dict__.items() if isinstance(value, CachedProperty)]:
                self.__integrity_check()
        return super(CMDOWSObject, self).__getattribute__(name)

    def __setattr__(self, name, value):
        # type: (str, Any) -> None
        """Add check on data_folder when setting it.

        Parameters
        ----------
            name : str
                Name of the attribute.

            value : any
                Value to set the attribute to.
        """
        if name == 'data_folder':
            self.__data_folder_check(value)

        super(CMDOWSObject, self).__setattr__(name, value)

    def __integrity_check(self):
        # type: () -> None
        """Ensure a CMDOWS file has been supplied.

        Raises
        ------
            ValueError
                If no CMDOWS file has been supplied
        """
        if self._cmdows_path is None:
            raise ValueError('No CMDOWS file specified!')

    def __data_folder_check(self, folder_string):
        # TODO: Add docstring etc.
        if folder_string:
            if not os.path.exists(folder_string):
                os.makedirs(folder_string)

    def __check_for_super_driver(self):
        # TODO Add docstring etc.
        return self._get_super_drivers(self.full_loop_nesting_list)

    def _get_super_drivers(self, loop_nesting_obj):
        # type: (Dict[str, dict]) -> Union[list, dict]
        """TODO: Complete doc
        """
        super_drivers = []
        for item in loop_nesting_obj:
            if isinstance(item, dict):
                loop_elem_name = item.keys()[0]
                if self.loop_element_types[loop_elem_name] in ['optimizer', 'doe']:
                    super_drivers.append(loop_elem_name)
                else:
                    super_drivers.extend(self._get_super_drivers(item[item.keys()[0]]))
        return super_drivers

    @CachedProperty
    def super_drivers(self):
        # TODO add doc
        return self._get_super_drivers(self.full_loop_nesting_list)

    @CachedProperty
    def sub_drivers(self):
        # TODO Add doc
        return self._get_sub_drivers(self.full_loop_nesting_list)

    def _get_sub_drivers(self, loop_nesting_obj, super_driver_encountered=False):
        # TODO add doc
        sub_drivers = []
        for item in loop_nesting_obj:
            if isinstance(item, dict):
                loop_elem_name = item.keys()[0]
                if self.loop_element_types[loop_elem_name] in ['optimizer', 'doe'] and not super_driver_encountered:
                    super_driver_encountered = True
                    sub_drivers.extend(self._get_sub_drivers(item[item.keys()[0]], True))
                elif self.loop_element_types[loop_elem_name] in ['optimizer', 'doe'] and super_driver_encountered:
                    sub_drivers.append(loop_elem_name)
                    sub_drivers.extend(self._get_sub_drivers(item[item.keys()[0]], True))
                else:
                    sub_drivers.extend(self._get_sub_drivers(item[item.keys()[0]]))
        return sub_drivers

    def invalidate(self):
        # type: () -> None
        """Invalidate the instance.

        All computed (cached) properties will be recomputed upon being read once the instance has been invalidated."""
        for value in self.__class__.__dict__.values() + CMDOWSObject.__dict__.values():
            if isinstance(value, CachedProperty):
                value.invalidate()

    @property
    def cmdows_path(self):
        # type: () -> str
        """:obj:`str`: Path to the CMDOWS file this class corresponds to.

        When this property is set the instance is automatically invalidated.
        """
        return self._cmdows_path

    @cmdows_path.setter
    def cmdows_path(self, cmdows_path):
        # type: (str) -> None
        self._cmdows_path = cmdows_path
        self.invalidate()

    @property
    def kb_path(self):
        # type: () -> str
        """:obj:`str`: Path to the knowledge base.

        When this property is set the instance is automatically invalidated.
        """
        return self._kb_path

    @kb_path.setter
    def kb_path(self, kb_path):
        # type: (str) -> None
        self._kb_path = kb_path
        self.invalidate()

    @property
    def driver_uid(self):
        # type: () -> str
        """:obj:`str`: UID of the main driver (to distinguis between main model and subdrivers).

        When this property is set the instance is automatically invalidated.
        """
        return self._driver_uid

    @driver_uid.setter
    def driver_uid(self, driver_uid):
        # type: (str) -> None
        self._driver_uid = driver_uid
        self.invalidate()

    @CachedProperty
    def elem_cmdows(self):
        # type: () -> _Element
        """:obj:`etree._Element`: Root element of the CMDOWS XML file."""
        return etree.parse(self.cmdows_path).getroot()

    @CachedProperty
    def elem_problem_def(self):
        # type: () -> _Element
        """:obj:`etree._Element`: The problemDefition element of the CMDOWS file."""
        return self.elem_cmdows.find('problemDefinition')

    @CachedProperty
    def elem_workflow(self):
        # type: () -> _Element
        """:obj:`etree._Element`: The workflow element of the CMDOWS file."""
        return self.elem_cmdows.find('workflow')

    @CachedProperty
    def elem_params(self):
        # type: () -> _Element
        """:obj:`etree._Element`: The problemRoles/parameters element of the CMDOWS file."""
        params = self.elem_cmdows.find('problemDefinition/problemRoles/parameters')
        if params is None:
            raise InvalidCMDOWSFileError('does not contain (valid) parameters in the problemRoles')
        return params

    @CachedProperty
    def elem_arch_elems(self):
        # type: () -> _Element
        """:obj:`etree._Element`: The architectureElements element of the CMDOWS file."""
        arch_elems = self.elem_cmdows.find('architectureElements')
        if arch_elems is None:
            raise InvalidCMDOWSFileError('does not contain (valid) architecture elements')
        return arch_elems

    @CachedProperty
    def elem_loop_nesting(self):
        # type: () -> _Element
        """:obj:`etree._Element`: The loopNesting element of the CMDOWS file."""
        loop_nesting = self.elem_workflow.find('processGraph/metadata/loopNesting')
        if loop_nesting is None:
            raise InvalidCMDOWSFileError('does not contain loopNesting element')
        return loop_nesting

    @CachedProperty
    def elem_model_driver(self):
        # type: () -> Union[_Element, None]
        """:obj:`etree._Element`: The XML element of the super driver."""
        uid = self.driver_uid
        if uid:
            elem = get_element_by_uid(self.elem_cmdows, uid)
            if isinstance(elem, _Element):
                return elem
            else:
                raise InvalidCMDOWSFileError('does not contain element with UID {}'.format(uid))
        else:
            return None

    @CachedProperty
    def full_loop_nesting_list(self):
        # type: () -> List[str, dict]
        """:obj:`dict`: Dictionary of the loopNesting XML element."""
        return get_loop_nesting_obj(self.elem_loop_nesting)

    @CachedProperty
    def filtered_loop_nesting_list(self):
        # TODO Add docstring
        return self.filter_loop_nesting_list(self.full_loop_nesting_list)

    def filter_loop_nesting_list(self, loop_nesting_list, sub_driver_found=False):
        # type: (List[str, dict]) -> List[str, dict]
        """TODO: update :obj:`dict`: Dictionary of the loopNesting XML element."""
        _filtered_loop_nesting_list = []
        if self._driver_uid in self.sub_drivers and not sub_driver_found:
            add_all_blocks = False
        else:
            add_all_blocks = True
        driver_uid_is_sub_driver = True if self._driver_uid in self.sub_drivers else False
        for item in loop_nesting_list:
            if isinstance(item, dict):
                loop_elem_name = item.keys()[0]
                if self.loop_element_types[loop_elem_name] == 'converger' and add_all_blocks:
                    _filtered_loop_nesting_list.append(item)
                elif self.loop_element_types[loop_elem_name] == 'coordinator':
                    _filtered_loop_nesting_list.append({loop_elem_name:self.filter_loop_nesting_list(item[loop_elem_name])})
                elif self.loop_element_types[loop_elem_name] in ['optimizer', 'doe']:
                    if loop_elem_name == self._driver_uid:
                        if driver_uid_is_sub_driver:
                            _filtered_loop_nesting_list.append(
                                                    {loop_elem_name: self.filter_loop_nesting_list(item[loop_elem_name],
                                                                                                   sub_driver_found=True)})
                        else:
                            _filtered_loop_nesting_list.append(
                                                    {loop_elem_name: self.filter_loop_nesting_list(item[loop_elem_name],
                                                                                                   sub_driver_found=False)})
                    else:
                        if driver_uid_is_sub_driver:
                            if loop_elem_name in self.sub_drivers:
                                pass
                            else:
                                # TODO: Or remove the superdriver at this level?
                                _filtered_loop_nesting_list.append({'__SuperDriverComponent__' + loop_elem_name:
                                                                        self.filter_loop_nesting_list(
                                                                            item[loop_elem_name],
                                                                            sub_driver_found=False)})
                        else:
                            _filtered_loop_nesting_list.append('__SubDriverComponent__' + loop_elem_name)
                else:
                    raise AssertionError('Could not find element details for loop element {}.'.format(loop_elem_name))
            elif isinstance(item, str):
                if add_all_blocks:
                    _filtered_loop_nesting_list.append(item)
                else:
                    pass
            else:
                raise AssertionError('Invalid type {} found in loop nesting object.'.format(type(item)))
        return _filtered_loop_nesting_list

    @CachedProperty
    def all_executable_blocks(self):
        # TODO Add docstring
        return self.collect_all_executable_blocks(self.filtered_loop_nesting_list)

    def collect_all_executable_blocks(self, loop_nesting_list):
        # TODO Add docstring
        all_executable_blocks = []
        for item in loop_nesting_list:
            if isinstance(item, dict):
                loop_elem_name = item.keys()[0]
                all_executable_blocks.extend(self.collect_all_executable_blocks(item[loop_elem_name]))
            elif isinstance(item, str):
                all_executable_blocks.append(item)
        return all_executable_blocks

    @CachedProperty
    def all_loop_elements(self):
        # TODO Add docstring
        return self.collect_all_loop_elements(self.filtered_loop_nesting_list)

    def collect_all_loop_elements(self, loop_nesting_list):
        # TODO Add docstring
        all_loop_elements = []
        for item in loop_nesting_list:
            if isinstance(item, dict):
                loop_elem_name = item.keys()[0]
                all_loop_elements.append(loop_elem_name)
                all_loop_elements.extend(self.collect_all_loop_elements(item[loop_elem_name]))
        return all_loop_elements

    @CachedProperty
    def has_optimizer(self):
        # type: () -> bool
        """:obj:`bool`: True if there is an optimizer, False if not."""
        if self.driver_uid:
            if self.loop_element_types[self.driver_uid] == 'optimizer':
                return True
        return False

    @CachedProperty
    def has_doe(self):
        # type: () -> bool
        """:obj:`bool`: True if there is a DOE component, False if not."""
        if self.driver_uid:
            if self.loop_element_types[self.driver_uid] == 'doe':
                return True
        return False

    @CachedProperty
    def has_driver(self):
        # type: () -> bool
        """:obj:`bool`: True if there is a driver component (DOE or optimizer), False if not."""
        if self.has_doe or self.has_optimizer:
            return True
        return False

    @CachedProperty
    def block_order(self):
        # TODO: Add type and docstring
        return [x for _, x in sorted(zip(self.process_info['step_numbers'], self.process_info['uids']))]

    @CachedProperty
    def partition_sets(self):
        # type: () -> Dict[Set[str]]
        """:obj:`dict` of :obj:`set`: Dictionary of executable block ``uIDs`` per partitionID."""
        partitions = dict()
        for idx, block in enumerate(self.process_info['uids']):
            if self.process_info['partition_ids'][idx] is not None:
                partition_id = self.process_info['partition_ids'][idx]
                if partition_id not in partitions:
                    partitions[partition_id] = {block}
                else:
                    partitions[partition_id].add(block)
        return partitions

    @CachedProperty
    def coupled_blocks(self):
        # type: () -> List[str]
        """:obj:`list` of :obj:`str`: List of ``uIDs`` of the coupled executable blocks specified in the CMDOWS file."""
        _coupled_blocks = []
        for block in self.elem_arch_elems.iterfind(
                'executableBlocks/coupledAnalyses/coupledAnalysis/relatedExecutableBlockUID'):
            if block.text in self.all_executable_blocks:
                _coupled_blocks.append(block.text)
        return _coupled_blocks

    @CachedProperty
    def loop_element_types(self):
        # type: () -> Dict[str]
        """:obj:`dict` of :obj:`str`: Dictionary with mapping of loop elements specified in the CMDOWS file."""
        _loopelement_details = {}
        for elem in self.elem_arch_elems.iterfind('executableBlocks/coordinators/coordinator'):
            _loopelement_details[elem.attrib['uID']] = 'coordinator'
        for elem in self.elem_arch_elems.iterfind('executableBlocks/convergers/converger'):
            _loopelement_details[elem.attrib['uID']] = 'converger'
        for elem in self.elem_arch_elems.iterfind('executableBlocks/optimizers/optimizer'):
            _loopelement_details[elem.attrib['uID']] = 'optimizer'
        for elem in self.elem_arch_elems.iterfind('executableBlocks/does/doe'):
            _loopelement_details[elem.attrib['uID']] = 'doe'
        return _loopelement_details

    @CachedProperty
    def process_info(self):
        # TODO: Add type and docstring
        _uids = []
        _process_step_numbers = []
        _partition_ids = []
        for elem in self.elem_workflow.iterfind('processGraph/nodes/node'):
            _uids.append(elem.find('referenceUID').text)
            _process_step_numbers.append(int(elem.find('processStepNumber').text))
            if elem.find('partitionID') is not None:
                _partition_ids.append(elem.find('partitionID').text)
            else:
                _partition_ids.append(None)
        return {'uids': _uids, 'step_numbers': _process_step_numbers, 'partition_ids': _partition_ids}

    @CachedProperty
    def process_step_numbers(self):
        # TODO: Add type and docstring
        _process_step_numbers = {}
        for elem in self.elem_workflow.iterfind('processGraph/nodes/node'):
            _process_step_numbers[elem.find('referenceUID').text] = int(elem.find('processStepNumber').text)
        return _process_step_numbers


# TODO: Collect keyword terms like __SubDriverComponent__, __SuperDriverComponent__, etc.