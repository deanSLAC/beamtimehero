"""Send commands to a running SPEC session via GNU screen.

SPEC runs in a screen session named 'spec'. Commands are injected using
screen's 'stuff' mechanism, which types characters into the session.
Only whitelisted commands are allowed.
"""
import logging
import subprocess

logger = logging.getLogger(__name__)

SCREEN_SESSION = "spec"

# Whitelisted commands — no arguments allowed
ALLOWED_COMMANDS = {
    "wa": "wa",           # print all motor positions
    "pwd": "pwd",         # print current working directory
    "fon": "fon",         # show open data/log files
    "get_S": "p S",       # print counter array values
}


def send_spec_command(command: str) -> str:
    """Send a whitelisted command to the SPEC screen session.

    Args:
        command: One of the allowed command names (wa, pwd, fon, get_S).

    Returns:
        Status message. The actual output appears in the SPEC log file.

    Raises:
        ValueError: If the command is not whitelisted.
        RuntimeError: If the screen session is not available.
    """
    if command not in ALLOWED_COMMANDS:
        allowed = ", ".join(sorted(ALLOWED_COMMANDS.keys()))
        raise ValueError(
            f"Command '{command}' is not allowed. "
            f"Allowed commands: {allowed}"
        )

    spec_cmd = ALLOWED_COMMANDS[command]

    # Check if the screen session exists
    result = subprocess.run(
        ["screen", "-list"],
        capture_output=True, text=True,
    )
    if SCREEN_SESSION not in result.stdout:
        raise RuntimeError(
            f"SPEC screen session '{SCREEN_SESSION}' is not running. "
            "SPEC may not be active on this machine."
        )

    # Send the command to the screen session
    subprocess.run(
        ["screen", "-S", SCREEN_SESSION, "-X", "stuff", f"{spec_cmd}\n"],
        capture_output=True, text=True, check=True,
    )

    logger.info("Sent SPEC command: %s (as '%s')", command, spec_cmd)
    return (
        f"Command '{spec_cmd}' sent to SPEC. "
        "Check the log file for output (use get-latest-log-entries)."
    )
