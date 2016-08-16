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

def get_environment_dict(password, server, domain, stack, dns_servers):
    parameter_defaults = {
            'FreeIPAOTP': password,
            'FreeIPAServer': server,
            'FreeIPADomain': domain,
            'CloudDomain': domain,
        }
    if dns_servers:
        parameter_defaults['DnsServers'] = dns_servers
    return collections.OrderedDict([
        ('parameter_defaults', parameter_defaults),
        ('resource_registry', {
            'OS::TripleO::ControllerExtraConfigPre': os.path.abspath(stack)
        })
    ])

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
                     "domain %s ... watch out") % args.domain)

def _validate_input(args):
    _confirmation_if_output_file_exists(args.output, args.overwrite)
    _assert_stack_file_exists(args.stack)
    _assert_output_file_isnt_stack_file(args.output, args.stack)
    _assert_not_empty(args.server, args.domain)
    _warn_unmatching_domain(args.server, args.domain)

def _get_options():
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument('-S', '--stack',
                        default='templates/freeipa-pre-config-controller.yaml',
                        help=("location of the stack template that will be "
                              "used as ExtraConfigPre"))
    parser.add_argument('-o', '--output',
                        default='freeipa-enroll.yaml',
                        help='file that the environment will be written to.')
    parser.add_argument('--overwrite', action='store_true',
                        help='overwrite the output file if it already exists.')
    return parser.parse_args()

def main():
    args = _get_options()
    _validate_input(args)
    env_dict = get_environment_dict(args.password, args.server, args.domain,
                                    args.stack, args.dns_server)
    write_env_file(args.output, env_dict)
if __name__ == '__main__':
    main()
