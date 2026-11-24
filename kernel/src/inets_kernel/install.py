"""``python -m inets_kernel.install`` puts the kernel where Jupyter looks for kernels, so
that "Interaction nets" can be chosen for a notebook.

    python -m inets_kernel.install [--user | --sys-prefix | --prefix PATH]

The default is Jupyter's own choice, which may need rights to write system directories;
``--sys-prefix`` installs into the current Python environment and ``--user`` into the
user's Jupyter directory. ``jupyter kernelspec uninstall inets`` removes it.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

from jupyter_client.kernelspec import KernelSpecManager

KERNEL_NAME = "inets"
SPEC = Path(__file__).parent / "kernelspec" / "kernel.json"


def install(user=False, prefix=None):
    """Installs the kernel's description and returns where it went. The description
    names the Python that is running this, so the kernel starts in the same environment."""
    spec = json.loads(SPEC.read_text())
    spec["argv"][0] = sys.executable
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / KERNEL_NAME
        target.mkdir()
        (target / "kernel.json").write_text(json.dumps(spec, indent=2))
        return KernelSpecManager().install_kernel_spec(str(target), kernel_name=KERNEL_NAME, user=user, prefix=prefix)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install the Interaction nets kernel for Jupyter")
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--user", action="store_true", help="install into the user's Jupyter directory")
    where.add_argument("--sys-prefix", action="store_true", help="install into this Python environment")
    where.add_argument("--prefix", default=None, help="install under this directory")
    args = parser.parse_args(argv)
    prefix = sys.prefix if args.sys_prefix else args.prefix
    print("installed the kernel in", install(user=args.user, prefix=prefix))


if __name__ == "__main__":
    main()
