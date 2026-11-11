# Run your first Operon workflow in 10 minutes

This is a click-by-click guide. You will do one thing: run a tiny PCA on a small table to prove the installation works.

You do not need Python, Conda or an AI account. The data are made up. The result only checks the workflow; it is not a biological finding.

## Before you start

- Windows 10 or 11, ideally 8 GB of RAM.
- Internet access. The first environment check may download a few scientific packages.
- A writable install folder such as `D:\Operon Studio`. Do not use `C:\Program Files` or a folder that needs administrator rights.

## Step 1: Install

1. Open [Releases](https://github.com/lovegavin/Operon/releases/latest).
2. Download **Operon_Setup.exe**. Do not download a file whose name contains `Server` or `Library`.
3. Double-click it. If Windows shows a blue warning, choose **More info** → **Run anyway**.
4. Set the install folder to `D:\Operon Studio` and click **Install**.
5. Leave **Open Operon** checked and click **Finish**.

The first launch can be slow. Wait until the window is fully visible. The status area shows when the backend and frontend are ready.

## Step 2: Make a tiny table

Create a text file named `matrix.csv` with exactly these seven lines:

```csv
gene_a,gene_b,gene_c
1,2,3
2,3,4
4,1,2
3,4,1
5,2,6
6,5,3
```

The first line is the header; the other six lines are numbers. Use ordinary commas.

## Step 3: Load the table

1. In Operon Studio, click **Add input data**.
2. Select `matrix.csv`.
3. Choose **CsvReader**.
4. Enter dimensions `sample, feature` (English comma, no spaces).
5. Keep labels on automatic and enable the header row.
6. Confirm. An input node appears on the canvas.

## Step 4: Add PCA

1. Search the operator library for **PCA**.
2. Drag **PCA** onto the canvas, to the right of the input node.
3. Drag from the input node's output dot to PCA's input dot.
4. Double-click PCA:
   - dimension: `feature`;
   - number of components: `2`;
   - leave the other values at their defaults.
5. Confirm.

## Step 5: Check the environment and run

1. Open **Run settings** (top right).
2. Choose **Local** as the execution target.
3. Click **Check environment**.
4. If packages are missing, click **Prepare environment / Install dependencies**, wait, then check again.
5. Close the settings and click **Run**.
6. Wait for **Completed**, then open **Run history** → **View results**.

You should see a completed task with PCA output and two components. This example does not draw a scatter plot automatically. To make a figure, add a plotting operator after PCA.

## Step 6 (optional): Run on a Linux server

Skip this unless you actually have a Linux server.

1. Download **Operon-4.0.3-Server.zip** from Releases and upload it to the server.
2. On the server:

```sh
unzip Operon-4.0.3-Server.zip
cd Operon-4.0.3-Server
bash install.sh --prefix "$HOME/operon" --result "$PWD/server-install.json"
```

3. The result prints the real `install_dir`, `workspace` and `command`. Use those paths in place of the examples:

```sh
"$HOME/operon/bin/operon" --version
"$HOME/operon/bin/operon" workflow lint "$HOME/operon/workspace/quickstart/workflow.yaml"
"$HOME/operon/bin/operon" run "$HOME/operon/workspace/quickstart/workflow.yaml" --progress --brief
```

See the [server installation guide](docs/command_line_installation.md#linux-server) for the complete version.

## If something goes wrong

- **Blank window**: wait 1–2 minutes, then fully quit and reopen. Do not run several copies at once.
- **Environment check fails**: confirm internet access, then click **Prepare environment**. Behind a corporate proxy, configure the system proxy first.
- **Install folder is not writable**: use a normal folder such as `D:\Operon Studio`, not `C:\Program Files`.
- **Uninstall**: use Windows Apps, or run `Operon_Uninstall.exe` in the install folder. Operon 4.0.3 keeps the workspace and results under `<install folder>\workspace`; delete them manually only when you no longer need them.
- **Logs**: `%USERPROFILE%\.operon\profiles\<profile-id>\logs\desktop-YYYYMMDD.log`.

## Next

- [Documentation](docs/README.md)
- [Windows Setup and isolated installs](docs/windows_setup.md)
- [Command line and Linux server](docs/command_line_installation.md)
- [Workflow YAML](docs/workflow_yaml_v3.md)
- [中文快速开始](QUICKSTART.zh.md)

Operon is Apache-2.0 licensed: you may use, modify and redistribute it. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
