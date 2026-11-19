# Operon Studio 5.7.6

Environment preparation now refuses impossible work instead of failing late, and the
remaining queue and progress defects reported against 5.7.5 are fixed.

## Fixed

- **F-69 Platform gate.** `environment_install.prepare()` checks the new
  `platforms` field of an environment manifest before it downloads anything.
  Environments whose command line tools only exist for Linux and macOS are
  rejected on Windows within a second with a readable reason, and the reason is
  stored in `.operon-environment-errors/<name>.json` so the card shows it.
- **F-70 Readable conda failures.** When micromamba reports
  `* does not exist` for several packages, the error text now lists the missing
  packages instead of the raw solver dump.
- **F-71 Long install paths break pip.** On Windows a staging path longer than
  200 characters was passed to pip with the `\\?\` prefix, and pip built
  `../../Scripts/<name>` from it, which raised
  `OSError: [Errno 22] Invalid argument`. Such paths now fall back to the plain
  filesystem path, which is what fixed the `esmfold` environment.
- **F-72 Interrupted installations stay "installing" forever.** A progress file
  whose active phase is older than three minutes is reaped: it is rewritten as
  `failed` with `上次安装已中断（安装进程已退出），请重新准备该环境。`, and
  cancelling such an environment reports what happened instead of
  `没有正在进行的准备任务。`
- **F-73 A broken job could stop the queue.** The drainer now survives any
  exception raised by a job, and the queue restarts itself when items wait and
  no worker thread is alive.
- **F-75 The bioconda channel was skipped for most environments.** The channel
  list used to be guessed from a hard coded list of package name fragments, so
  environments such as `rna`, `hic` and `genomics` were solved against
  conda-forge only and failed with `does not exist`. Any environment that
  declares conda packages now gets conda-forge followed by bioconda, with
  strict channel priority keeping conda-forge first.
- **F-76 The log drawer opened off screen.** Clicking 查看日志 did open the
  drawer, but it was rendered after eighteen environment cards inside the
  scrolling panel, so nothing appeared to happen. It is now a fixed overlay in
  the lower right corner, and an environment without log output says
  `该环境还没有日志输出。`.
- **F-74 Execution location was forgotten.** The runtime panel remembers the
  selected execution location, so after a refresh the panel no longer silently
  falls back to the local machine.

- **F-77 `hic` could not finish its pip step.** `cooltools==0.6.1` has no
  binary wheel, and building it from source fails with
  `Cython.Compiler.Errors.CompileError: cooltools/lib/_numutils.pyx` because the
  isolated environment has no C toolchain. The pin is gone; `cooler` and
  `pairtools` still cover the Hi-C matrix work.
- **F-78 `genomics` could never solve.** Every `flye 2.9.3` build requires
  Python 3.10 or older, which conflicts with the Python 3.11 that every other
  command line tool in that environment needs. The pin is gone.

## Changed

- Environment cards show a `当前系统不支持` badge, disable `准备` and `重新准备`,
  and explain the platform restriction in the tooltip.
- Dependency cards report `x/y 已安装`, and every dependency row shows whether
  that package is installed and offers `安装` or `重新安装`.

## Library 1.1.4

`environment_assignments.json` and the environment manifests are unchanged apart
from the new `platforms` field; the library version only marks the release that
ships it.
