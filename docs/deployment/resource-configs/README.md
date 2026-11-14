# Per-operator resource configuration

Each JSON file configures exactly one operator. Nothing here is a shared global
configuration: a workflow node must either pass the listed parameters or the
service must set the listed environment variables.

Paths use the deployment root `/public/home/lihj/operon-resources`. Local users
should replace that prefix with their own resource root.

Files here are deployment references, not engine-owned parameters. Do not copy a
value into a different operator; use the matching file.
