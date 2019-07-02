#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""Service module."""
import logging
from typing import Dict

from zipfile import ZipFile

import onapsdk.constants as const
from onapsdk.sdc_resource import SdcResource
from onapsdk.utils.headers_creator import headers_sdc_creator
from onapsdk.utils.headers_creator import headers_sdc_tester
from onapsdk.utils.headers_creator import headers_sdc_governor
from onapsdk.utils.headers_creator import headers_sdc_operator
from onapsdk.utils.jinja import jinja_env
from onapsdk.utils.configuration import tosca_path
from onapsdk.utils.configuration import components_needing_distribution


class Service(SdcResource):
    """
    ONAP Service Object used for SDC operations.

    Attributes:
        name (str): the name of the vendor. Defaults to "Generic-Vendor".
        identifier (str): the unique ID of the vendor from SDC.
        status (str): the status of the vendor from SDC.
        version (str): the version ID of the vendor from SDC.
        vsp (Vsp): the Vsp used for Service creation
        uuid (str): the UUID of the Service (which is different from
                    identifier, don't ask why...)
        distribution_status (str):  the status of distribution in the different
                                    ONAP parts.
        distribution_id (str): the ID of the distribution when service is
                               distributed.
        unique_identifier (str): Yet Another ID, just to puzzle us...

    """

    PATH = "services"
    _logger: logging.Logger = logging.getLogger(__name__)
    headers = headers_sdc_creator(SdcResource.headers)

    def __init__(self, name: str = None, sdc_values: Dict[str, str] = None):
        """
        Initialize vendor object.

        Args:
            name (optional): the name of the vendor
        """
        super().__init__(sdc_values=sdc_values)
        self.name: str = name or "ONAP-test-Service"
        if sdc_values:
            self.distribution_status = sdc_values['distributionStatus']
        self.resources = []
        self._distribution_id: str = None

    @property
    def distribution_id(self) -> str:
        """Return and lazy load the distribution_id."""
        if not self._distribution_id:
            self.load_metadata()
        return self._distribution_id

    @distribution_id.setter
    def distribution_id(self, value: str) -> None:
        """Set value for distribution_id."""
        self._distribution_id = value

    def create(self) -> None:
        """Create the Service in SDC if not already existing."""
        self._create("service_create.json.j2", name=self.name)

    def add_resource(self, resource: SdcResource) -> None:
        """
        Add a Resource to the service.

        Args:
            resource (SdcResource): the resource to add

        """
        if self.status == const.DRAFT:
            url = "{}/{}/{}/resourceInstance".format(self._base_create_url(),
                                                     self.PATH,
                                                     self.unique_identifier)

            template = jinja_env().get_template(
                "add_resource_to_service.json.j2")
            data = template.render(resource=resource,
                                   resource_type=type(resource).__name__)
            result = self.send_message("POST", "Add {} to service".format(
                type(resource).__name__), url, data=data)
            if result:
                self._logger.info("Resource %s %s has been added on serice %s",
                                  type(resource).__name__, resource.name,
                                  self.name)
                return result
            self._logger.error(
                ("an error occured during adding resource %s %s"
                 " on service %s in SDC"), type(resource).__name__,
                resource.name, self.name)
            return None
        self._logger.error("Service is not in Draft mode")
        return None

    def checkin(self) -> None:
        """Checkin Service."""
        self._verify_action_to_sdc(const.DRAFT, const.CHECKIN)

    def submit(self) -> None:
        """Really submit the SDC Service."""
        self._verify_action_to_sdc(const.DRAFT, const.SUBMIT_FOR_TESTING)

    def start_certification(self) -> None:
        """Start Certification on Service."""
        headers = headers_sdc_tester(SdcResource.headers)
        self._verify_action_to_sdc(const.DRAFT, const.START_CERTIFICATION,
                                   headers=headers)

    def certify(self) -> None:
        """Certify Service in SDC."""
        headers = headers_sdc_tester(SdcResource.headers)
        self._verify_action_to_sdc(const.DRAFT, const.CERTIFY,
                                   headers=headers)

    def approve(self) -> None:
        """Approve Service in SDC."""
        headers = headers_sdc_governor(SdcResource.headers)
        self._verify_action_to_sdc(const.DRAFT, const.APPROVE,
                                   headers=headers)

    def distribute(self) -> None:
        """Apptove Service in SDC."""
        headers = headers_sdc_operator(SdcResource.headers)
        self._verify_action_to_sdc(const.DRAFT, const.DISTRIBUTE,
                                   headers=headers)

    def get_tosca(self) -> None:
        """Get Service tosca files and save it."""
        url = "{}/services/{}/toscaModel".format(self._base_url(),
                                                 self.identifier)
        headers = self.headers.copy()
        headers["Accept"] = "application/octet-stream"
        result = self.send_message(
            "GET", "Download Tosca Model for {}".format(self.name), url,
            headers=headers)
        if result:
            csar_filename = "service-{}-csar.csar".format(self.name)
            with open((tosca_path() + csar_filename), 'wb') as csar_file:
                for chunk in result.iter_content(chunk_size=128):
                    csar_file.write(chunk)
            with ZipFile(tosca_path() + csar_filename) as myzip:
                for name in myzip.namelist():
                    if (name[-13:] == "-template.yml" and
                            name[:20] == "Definitions/service-"):
                        service_template = name
                with myzip.open(service_template) as file1:
                    with open(tosca_path() +
                              service_template[12:], 'wb') as file2:
                        file2.write(file1.read())

    def distributed(self) -> bool:
        """Check if service is distributed."""
        url = "{}/services/distribution/{}".format(self._base_create_url(),
                                                   self.distribution_id)
        headers = headers_sdc_operator(SdcResource.headers)
        result = self.send_message_json("GET",
                                        "Check distribution for {}".format(
                                            self.name), url, headers=headers)
        status = {}
        for component in components_needing_distribution():
            status[component] = False
        if result:
            distrib_list = result['distributionStatusList']
            self._logger.debug("[SDC][Get Distribution] distrib_list = %s",
                               distrib_list)
            for elt in distrib_list:
                for key in status:
                    if ((key in elt['omfComponentID']) and
                            (const.DOWNLOAD_OK in elt['status'])):
                        status[key] = True
                        self._logger.info(("[SDC][Get Distribution] Service "
                                           "distributed in %s"), key)
        for state in status.values():
            if not state:
                return False
        return True

    def load_metadata(self) -> None:
        """Load Metada of Service and retrieve informations."""
        url = "{}/services/{}/distribution".format(self._base_create_url(),
                                                   self.identifier)
        headers = headers_sdc_operator(SdcResource.headers)
        result = self.send_message_json("GET",
                                        "Get Metadata for {}".format(
                                            self.name), url, headers=headers)
        if (result and 'distributionStatusOfServiceList'in result):
            dist_status = result['distributionStatusOfServiceList'][-1]
            self._distribution_id = dist_status['distributionID']

    @classmethod
    def _get_all_url(cls) -> str:
        """
        Get URL for all elements in SDC.

        Returns:
            str: the url

        """
        return "{}/{}".format(cls._base_url(), cls.PATH)

    def _really_submit(self) -> None:
        """Really submit the SDC Service in order to enable it."""
        result = self._action_to_sdc(const.CERTIFY)
        if result:
            self.load()

    def _specific_copy(self, obj: 'Service') -> None:
        """
        Copy specific properties from object.

        Args:
            obj (Service): the object to "copy"

        """
        self.distribution_status = obj.distribution_status

    def _verify_action_to_sdc(self, desired_status: str,
                              desired_action: str, **kwargs) -> None:
        """
        Verify action to SDC.

        Verify that object is in right state before launching the action on
        SDC.

        Args:
            desired_status (str): the status the object should be
            desired_action (str): the action we want to perform
            **kwargs: any specific stuff to give to requests

        """
        self._logger.info("attempting to %s Service %s in SDC",
                          desired_action, self.name)
        if self.status == desired_status and self.created():
            result = self._action_to_sdc(desired_action, **kwargs)
            if result:
                self.load()
        elif not self.created():
            self._logger.warning("Service %s in SDC is not created", self.name)
        elif self.status != desired_status:
            self._logger.warning(("Service %s in SDC is in status %s and it "
                                  "should be in  status %s"), self.name,
                                 self.status, desired_status)