#!/usr/bin/env python
"""
Generate an environment file to enroll the controller nodes to FreeIPA via the
ExtraConfigPre hook.

Please note that this is only used for testing.
"""

from __future__ import print_function

import argparse
import collections
import logging
import os
import yaml

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

autogen_warning = """### DO NOT MODIFY THIS FILE
### by the script create_freeipa_enroll_envfile.py

"""

class TemplateDumper(yaml.SafeDumper):
    def represent_ordered_dict(self, data):
        return self.represent_dict(data.items())


TemplateDumper.add_representer(collections.OrderedDict,
                               TemplateDumper.represent_ordered_dict)


def write_env_file(output_file, env_dict):
    with open(output_file, 'w') as f:
        f.write(autogen_warning)
        yaml.dump(env_dict, f, TemplateDumper, width=68,
                  default_flow_style=False)
    LOG.info("environment file written to %s" % os.path.abspath(output_file))

def get_freeipa_parameter_defaults_dict(password, server, domain,
                                        dns_servers, ipa_ip):
    parameter_defaults = {
            'FreeIPAOTP': password,
            'FreeIPAServer': server,
            'CloudDomain': domain,
        }
    if dns_servers:
        parameter_defaults['DnsServers'] = dns_servers
    if ipa_ip:
        parameter_defaults['FreeIPAIPAddress'] = ipa_ip
    return parameter_defaults

def get_freeipa_resource_registry_dict(stack, add_computes):
    resource_registry = {
        'OS::TripleO::ControllerExtraConfigPre': os.path.abspath(stack)
    }
    if add_computes:
        resource_registry['OS::TripleO::ComputeExtraConfigPre'] = (
            os.path.abspath(stack))
    return resource_registry

def _form_fqdn(name, domain):
    return "%s.%s" % (name, domain)

def get_cloud_names_parameter_defaults_dict(cloud_name,
                                             cloud_name_internal,
                                             cloud_name_storage,
                                             cloud_name_storage_management,
                                             cloud_name_ctlplane,
                                             cloud_domain):
    return {
        'CloudName': _form_fqdn(cloud_name, cloud_domain),
        'CloudNameInternal': _form_fqdn(cloud_name_internal, cloud_domain),
        'CloudNameStorage': _form_fqdn(cloud_name_storage, cloud_domain),
        'CloudNameStorageManagement': _form_fqdn(cloud_name_storage_management,
                                                 cloud_domain),
        'CloudNameCtlplane': _form_fqdn(cloud_name_ctlplane, cloud_domain),
    }

def get_freeipa_environment_dict(password, server, domain, dns_servers, ipa_ip,
                                 stack, add_computes):
    return get_environment_dict(
        get_freeipa_parameter_defaults_dict(password, server, domain,
                                            dns_servers, ipa_ip),
        get_freeipa_resource_registry_dict(stack, add_computes))

def get_cloud_names_environment_dict(cloud_name, cloud_name_internal,
                                     cloud_name_storage,
                                     cloud_name_storage_management,
                                     cloud_name_ctlplane, cloud_domain):
    return get_environment_dict(
        get_cloud_names_parameter_defaults_dict(cloud_name,
                                                 cloud_name_internal,
                                                 cloud_name_storage,
                                                 cloud_name_storage_management,
                                                 cloud_name_ctlplane,
                                                 cloud_domain))

def get_environment_dict(parameter_defaults=None, resource_registry=None):
    resulting_dict = collections.OrderedDict()
    if parameter_defaults:
        resulting_dict['parameter_defaults'] = parameter_defaults
    if resource_registry:
        resulting_dict['resource_registry'] = resource_registry
    return resulting_dict

def _confirm(message):
    user_input = raw_input(message)
    return user_input.lower() in ['true', '1', 't', 'y', 'yes']

def _confirmation_if_output_file_exists(output, overwrite):
    if os.path.isfile(output) and not overwrite:
        LOG.warning("%s exists in the filesystem." % output)
        if not _confirm("Do you want to overwrite it? "):
            raise RuntimeError("%s exists and won't be overwritten." % output)

def _assert_stack_file_exists(stack):
    if not os.path.isfile(stack):
        raise IOError("%s file doesn't exist." % args.stack)

def _assert_output_file_isnt_stack_file(output, stack):
    with open(output, 'w') as output_file:
        if os.path.abspath(output_file.name) == os.path.abspath(stack):
            raise RuntimeError(
                "The output and the stack can't be the same file")

def _assert_not_empty(server, domain):
    if not server or not domain:
        raise RuntimeError(
            "FreeIPA's server and the domain name can't be empty")

def _warn_unmatching_domain(server, domain):
    if not server.endswith(domain):
        LOG.warning(("FreeIPA's server domain doesn't seem to match the given "
                     "domain %s ... watch out") % domain)

def _validate_input(args):
    _confirmation_if_output_file_exists(args.output, args.overwrite)
    _assert_stack_file_exists(args.stack)
    _assert_output_file_isnt_stack_file(args.output, args.stack)
    _assert_not_empty(args.server, args.domain)
    _warn_unmatching_domain(args.server, args.domain)

def _get_options():
    parser = argparse.ArgumentParser(description=__doc__)
    # Base stack arguments
    parser.add_argument('-w', '--password', required=True,
                        help='The OTP that will be used for the nodes.')
    parser.add_argument('-s', '--server', required=True,
                        help="The FreeIPA server's fqdn.")
    parser.add_argument('-d', '--domain', required=True,
                        help=("The FreeIPA managed domain (must match the "
                              "kerberos realm."))
    parser.add_argument('-D', '--dns-server', action='append',
                        help=("The DNS server(s) that the overcloud should "
                              "have configured."))
    parser.add_argument('-c', '--add-computes', action='store_true',
                        help="Also override the compute preconfig.")
    parser.add_argument('-i', '--ipa-ip',
                        help="The FreeIPA server's IP address.")
    parser.add_argument('-S', '--stack',
                        default='templates/freeipa-pre-config-controller.yaml',
                        help=("location of the stack template that will be "
                              "used as ExtraConfigPre"))
    parser.add_argument('-o', '--output',
                        default='freeipa-enroll.yaml',
                        help=('file that the freeipa-related environment will '
                              'be written to.'))

    # Cloud name environment arguments
    parser.add_argument('--cloud-name',
                        default='overcloud',
                        help=("The shortname for the overcloud (the domain "
                              "will be appended to this)."))
    parser.add_argument('--cloud-name-internal',
                        default='overcloud.internalapi',
                        help=("The shortname name of the overcloud's internal "
                              "API endpoint (the domain will be appended to "
                              "this)."))
    parser.add_argument('--cloud-name-storage',
                        default='overcloud.storage',
                        help=("The shortname name of the overcloud's storage "
                              "endpoint (the domain will be appended to "
                              "this)."))
    parser.add_argument('--cloud-name-storage-management',
                        default='overcloud.storagemgmt',
                        help=("The shortname name of the overcloud's storage "
                              " management endpoint (the domain will be "
                              "appended to this)."))
    parser.add_argument('--cloud-name-ctlplane',
                        default='overcloud.ctlplane',
                        help=("The shortname name of the overcloud's "
                              "ctlplane endpoint (the domain will be "
                              "appended to this)."))
    parser.add_argument('--cloud-names-output',
                        default='cloud-names.yaml',
                        help=("file that the cloud-names environment will be "
                              "written to."))

    # Extra
    parser.add_argument('--overwrite', action='store_true',
                        help='overwrite the output file if it already exists.')
    return parser.parse_args()

def main():
    args = _get_options()
    _validate_input(args)
    env_dict = get_freeipa_environment_dict(args.password, args.server,
                                            args.domain, args.dns_server,
                                            args.ipa_ip, args.stack,
                                            args.add_computes)
    write_env_file(args.output, env_dict)

    env_dict = get_cloud_names_environment_dict(
        args.cloud_name, args.cloud_name_internal, args.cloud_name_storage,
        args.cloud_name_storage_management, args.cloud_name_ctlplane,
        args.domain)
    write_env_file(args.cloud_names_output, env_dict)
if __name__ == '__main__':
    main()
