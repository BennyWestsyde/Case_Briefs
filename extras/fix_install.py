import sys
import subprocess


def check_virtualenv():
    return sys.prefix != sys.base_prefix


def enable_virtualenv():
    if not check_virtualenv():
        print("This script must be run inside a virtual environment.")
        sys.exit(1)


def upgrade_pip():
    if check_virtualenv():
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"]
        )


def reinstall_packages():
    return_code = subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "-r",
            "requirements.txt",
        ]
    )
    return return_code == 0


if __name__ == "__main__":
    enable_virtualenv()
    upgrade_pip()
    if reinstall_packages():
        print("All packages reinstalled successfully.")
    else:
        print("Failed to reinstall packages.")
