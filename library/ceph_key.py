#!/usr/bin/python
# Copyright 2018, Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ceph_key

author: Sebastien Han <seb@redhat.com>

short_description: Manage Cephx key(s)

version_added: "2.6"

description:
    - Manage CephX creation, deletion and updates.
    It can also list and get information about key(s)
options:
    cluster:
        description:
            - The ceph cluster name.
        required: false
        default: ceph
    name:
        description:
            - name of the CephX key
        required: true
    state:
        description:
            - present|absent|list|update|info
        required: true
        choices: ['present', 'absent', 'list', 'update', 'info']
        default: list
    caps:
        description:
            - CephX key capabilities
        required: false
    secret:
        description:
            - key's secret value
        required: false
        default: None
    containerized:
        description:
            - Weither or not this is a containerized cluster. The value is
            assigned or not depending on how the playbook runs.
        required: false
        default: None
'''

EXAMPLES = '''
- name: create cephx key
  ceph_key:
    name: "my_key"
    state: present
    caps: "{{ caps }}"

- name: update cephx key
  ceph_key:
    name: "my_key"
    state: update
    caps: "{{ caps }}"

- name: delete cephx key
  ceph_key:
    name: "my_key"
    state: absent

- name: info cephx key
  ceph_key:
    name: "my_key""
    state: info

- name: list cephx keys
  ceph_key:
    state: list
'''

RETURN = '''#  '''

from ansible.module_utils.basic import AnsibleModule
import datetime
import os
import struct
import time
import base64


def fatal(message, module):
    '''
    Report a fatal error and exit
    '''

    if module:
        module.fail_json(msg=message, rc=1)
    else:
        raise(Exception(message))


def key_mode(file_path):
    '''
    Change mode file for a CephX key
    Problem, how do to do on containerized deployment?
    '''
    os.chmod(file_path)


def generate_secret():
    '''
    Generate a CephX secret
    '''

    key = os.urandom(16)
    header = struct.pack('<hiih', 1, int(time.time()), 0, len(key))
    secret = base64.b64encode(header + key)

    return secret


def generate_caps(cmd, type, caps):
    '''
    Generate CephX capabilities list
    '''
    cmd = cmd

    for k, v in caps.iteritems():
        if type == "ceph-authtool":
            cmd.extend(["--cap"])

        cmd.extend([k, v])

    return cmd


def generate_ceph_cmd(cluster, args, containerized):
    '''
    Generate 'ceph' command line to execute
    '''

    cmd = []

    base_cmd = [
        'ceph',
        '--cluster',
        cluster,
        'auth',
    ]

    cmd.extend(base_cmd + args)

    if containerized:
        cmd = containerized.split() + cmd

    return cmd


def generate_ceph_authtool_cmd(cluster, name, secret, caps, containerized):
    '''
    Generate 'ceph-authtool' command line to execute
    '''

    file_destination = "/etc/ceph/" + cluster + "." + name + ".keyring"

    cmd = [
        'ceph-authtool',
        '--create-keyring',
        file_destination,
        '--name',
        name,
        '--add-key',
        secret,
    ]

    cmd = generate_caps(cmd, "ceph-authtool", caps)

    if containerized:
        cmd = containerized.split() + cmd

    return cmd


def create_key(module, result, cluster, name, secret, caps, containerized):
    '''
    Create a CephX key
    '''

    file_path = "/etc/ceph/" + cluster + "." + name + ".keyring"

    args = [
        "import",
        "-i",
        file_path,
    ]
    cmd_list = []

    if secret is None:
        secret = generate_secret()

    cmd_list.append(generate_ceph_authtool_cmd(cluster, name, secret, caps, containerized))
    cmd_list.append(generate_ceph_cmd(cluster, args, containerized))

    return cmd_list


def update_key(cluster, name, caps, containerized):
    '''
    Update a CephX key's capabilities
    '''

    cmd_list = []

    args = [
        "caps",
        name,
    ]

    args = generate_caps(args, "ceph", caps)
    cmd_list.append(generate_ceph_cmd(cluster, args, containerized))

    return cmd_list


def delete_key(cluster, name, containerized):
    '''
    Delete a CephX key
    '''

    cmd_list = []

    args = [
        "del",
        name,
    ]

    cmd_list.append(generate_ceph_cmd(cluster, args, containerized))

    return cmd_list


def info_key(cluster, name, containerized):
    '''
    Get information about a CephX key
    '''

    cmd_list = []

    args = [
        "get",
        name,
        '-f',
        'json',
    ]

    cmd_list.append(generate_ceph_cmd(cluster, args, containerized))

    return cmd_list


def list_keys(cluster, containerized):
    '''
    List all CephX keys
    '''

    cmd_list = []

    args = [
        "ls",
        '-f',
        'json',
    ]

    cmd_list.append(generate_ceph_cmd(cluster, args, containerized))

    return cmd_list


def exec_commands(module, cmd_list):
    '''
    Execute command(s)
    '''

    for cmd in cmd_list:
        rc, out, err = module.run_command(cmd, encoding=None)
        if rc != 0:
            return rc, cmd, out, err

    return rc, cmd, out, err


def run_module():
    module_args = dict(
        cluster=dict(type='str', required=False, default='ceph'),
        name=dict(type='str', required=False),
        state=dict(type='str', required=True),
        containerized=dict(type='str', required=False, default=None),
        caps=dict(type='dict', required=False, default=None),
        secret=dict(type='str', required=False, default=None),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Gather module parameters in variables
    cluster = module.params['cluster']
    containerized = module.params['containerized']
    name = module.params['name']
    state = module.params['state']
    caps = module.params['caps']
    secret = module.params['secret']

    result = dict(
        changed=False,
        stdout='',
        stderr='',
        rc='',
        start='',
        end='',
        delta='',
    )

    if module.check_mode:
        return result

    startd = datetime.datetime.now()

    if state == "present":
        if caps is None:
            fatal("Capabilities must be provided when state is 'present'", module)

        if len(secret) == 0:
            secret = None

        # Test if the key exists, if it does we skip its creation
        rc, cmd, out, err = exec_commands(module, info_key(cluster, name, containerized))
        if rc == 0:
            result["stdout"] = "skipped, since {0} already exists, if you want to update a key use 'state: update'".format(name)
            result['rc'] = rc
            module.exit_json(**result)

        rc, cmd, out, err = exec_commands(module, create_key(module, result, cluster, name, secret, caps, containerized))

    elif state == "update":
        if caps is None:
            fatal("Capabilities must be provided when state is 'update'", module)

        # Test if the key exists, if it does not we skip
        rc, cmd, out, err = exec_commands(module, info_key(cluster, name, containerized))
        if rc != 0:
            result["stdout"] = "skipped, since {0} does not exist".format(name)
            result['rc'] = 0
            module.exit_json(**result)

        rc, cmd, out, err = exec_commands(module, update_key(cluster, name, caps, containerized))

    elif state == "absent":
        rc, cmd, out, err = exec_commands(module, delete_key(cluster, name, containerized))

    elif state == "info":
        # Test if the key exists, if it does not we skip
        rc, cmd, out, err = exec_commands(module, info_key(cluster, name, containerized))
        if rc != 0:
            result["stdout"] = "skipped, since {0} does not exist".format(name)
            result['rc'] = 0
            module.exit_json(**result)

        rc, cmd, out, err = exec_commands(module, info_key(cluster, name, containerized))

    elif state == "list":
        rc, cmd, out, err = exec_commands(module, list_keys(cluster, containerized))

    else:
        module.fail_json(msg='State must either be "present" or "absent" or "update" or "list" or "info".', changed=False, rc=1)

    endd = datetime.datetime.now()
    delta = endd - startd

    result = dict(
        cmd=cmd,
        start=str(startd),
        end=str(endd),
        delta=str(delta),
        rc=rc,
        stdout=out.rstrip(b"\r\n"),
        stderr=err.rstrip(b"\r\n"),
        changed=True,
    )

    if rc != 0:
        module.fail_json(msg='non-zero return code', **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
