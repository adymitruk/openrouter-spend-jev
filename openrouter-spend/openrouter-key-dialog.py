#!/usr/bin/env python3
"""Open a foot terminal asking for the OpenRouter management key.
Writes the key to the state dir and persists to shell.json."""

import os
import sys
import subprocess
import tempfile

WORK_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    # Write a small prompt script that reads the key and prints it to a file
    outpath = tempfile.mktemp(prefix="orkey-", suffix=".out")

    # Masked input: echo one '*' per character so the user can see the paste
    # landed, without showing the key itself.
    prompt_script = r'''#!/usr/bin/env bash
echo -n "OpenRouter key (sk-or-...): "
KEY=""
while IFS= read -rs -n1 c; do
  if [[ -z $c ]]; then break; fi
  if [[ $c == $'\x7f' ]]; then
    if [[ -n $KEY ]]; then KEY=${KEY%?}; echo -ne '\b \b'; fi
  else
    KEY+=$c
    echo -n '*'
  fi
done
echo
echo "$KEY" > "''' + outpath + '"'

    script = tempfile.NamedTemporaryFile(mode="w", delete=False, prefix="orkey-", suffix=".sh")
    script.write(prompt_script + "\n")
    script.close()
    os.chmod(script.name, 0o700)

    subprocess.run(
        ["foot", script.name],
        timeout=120,
        env={**os.environ, "DISPLAY": "", "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", "wayland-0")}
    )

    os.unlink(script.name)

    try:
        with open(outpath) as f:
            k = f.read().strip()
    except (FileNotFoundError, PermissionError):
        k = ""
    finally:
        try:
            os.unlink(outpath)
        except FileNotFoundError:
            pass

    if not k:
        sys.exit(1)

    # Print key to stdout for QML capture
    print(k)

    # Write to state dir
    helper = os.path.join(WORK_DIR, "openrouter-helper.py")
    subprocess.run([sys.executable, helper, "write-key", "openrouter-key", k],
                   capture_output=True)

    # Persist to shell.json (survives reboot)
    subprocess.run(["omarchy", "bar", "set", "adam.openrouter-spend", "openrouterKey", k],
                   capture_output=True)

if __name__ == "__main__":
    main()