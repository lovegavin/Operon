"""Storage-only Paramiko connections with explicit trust at every hop.

No remote shell, Operon handshake, install, or ProxyCommand is involved.
An instance exclusively owns its SFTP client, target connection and jump channel.
"""
from __future__ import annotations

import math
from operon.remote.client import HostKeyRequired
from .references import StorageError


class SFTPConnection:
    def __init__(self, profile, credentials, *, jump_profile=None,
                 jump_credentials=None, io_timeout=10):
        import paramiko
        if (isinstance(io_timeout, bool) or not isinstance(io_timeout, (int, float))
                or not math.isfinite(io_timeout) or io_timeout <= 0):
            raise ValueError('SFTP I/O timeout must be positive')
        self.sftp = self.target = self.jump = self.tunnel = None

        def connect(profile, credentials, *, sock=None):
            if any(profile.get(key) for key in ('ProxyCommand', 'proxy_command', 'proxycommand')):
                raise StorageError('Shell ProxyCommand routes are not supported',
                                   code='storage_route_unsupported')
            client = paramiko.SSHClient()
            trusted = profile.get('host_key')

            class Trust(paramiko.MissingHostKeyPolicy):
                def missing_host_key(policy, ssh, hostname, key):
                    if (not trusted or trusted['type'] != key.get_name()
                            or trusted['base64'] != key.get_base64()):
                        raise HostKeyRequired(key, changed=bool(trusted))

            # This is the same user-approved profile key policy as SSHConnection.
            # Neither jump nor target keys are implicitly accepted or saved.
            client.set_missing_host_key_policy(Trust())
            try:
                client.connect(profile['host'], port=profile['port'], username=profile['username'],
                               password=credentials.get('password') or None,
                               passphrase=credentials.get('passphrase') or None,
                               key_filename=profile.get('key_path') or None,
                               allow_agent=profile['auth'] == 'agent',
                               look_for_keys=profile['auth'] == 'agent', sock=sock,
                               timeout=io_timeout, auth_timeout=30, banner_timeout=30)
                client.get_transport().set_keepalive(20)
                return client
            except BaseException:
                client.close()
                raise

        try:
            if jump_profile is not None:
                self.jump = connect(jump_profile, jump_credentials or {})
                self.tunnel = self.jump.get_transport().open_channel(
                    'direct-tcpip', (profile['host'], profile['port']),
                    ('127.0.0.1', 0), timeout=io_timeout)
            self.target = connect(profile, credentials, sock=self.tunnel)
            self.sftp = self.target.open_sftp()
            self.sftp.get_channel().settimeout(io_timeout)
        except BaseException:
            self.close()
            raise

    def close(self):
        for name in ('sftp', 'target', 'tunnel', 'jump'):
            resource = getattr(self, name, None)
            setattr(self, name, None)
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
