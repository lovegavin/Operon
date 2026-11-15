CREATE TABLE controller_owner (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 cluster_id text NOT NULL, epoch bigint NOT NULL CHECK(epoch > 0), owner_id text NOT NULL,
 acquired_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE nodes (
 node_id text PRIMARY KEY, capacity_domain text NOT NULL UNIQUE,
 executor text NOT NULL CHECK(executor IN ('ssh','slurm')),
 inventory jsonb NOT NULL, observed_pool_epoch bigint, health text NOT NULL DEFAULT 'suspect',
 heartbeat_at timestamptz, revision bigint NOT NULL DEFAULT 1
);
CREATE TABLE storage_endpoints (
 storage_id text PRIMARY KEY, revision bigint NOT NULL, topology jsonb NOT NULL
);
CREATE TABLE node_mounts (
 node_id text NOT NULL REFERENCES nodes(node_id), storage_id text NOT NULL REFERENCES storage_endpoints(storage_id),
 root text NOT NULL, validation jsonb NOT NULL, PRIMARY KEY(node_id,storage_id)
);
CREATE TABLE requests (
 principal text NOT NULL, request_id text NOT NULL, digest text NOT NULL,
 receipt jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(principal,request_id)
);
CREATE TABLE quota_usage (
 principal text NOT NULL, scope text NOT NULL,
 runs bigint NOT NULL DEFAULT 0 CHECK(runs>=0), units bigint NOT NULL DEFAULT 0 CHECK(units>=0),
 plan_bytes bigint NOT NULL DEFAULT 0 CHECK(plan_bytes>=0),
 preparations bigint NOT NULL DEFAULT 0 CHECK(preparations>=0),
 retained_requests bigint NOT NULL DEFAULT 0 CHECK(retained_requests>=0),
 PRIMARY KEY(principal,scope)
);
CREATE TABLE runs (
 run_id text PRIMARY KEY, principal text NOT NULL, request_id text NOT NULL,
 plan_id text NOT NULL, plan jsonb NOT NULL, plan_bytes bigint NOT NULL,
 unit_count integer NOT NULL, preparations integer NOT NULL DEFAULT 0,
 state text NOT NULL DEFAULT 'queued', revision bigint NOT NULL DEFAULT 1,
 quota_released boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(principal,request_id) REFERENCES requests(principal,request_id)
);
CREATE TABLE units (
 run_id text NOT NULL REFERENCES runs(run_id), unit_id text NOT NULL,
 spec jsonb NOT NULL, depends_on jsonb NOT NULL, state text NOT NULL,
 revision bigint NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(run_id,unit_id)
);
CREATE TABLE environment_bindings (
 binding_id text PRIMARY KEY, requirement_digest text NOT NULL, node_id text NOT NULL REFERENCES nodes(node_id),
 generation_id text NOT NULL, content_digest text NOT NULL, verification jsonb NOT NULL,
 UNIQUE(requirement_digest,node_id,generation_id)
);
CREATE TABLE placements (
 attempt_id text PRIMARY KEY, run_id text NOT NULL, unit_id text NOT NULL,
 node_id text NOT NULL REFERENCES nodes(node_id), executor text NOT NULL,
 command_id text NOT NULL UNIQUE, request_key text NOT NULL UNIQUE,
 controller_id text NOT NULL, controller_epoch bigint NOT NULL,
 external_handle text, host_fence bigint, state text NOT NULL DEFAULT 'admitted',
 phase text NOT NULL DEFAULT 'pending', binding_id text REFERENCES environment_bindings(binding_id),
 payload jsonb NOT NULL, evidence jsonb NOT NULL DEFAULT '{}', revision bigint NOT NULL DEFAULT 1,
 active boolean NOT NULL DEFAULT true, observed_epoch bigint NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(run_id,unit_id) REFERENCES units(run_id,unit_id)
);
CREATE UNIQUE INDEX one_active_placement ON placements(run_id,unit_id) WHERE active;
CREATE TABLE transfer_jobs (
 transfer_id text PRIMARY KEY, artifact_id text NOT NULL, target_identity text NOT NULL,
 checkpoint jsonb NOT NULL, state text NOT NULL, UNIQUE(artifact_id,target_identity)
);
CREATE TABLE events (
 cursor bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, principal text NOT NULL,
 run_id text, kind text NOT NULL, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX event_principal_cursor ON events(principal,cursor);
CREATE TABLE outbox (
 command_id text PRIMARY KEY, attempt_id text REFERENCES placements(attempt_id),
 run_id text NOT NULL REFERENCES runs(run_id), kind text NOT NULL,
 state text NOT NULL DEFAULT 'pending', payload jsonb NOT NULL, evidence jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX pending_commands ON outbox(state,created_at);
CREATE TABLE cost_estimates (
 cost_key text PRIMARY KEY, seconds double precision NOT NULL CHECK(seconds>=0),
 sample_count bigint NOT NULL CHECK(sample_count>0), confidence double precision NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 updated_at timestamptz NOT NULL DEFAULT now()
);
