"""SSH bootstrap without a preinstalled Python. Only owned server paths change."""
import base64
import hashlib
import gzip
import io
import json
from pathlib import Path
import re
import shlex
import tarfile
import time
import uuid

MAMBA_URL = 'https://conda.anaconda.org/conda-forge/linux-64/micromamba-2.10.0-0.tar.bz2'
# Native helpers only: Python, pip and the two Hi-C command line tools.
# Compilers are added on demand when a source build is actually required.
CONDA_PACKAGES = 'python=3.11 pip bwa=0.7.19 samtools=1.22.1'
# Shell-safe tokens: each spec must reach micromamba as its own argument.
CONDA_SPECS = ' '.join(spec for spec in CONDA_PACKAGES.split() if spec)
CONDA_MARKER = '.operon-conda-packages'
MAMBA_ARCHIVE_SHA = '9a97976244929bbae28fb1fae504e74a3e7e6d1932870e3a03321f01b7fbd07b'
MAMBA_SHA = '701f39c06f8e6a670a0e186c8479b9e5c0502a2f0cda6cef65d83bdd2875e8bd'
# Fixed ordinary epoch retains reproducible archives without old-timestamp warnings.
SOURCE_EPOCH = 946684800  # 2000-01-01 UTC


def source_archive(root):
    """Explicit code allowlist. Never includes profiles, datasets, SSH or git files."""
    root = Path(root)
    files = [root / name for name in ('pyproject.toml', 'README.md', 'requirements-hic-linux.txt',
                                     'scripts/run.py', 'scripts/desktop_server.py')]
    if (root / 'library/pyproject.toml').is_file():
        files += [root / 'library/pyproject.toml', root / 'library/release.json']
    for directory in ('operon', 'operon_sdk', 'operon', 'src', 'library/seed'):
        files += [p for p in (root / directory).rglob('*') if p.is_file()
                  and p.suffix in ('.py', '.json', '.md', '.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif', '.yaml', '.yml')
                  and '__pycache__' not in p.parts]
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        for path in sorted(files):
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('Deployment source cannot contain symlinks outside its code root')
            data = path.read_bytes()
            member = tarfile.TarInfo(path.relative_to(root).as_posix())
            member.size = len(data); member.mode = 0o644; member.mtime = SOURCE_EPOCH
            archive.addfile(member, io.BytesIO(data))
    return gzip.compress(stream.getvalue(), mtime=0)


class Shell:
    """Small acknowledged commands work on normal SSH and numbered PTY gateways."""
    def __init__(self, connection, progress, cancel):
        self.connection, self.progress, self.cancel = connection, progress, cancel

    def run(self, command, *, timeout=120):
        from .client import RemoteError
        if self.cancel.is_set():
            raise RemoteError('环境准备已取消。', code='remote_cancelled')
        marker = 'BP_SETUP_' + uuid.uuid4().hex
        # A subshell confines cd/env/exit and redirects only this command's output.
        self.connection.channel.sendall(('( ' + command + ' ) 2>&1; printf "\\n' + marker + ' %s\\n" "$?"\n').encode())
        end = time.monotonic() + timeout
        output = []
        while time.monotonic() < end:
            if self.cancel.is_set():
                self.connection.close()
                raise RemoteError('环境准备已取消；重新连接可重试。', code='remote_cancelled')
            try:
                line = self.connection._line(min(end, time.monotonic() + 1))
            except TimeoutError:
                continue
            match = re.search(re.escape(marker) + r' (\d+)\s*$', line)
            if match:
                if int(match[1]):
                    raise RemoteError('服务器环境准备失败：\n' + '\n'.join(output[-12:]), code='remote_setup_failed')
                return '\n'.join(output)
            if line.strip():
                output.append(line[-2000:]); output = output[-80:]
                self.progress(line[-2000:])
        raise RemoteError('服务器环境准备超时；可重新连接重试。', code='remote_setup_failed')

    def upload(self, path, data):
        """Idempotent indexed chunks, then a full checksum before use."""
        target = shlex.quote(path)
        encoded = base64.b64encode(data).decode()
        chunks = [encoded[i:i+768] for i in range(0, len(encoded), 768)]
        staging = path + '.parts-' + uuid.uuid4().hex
        self.run('mkdir -m 700 -- ' + shlex.quote(staging))
        for index, chunk in enumerate(chunks):
            self.run('printf %s ' + shlex.quote(chunk) + ' > ' + shlex.quote(staging + f'/{index:08d}'))
            if index % 100 == 0:
                self.progress(f'上传程序 {index + 1}/{len(chunks)}')
        # No recursive cleanup or executable unpack until exact content verified.
        self.run('cat ' + shlex.quote(staging) + '/* | base64 -d > ' + target +
                 ' && printf %s ' + shlex.quote(hashlib.sha256(data).hexdigest() + '  ' + path + '\n') +
                 ' | sha256sum -c - && rm -- ' + shlex.quote(staging) + '/* && rmdir -- ' + shlex.quote(staging))


def locate(connection, profile, progress, cancel, expected=None):
    """Read one server-owned receipt; never build/upload code or repair packages."""
    from .client import RemoteError
    from .installation import MAX_RECEIPT_BYTES, validate
    shell = Shell(connection, progress, cancel)
    progress('读取服务端安装登记')
    base = profile.get('managed_root')
    if not base:
        home = shell.run('printf "\\nBP_HOME=%s\\n" "$HOME"')
        found = re.search(r'BP_HOME=(/[^\r\n]*)', home)
        if not found:
            raise RemoteError('无法确定服务器用户目录。', code='server_not_installed')
        base = found[1].rstrip('/') + '/.local/share/operon'
    receipt = base + '/server.json'
    q = shlex.quote
    output = shell.run('if test -f ' + q(receipt) + '; then printf "\\nBP_SERVER_DOCUMENT\\n"; head -c '
                       + str(MAX_RECEIPT_BYTES + 1) + ' -- ' + q(receipt)
                       + '; printf "\\nBP_SERVER_END\\n"; fi')
    if 'BP_SERVER_DOCUMENT\n' not in output:
        raise RemoteError('未找到服务端安装登记。请先选择“安装 / 升级服务端”，或登记已有安装后重连。', code='server_not_installed')
    document = output.split('BP_SERVER_DOCUMENT\n', 1)[1].rsplit('\nBP_SERVER_END', 1)[0]
    try:
        if len(document.encode('utf-8')) > MAX_RECEIPT_BYTES:
            raise ValueError('Server installation document is too large')
        value = validate(json.loads(document))
    except (ValueError, TypeError, KeyError) as exc:
        raise RemoteError('服务端安装登记无效，请重新登记或修复安装。', code='server_installation_invalid') from exc
    build = value.get('build')
    if expected is not None:
        from operon.build_identity import matches
        if not matches(expected, build):
            raise RemoteError('服务端代码或算子库与桌面端不一致；请安装 / 升级服务端后再连接。',
                              code='stale_build')
    progress('复用已安装的服务端；不上传程序、不安装依赖')
    return {**profile, 'app_dir': value['app_dir'], 'python': value['python'],
            'workspace': profile.get('workspace') or value['workspace'], 'managed_root': base,
            'installation_id': value['server_id'], 'build': build}


RETIRE_SCRIPT = r"""
import glob, hashlib, json, os, shutil, signal, socket, struct, sys, tempfile, time
home = os.path.realpath(sys.argv[1])
force = len(sys.argv) > 2 and sys.argv[2] == "force"
uid = os.getuid()
directory = os.path.join(tempfile.gettempdir(), f"operon-ssh-{uid}")
ACTIVE = {"queued", "preparing", "uploading", "running", "waiting_connection", "recovery_required"}


def args_of(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as stream:
            return [os.fsdecode(value) for value in stream.read().split(b"\x00") if value]
    except OSError:
        return []


def workspace_of(args):
    for index, value in enumerate(args):
        if value == "--workspace" and index + 1 < len(args):
            return args[index + 1]
        if value.startswith("--workspace="):
            return value.split("=", 1)[1]
    return None


def request(address, payload):
    client = socket.socket(socket.AF_UNIX)
    client.settimeout(8)
    try:
        client.connect(address)
        body = json.dumps(payload, ensure_ascii=False).encode()
        client.sendall(struct.pack("!Q", len(body)) + body)
        header = b""
        while len(header) < 8:
            block = client.recv(8 - len(header))
            if not block:
                raise OSError("short response header")
            header += block
        size = struct.unpack("!Q", header)[0]
        data = b""
        while len(data) < size:
            block = client.recv(size - len(data))
            if not block:
                raise OSError("short response body")
            data += block
        return json.loads(data)
    finally:
        client.close()


def alive(pid):
    return os.path.exists(f"/proc/{pid}")


def wait_gone(pid, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not alive(pid):
            return True
        time.sleep(.1)
    return not alive(pid)


def kill(pid, sig):
    try:
        os.killpg(os.getpgid(pid), sig)
    except OSError:
        try:
            os.kill(pid, sig)
        except OSError:
            pass


def cancel(address, pid, workspace, forced):
    try:
        history = request(address, {"id": os.urandom(8).hex(), "method": "history", "params": {}})
        jobs = history.get("value") or []
        for job in jobs if isinstance(jobs, list) else []:
            if isinstance(job, dict) and job.get("status") in ACTIVE and job.get("id"):
                try:
                    request(address, {"id": os.urandom(8).hex(), "method": "cancel",
                                      "params": {"job_id": job["id"]}})
                except OSError:
                    pass
        time.sleep(.4)
        response = request(address, {"id": os.urandom(8).hex(), "method": "retire_if_idle", "params": {}})
        value = response.get("value") or {}
        return bool(response.get("ok") and value.get("retired"))
    except OSError:
        return False


retired, forced, blocked, skipped, pools = [], [], [], [], []
for entry in os.listdir("/proc"):
    if not entry.isdigit() or int(entry) == os.getpid():
        continue
    pid = int(entry)
    args = args_of(pid)
    joined = " ".join(args)
    if "operon.remote.server" not in joined and "biopipe.remote.server" not in joined:
        continue
    workspace = workspace_of(args)
    if not workspace:
        skipped.append({"pid": pid, "reason": "workspace missing"})
        continue
    try:
        cwd = os.path.realpath(f"/proc/{pid}/cwd")
    except OSError:
        continue
    if not (cwd == home or cwd.startswith(home + os.sep)):
        continue
    address = os.path.join(directory, hashlib.sha256(os.path.realpath(workspace).encode()).hexdigest()[:24] + ".sock")
    if not os.path.exists(address):
        if not force:
            skipped.append({"pid": pid, "workspace": workspace, "reason": "socket missing"})
            continue
        kill(pid, signal.SIGTERM)
        if wait_gone(pid, 5) or (kill(pid, signal.SIGKILL) or wait_gone(pid, 3)):
            forced.append({"pid": pid, "workspace": workspace, "reason": "no control socket"})
        else:
            blocked.append({"pid": pid, "workspace": workspace, "reason": "server did not exit"})
        continue
    try:
        response = request(address, {"id": os.urandom(8).hex(), "method": "retire_if_idle", "params": {}})
    except OSError as exc:
        if not force:
            blocked.append({"pid": pid, "workspace": workspace, "reason": f"control socket: {exc}"})
            continue
        response = {"ok": False, "value": {"reason": f"control socket: {exc}"}}
    value = response.get("value") or {}
    if response.get("ok") and value.get("retired"):
        retired.append({"pid": pid, "workspace": workspace})
        continue
    if not force:
        blocked.append({"pid": pid, "workspace": workspace,
                        "reason": response.get("error") or value.get("reason") or "retire refused"})
        continue
    if cancel(address, pid, workspace, forced):
        retired.append({"pid": pid, "workspace": workspace, "reason": "tasks cancelled"})
        continue
    kill(pid, signal.SIGTERM)
    if wait_gone(pid, 6) or (kill(pid, signal.SIGKILL) or wait_gone(pid, 3)):
        forced.append({"pid": pid, "workspace": workspace, "reason": "force-cancelled"})
    else:
        blocked.append({"pid": pid, "workspace": workspace, "reason": "server did not exit"})
if force:
    for family in (".operon", ".biopipe"):
        pattern = os.path.join(home, family, "admission", "*", "managed-pool", "instance.json")
        for path in glob.glob(pattern):
            try:
                record = json.loads(open(path, encoding="utf-8").read())
                pid = int(record.get("pid") or 0)
            except (OSError, ValueError, TypeError):
                continue
            if not pid or pid == os.getpid() or not alive(pid):
                continue
            kill(pid, signal.SIGTERM)
            if not (wait_gone(pid, 6) or (kill(pid, signal.SIGKILL) or wait_gone(pid, 3))):
                blocked.append({"pid": pid, "reason": "shared pool did not exit"})
            else:
                pools.append({"pid": pid, "record": path})
                shutil.rmtree(os.path.dirname(path), ignore_errors=True)
print("BP_RETIRE_RESULT " + json.dumps({"retired": retired, "forced": forced, "blocked": blocked,
                                         "skipped": skipped, "pools": pools},
                                         ensure_ascii=False, separators=(",", ":")))
"""


def _retire_old_servers(shell, home, managed, progress, force=False):
    """Stop idle daemons before immutable replacement; active work blocks the upgrade."""
    from .client import RemoteError
    q = shlex.quote
    path = managed + '/retire-' + uuid.uuid4().hex + '.py'
    shell.upload(path, RETIRE_SCRIPT.encode())
    try:
        output = shell.run(
            'if command -v python3 >/dev/null 2>&1; then python3 ' + q(path) + ' ' + q(home) + (' force' if force else '') +
            '; else printf "BP_RETIRE_RESULT {\"retired\":[],\"forced\":[],\"blocked\":[],\"skipped\":[],\"pools\":[]}\n"; fi',
            timeout=90)
    except RemoteError as exc:
        raise RemoteError('无法检查旧版服务端；为避免覆盖运行中的任务，升级已停止。\n' + str(exc),
                          code='remote_upgrade_blocked') from exc
    finally:
        try:
            shell.run('rm -f -- ' + q(path))
        except RemoteError:
            pass
    match = re.search(r'BP_RETIRE_RESULT (\{.*\})', output, re.S)
    if not match:
        raise RemoteError('旧版服务端状态无法确认；升级已停止，未修改任何文件。', code='remote_upgrade_blocked')
    try:
        result = json.loads(match.group(1))
    except ValueError as exc:
        raise RemoteError('旧版服务端状态无效；升级已停止，未修改任何文件。', code='remote_upgrade_blocked') from exc
    blocked = result.get('blocked') or []
    if blocked:
        detail = '; '.join(f"PID {item.get('pid')}: {item.get('reason')}" for item in blocked[:4])
        message = ('强制升级未能停止旧版服务端。' if force else
                   '旧版服务端仍有任务或无法安全停止，升级已取消。请等待任务结束后重试。')
        raise RemoteError(message + detail, code='remote_upgrade_blocked')
    if result.get('retired'):
        progress('已释放 %d 个旧版服务端' % len(result['retired']))
    if result.get('forced'):
        progress('已强制停止 %d 个旧版服务端' % len(result['forced']))
    if result.get('pools'):
        progress('已关闭 %d 个旧版共享池' % len(result['pools']))


CLEANUP_SCRIPT = r"""
import glob, os, shutil, sys

managed, code, env, log = sys.argv[1:5]
keep = {os.path.basename(code), os.path.basename(env), os.path.basename(log)}
for name in os.listdir(managed):
    if name in keep:
        continue
    if not name.startswith(("code-", "env-", "source-", "install-", "retire-", "setup-")):
        continue
    target = os.path.join(managed, name)
    try:
        if os.path.isdir(target) and not os.path.islink(target):
            shutil.rmtree(target, ignore_errors=True)
        else:
            os.unlink(target)
    except OSError:
        pass
print("BP_CLEANUP_OK")
"""


def application_root() -> Path:
    """Locate the shipped application tree, never the interpreter's site-packages.

    The desktop runtime imports `operon` from
    `runtime/python/Lib/site-packages`, so `Path(__file__).parents[2]` points at
    site-packages when the package is imported there. `code_root()` already
    knows how to find the version directory that holds `operon` and `src/task`.
    """
    try:
        from operon.environments import code_root
        return Path(code_root())
    except Exception:
        return Path(__file__).resolve().parents[2]


def provision(connection, profile, progress, cancel, root=None, expected=None, force=False):
    from .client import RemoteError
    shell = Shell(connection, progress, cancel)
    progress('检查服务器系统与部署目录')
    probe = shell.run('printf "\\nBP_SYSTEM=%s\\nBP_ARCH=%s\\nBP_HOME=%s\\n" "$(uname -s)" "$(uname -m)" "$HOME"; for bp_tool in bash tar base64 sha256sum flock tee; do command -v "$bp_tool" || exit 1; done')
    if not re.search(r'BP_SYSTEM=Linux\s*(?:\n|$)', probe) or not re.search(r'BP_ARCH=x86_64\s*(?:\n|$)', probe):
        raise RemoteError('自动部署目前支持 Linux x86_64；其他系统请使用已有环境。')
    home = re.search(r'BP_HOME=(/[^\r\n]*)', probe)
    if not home:
        raise RemoteError('无法确定服务器用户目录。')
    base = profile.get('managed_root') or home[1].rstrip('/') + '/.local/share/operon'
    q = shlex.quote
    shell.run('umask 077; mkdir -p -- ' + q(base) + '; test -w ' + q(base))
    # Own only a dedicated namespace, never an existing arbitrary installation.
    managed = base + '/managed-v1'
    shell.run('umask 077; mkdir -p -- ' + q(managed))
    _retire_old_servers(shell, home[1].rstrip('/'), managed, progress, force=force)
    data = source_archive(root or application_root())
    digest = hashlib.sha256(data).hexdigest()
    from operon.build_identity import build_identity
    identity = build_identity(root or application_root(), source_sha256=digest)
    if expected is not None and expected.get('build_id') != identity['build_id']:
        raise RemoteError('本地程序在准备期间发生变化，请重试。', code='build_changed')
    code = managed + '/code-' + digest[:20]
    archive = managed + '/source-' + digest[:20] + '.tar.gz'
    log = managed + '/setup-' + digest[:20] + '.log'
    progress('服务端安装日志：' + log)
    shell.run('umask 077; printf "\\n%s\\n" ' + q('Operon deployment ' + digest) + ' >> ' + q(log))
    present = shell.run('if test -f ' + q(code + '/.source-sha') + '; then cat ' + q(code + '/.source-sha') + '; fi')
    if digest not in present:
        progress('上传与桌面端匹配的 Operon 程序')
        shell.upload(archive, data)
        # Concurrent publishers serialize extraction; published code stays immutable.
        extract = ('flock ' + q(managed + '/publish.lock') + ' bash -c ' + q(
            'set -eu; mkdir -p -- ' + q(code) + '; tar -xzf ' + q(archive) + ' -C ' + q(code) +
            '; printf %s ' + q(digest) + ' > ' + q(code + '/.source-sha')))
        shell.run('bash -o pipefail -c ' + q(extract + ' 2>&1 | tee -a ' + q(log)))
    env = managed + '/env-' + digest[:20]
    python = env + '/bin/python'
    workspace = profile.get('workspace') or base + '/workspace'
    installer = code + '/operon/remote/install_linux.py'
    # micromamba is static: the server does not need Python, Conda, sudo or a compiler.
    # Some package post-link hooks require the executable basename `micromamba`.
    mamba = managed + '/tools/micromamba-2.10.0/bin/micromamba'
    install = f'''set -eu
umask 077
unset CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_SHLVL CONDA_PROMPT_MODIFIER CONDA_EXE CONDA_PYTHON_EXE MAMBA_EXE MAMBA_ROOT_PREFIX _CE_CONDA _CE_M
mkdir -p -- {q(mamba.rsplit('/', 1)[0])}
if ! printf '%s  %s\\n' {q(MAMBA_SHA)} {q(mamba)} | sha256sum -c - >/dev/null 2>&1; then
  echo 'Downloading the verified environment manager'
  if command -v curl >/dev/null; then
    for bp_attempt in 1 2 3; do
      curl --fail --location --continue-at - --connect-timeout 30 --max-time 600 --silent --show-error {q(MAMBA_URL)} -o {q(mamba + '.download')} && break
      echo "Download interrupted; resuming attempt $bp_attempt"
    done
  elif command -v wget >/dev/null; then wget --continue --timeout=30 --tries=3 -O {q(mamba + '.download')} {q(MAMBA_URL)};
  else echo 'Install curl or wget to download the managed runtime'; exit 1; fi
  printf '%s  %s\\n' {q(MAMBA_ARCHIVE_SHA)} {q(mamba + '.download')} | sha256sum -c -
  tar -xOjf {q(mamba + '.download')} bin/micromamba > {q(mamba + '.new')}
  printf '%s  %s\\n' {q(MAMBA_SHA)} {q(mamba + '.new')} | sha256sum -c -
  chmod 700 {q(mamba + '.new')}; mv -- {q(mamba + '.new')} {q(mamba)}
fi
export MAMBA_ROOT_PREFIX={q(managed + '/mamba-cache')}
if ! test -f {q(env + '/operon-ready.json')} || ! test -x {q(env + '/bin/bwa')} || ! test -x {q(env + '/bin/samtools')} || test "$(cat {q(env + '/.operon-conda-packages')} 2>/dev/null)" != {q(CONDA_SPECS)}; then
  echo 'Preparing Python and native Hi-C dependencies'
  bp_action=create; bp_repair=''
  if test -d {q(env + '/conda-meta')}; then
    bp_action=install
    if ! test -x {q(env + '/bin/bwa')} || ! test -x {q(env + '/bin/samtools')} || ! test -x {q(python)}; then bp_repair=--force-reinstall; fi
  fi
  {q(mamba)} --no-rc "$bp_action" $bp_repair -y -p {q(env)} --override-channels -c https://conda.anaconda.org/conda-forge -c https://conda.anaconda.org/bioconda --strict-channel-priority {CONDA_SPECS}
  printf '%s' {q(CONDA_SPECS)} > {q(env + '/.operon-conda-packages')}
fi
export PATH={q(env + '/bin')}:"$PATH"
export PYTHONNOUSERSITE=1
unset PYTHONPATH PYTHONHOME
export OPERON_MAMBA={q(mamba)}
{q(python)} -I {q(installer)} --code {q(code)} --digest {q(digest)} --workspace {q(workspace)} --build {q(json.dumps(identity, separators=(',', ':')))}
'''
    # Redirect noisy resolver output on the server, but show bounded live lines.
    # The lock prevents two desktops from mutating the same target environment.
    script = managed + '/install-' + uuid.uuid4().hex + '.sh'
    shell.upload(script, install.encode())
    progress('检查并补齐 Python、Operon 与 Hi-C 依赖（首次可能需要数分钟）')
    # Closing SSH requests installer shutdown; an outstanding child may finish.
    command = ('umask 077; flock ' + q(managed + '/environment.lock') + ' bash ' + q(script) +
               ' >> ' + q(log) + ' 2>&1 & bp_setup_pid=$!; ' +
               'trap \'kill "$bp_setup_pid" 2>/dev/null || true\' HUP INT TERM; ' +
               'while kill -0 "$bp_setup_pid" 2>/dev/null; do tail -n 1 ' + q(log) +
               '; printf "\\n"; sleep 2; done; wait "$bp_setup_pid"; bp_status=$?; tail -n 12 ' + q(log) + '; exit "$bp_status"')
    try:
        shell.run(command, timeout=3600)
    except RemoteError as exc:
        raise RemoteError(str(exc) + '\n完整安装日志：' + log, code=exc.code) from exc
    # Publish a stable, server-owned entry point only after successful setup.
    # Other desktop versions read this document without uploading their code.
    shell.run(q(python) + ' -I -m operon.remote.installation register --base ' + q(base)
              + ' --app-dir ' + q(code) + ' --workspace ' + q(workspace)
              + ' --source-sha256 ' + q(digest)
              + ' --build ' + q(json.dumps(identity, separators=(',', ':'))))
    progress('清理旧的程序与运行环境')
    cleanup = managed + '/cleanup-' + uuid.uuid4().hex + '.py'
    shell.upload(cleanup, CLEANUP_SCRIPT.encode())
    try:
        shell.run(q(python) + ' -I ' + q(cleanup) + ' ' + q(managed) + ' ' + q(code) + ' ' + q(env) + ' ' + q(log),
                  timeout=300)
    finally:
        try:
            shell.run('rm -f -- ' + q(cleanup))
        except RemoteError:
            pass
    progress('环境就绪，正在连接运行服务')
    return {**profile, 'python': python, 'app_dir': code, 'workspace': workspace,
            'setup_log': log, 'managed_root': base, 'build': identity}
