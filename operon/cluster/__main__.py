"""Experimental cluster controller lifecycle and PostgreSQL receipts.

Only the serve subcommand starts a scheduler; other commands never autostart it.
Multi-host SSH/failover and Slurm are experimental and not platform-qualified.
The default desktop and server execution path remains the validated host pool.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import Field

from operon.contracts.base import ContractModel
from operon.contracts.run_plan import RunPlan
from .postgres import DatabaseConfig, Postgres
from .repository import ClusterRepository


class ClusterCLIConfig(ContractModel):
    format: Literal['operon.cluster-client'] = 'operon.cluster-client'
    schema_version: Literal[1] = 1
    dsn_environment: str = Field(default='OPERON_CLUSTER_DSN', pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    schema_name: str = Field(default='public', pattern=r'^[a-z_][a-z0-9_]{0,62}$')
    # Configuration belongs to the authenticated DB service account. Caller
    # supplied arbitrary --principal flags are intentionally not an identity.
    principal: str = Field(min_length=1, max_length=128)


def _read(path, *, limit):
    with Path(path).open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Input exceeds its configured byte limit')
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate JSON key')
            value[key] = item
        return value
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True, help='Strict service-account client configuration; DSN is read from an environment variable')
    sub = parser.add_subparsers(dest='operation', required=True)
    sub.add_parser('migrate', help='Apply packaged additive PostgreSQL migrations under the migration lock')
    sub.add_parser('serve', help='Own one configured controller until interrupted; requires prior migration and verified preparations')
    submit = sub.add_parser('submit', help='Commit a RunPlan admission and return its durable receipt')
    submit.add_argument('--plan', type=Path, required=True)
    submit.add_argument('--request-id', required=True)
    for name in ('status', 'cancel'):
        command = sub.add_parser(name)
        command.add_argument('run_id')
    lookup = sub.add_parser('lookup', help='Resolve the original request key after an uncertain submission')
    lookup.add_argument('request_id')
    events = sub.add_parser('events')
    events.add_argument('--after', default='0')
    events.add_argument('--limit', default=200, type=int)
    args = parser.parse_args(argv)
    database = None
    try:
        raw_config = _read(args.config, limit=1024 * 1024)
        if args.operation == 'serve' or raw_config.get('format') == 'operon.cluster-controller':
            from .daemon import ControllerSettings, serve
            config = ControllerSettings.model_validate(raw_config)
        else:
            config = ClusterCLIConfig.model_validate(raw_config)
        dsn = os.environ.get(config.dsn_environment)
        if not dsn:
            raise ValueError('Configured cluster DSN environment variable is not set')
        database = Postgres(DatabaseConfig(dsn, schema=config.schema_name))
        repository = ClusterRepository(database)
        if args.operation == 'serve':
            result = serve(config, database, directory=args.config.resolve().parent)
        elif args.operation == 'migrate':
            result = {'migrations': list(database.migrate())}
        elif args.operation == 'submit':
            plan = RunPlan.model_validate(_read(args.plan, limit=repository.limits.plan_bytes))
            result = repository.submit(principal=config.principal, request_id=args.request_id, plan=plan)
        elif args.operation == 'status':
            result = repository.status(config.principal, args.run_id)
        elif args.operation == 'cancel':
            result = repository.cancel(config.principal, args.run_id)
        elif args.operation == 'lookup':
            result = repository.request(config.principal, args.request_id)
        else:
            result = repository.events(config.principal, after=args.after, limit=args.limit)
        print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception as exc:
        # Never print DSNs, SQL statements, driver connection text or credentials.
        code = getattr(exc, 'code', 'cluster_command_failed')
        result = {'ok': False, 'error': {'code': code, 'message': 'Cluster operation did not complete',
                                       'next_actions': ['lookup_original_request'] if code == 'commit_outcome_unknown' else []}}
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 1
    finally:
        if database is not None:
            database.close()


if __name__ == '__main__':
    raise SystemExit(main())
