#!/usr/bin/env python
"""
Create the necessary hosts and services in FreeIPA before we attempt to enroll
them. This assumes that you have the appropriate credentials set already.
"""

from __future__ import print_function
from __future__ import unicode_literals

import argparse
import itertools
import logging

from ipalib import api
from ipalib import errors
import six

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

NETWORKS = ['ctlplane', 'internalapi', 'storage', 'storagemgmt']

CLOUD_VIP_HOSTS_TEMPLATE = 'overcloud'
CLOUD_VIP_HOSTS_SERVICES = ['haproxy', 'mysql']


CONTROLLERS_TEMPLATE = 'overcloud-controller-{node_id}'
CONTROLLER_HOSTS_SERVICES = ['HTTP']


COMPUTES_TEMPLATE = 'overcloud-novacompute-{node_id}'
COMPUTES_SERVICES = []


class IPAHostDriver(object):
    def __init__(self, api):
        self.api = api

    def delete_host(self, fqdn):
        try:
            return self.api.Command.host_del(fqdn)
        except Exception as e:
            LOG.exception("Couldn't delete host: %s" % fqdn)
            raise

    def create_host(self, fqdn, password=None, overwrite_existing=True):
        try:
            kwargs={}
            if password:
                kwargs['userpassword'] = password
            res = self.api.Command.host_add(fqdn, force=True, **kwargs)
            LOG.info(res['summary'])
            return res['result']['fqdn'][0]
        except errors.DuplicateEntry:
            if overwrite_existing:
                LOG.warning("host %s already exists... overwritting" % fqdn)
                self.delete_host(fqdn)
                return self.create_host(fqdn, password=password,
                                        overwrite_existing=False)
            else:
                raise
        except Exception as e:
            LOG.exception("Couldn't create host: %s" % fqdn)
            raise

    def create_service(self, principal):
        try:
            res = self.api.Command.service_add(principal, force=True)
            LOG.info(res['summary'])
            return res['result']['krbprincipalname'][0]
        except Exception as e:
            LOG.exception("Couldn't create service: %s" % principal)
            raise

    def service_add_host(self, principal, host):
        try:
            res = self.api.Command.service_add_host(principal, host=host)
        except Exception as e:
            LOG.exception("Couldn't add host %s to service %s" % (host,
                                                                  principal))
            raise

def create_host(driver, hostname, domain, network=None, password=None):
    fqdn = ".".join(x for x in [hostname, network, domain] if x)
    return driver.create_host(fqdn, password)

def create_services_for_host(driver, fqdn, services):
    resulting_services = list()
    for service in services:
        principal = "%s/%s" % (service, fqdn)
        resulting_services.append(driver.create_service(principal))
    return resulting_services


def create_hosts(api, domain, password, controller_count, compute_count):
    driver = IPAHostDriver(api)

    # VIP
    vip_services = list()
    fqdn = create_host(driver, CLOUD_VIP_HOSTS_TEMPLATE, domain)
    vip_services.extend(
        create_services_for_host(driver, fqdn, CLOUD_VIP_HOSTS_SERVICES))
    for network in NETWORKS:
        fqdn = create_host(driver, CLOUD_VIP_HOSTS_TEMPLATE, domain, network)
        vip_services.extend(
            create_services_for_host(driver, fqdn, CLOUD_VIP_HOSTS_SERVICES))

    # controllers
    for index in xrange(0, controller_count):
        hostname = CONTROLLERS_TEMPLATE.format(node_id=index)
        main_fqdn = create_host(driver, hostname, domain, password=password)
        # base controller nodes manage VIP services
        for vip_service in vip_services:
            driver.service_add_host(vip_service, main_fqdn)

        # create subnet controller hosts and services
        for network in NETWORKS:
            hostname = CONTROLLERS_TEMPLATE.format(node_id=index)
            fqdn = create_host(driver, hostname, domain, network)
            services = create_services_for_host(driver, fqdn,
                                                CONTROLLER_HOSTS_SERVICES)
            # base controller nodes manage subnet controller services
            for service in services:
                driver.service_add_host(service, main_fqdn)

    # computes
    for index in xrange(0, compute_count):
        hostname = COMPUTES_TEMPLATE.format(node_id=index)
        fqdn = create_host(driver, hostname, domain, password=password)
        for network in NETWORKS:
            hostname = COMPUTES_TEMPLATE.format(node_id=index)
            fqdn = create_host(driver, hostname, domain, network)
            create_services_for_host(driver, fqdn, COMPUTES_SERVICES)


def get_freeipa_api():
    api.bootstrap(context='cli')
    api.finalize()
    api.Backend.rpcclient.connect()
    return api


def check_negative(value):
    ivalue = int(value)
    if ivalue < 0:
         raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
    return ivalue


def use_utf8(value):
    return value.decode('utf-8')


def _get_options():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-w', '--password', required=True, type=use_utf8,
                        help='The OTP that will be used for the nodes.')
    parser.add_argument('-d', '--domain', required=True, type=use_utf8,
                        help=("The FreeIPA managed domain (must match the "
                              "kerberos realm."))
    parser.add_argument('--controller-count', default=1, type=check_negative)
    parser.add_argument('--compute-count', default=1, type=check_negative)
    return parser.parse_args()


def main():
    args = _get_options()
    api = get_freeipa_api()
    create_hosts(api, args.domain, args.password, args.controller_count,
                 args.compute_count)


if __name__ == '__main__':
    main()
