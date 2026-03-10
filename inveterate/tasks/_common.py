import logging
import re
import shlex
import subprocess

logger = logging.getLogger("inveterate.tasks")

MAX_POLL_SECONDS = 600  # 10 minute timeout for Proxmox polling loops

# Snippets directory on Proxmox nodes (local storage default path)
_SNIPPETS_DIR = "/var/lib/vz/snippets"
_SSH_OPTS = [
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=10",
    "-o", "LogLevel=ERROR",
]

# Only allow safe characters in snippet filenames (alphanumeric, hyphen, underscore, dot)
_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def _validate_snippet_filename(filename: str) -> None:
    """Raise ValueError if filename contains unsafe characters or path traversal."""
    if not filename or not _SAFE_FILENAME_RE.match(filename):
        raise ValueError(f"Invalid snippet filename: {filename!r}")
    if ".." in filename or "/" in filename:
        raise ValueError(f"Path traversal in snippet filename: {filename!r}")


def _get_node_ip(proxmox, node_name):
    """Resolve a Proxmox node name to its cluster IP via the cluster status API."""
    for item in proxmox.cluster.status.get():
        if item.get("type") == "node" and item.get("name") == node_name:
            return item["ip"]
    raise RuntimeError(f"Cannot resolve IP for Proxmox node '{node_name}'")


def write_snippet(proxmox, node_name, filename, content):
    """Write a cloud-init snippet to a Proxmox node via SSH.

    The Proxmox upload API does not support the 'snippets' content type,
    so we write the file directly via SSH to the node's local storage.
    """
    _validate_snippet_filename(filename)
    node_ip = _get_node_ip(proxmox, node_name)
    remote_path = f"{_SNIPPETS_DIR}/{filename}"
    safe_path = shlex.quote(remote_path)
    cmd = ["ssh", *_SSH_OPTS, f"root@{node_ip}", f"cat > {safe_path} && chmod 600 {safe_path}"]
    result = subprocess.run(cmd, input=content.encode(), capture_output=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to write snippet to {node_name}:{remote_path} — "
            f"ssh exit {result.returncode}: {result.stderr.decode().strip()}"
        )
    logger.info("Wrote cloud-init snippet %s to node %s", filename, node_name)


def delete_snippet(proxmox, node_name, filename):
    """Delete a cloud-init snippet from a Proxmox node via SSH."""
    _validate_snippet_filename(filename)
    node_ip = _get_node_ip(proxmox, node_name)
    remote_path = f"{_SNIPPETS_DIR}/{filename}"
    safe_path = shlex.quote(remote_path)
    cmd = ["ssh", *_SSH_OPTS, f"root@{node_ip}", f"rm -f {safe_path}"]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    if result.returncode != 0:
        logger.warning(
            "Failed to delete snippet %s from node %s: %s",
            filename, node_name, result.stderr.decode().strip(),
        )
    else:
        logger.info("Deleted cloud-init snippet %s from node %s", filename, node_name)
