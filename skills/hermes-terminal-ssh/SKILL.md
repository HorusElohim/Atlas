---
name: hermes-terminal-ssh
description: Configure Hermes terminal SSH settings for remote hosts.
---
# Hermes Terminal SSH Configuration

This skill covers setting up SSH for the Hermes terminal to connect to remote hosts.

## Steps

1. Determine the remote host IP or hostname and the username for SSH access.
2. Set the TERMINAL_SSH_HOST config: `hermes config set TERMINAL_SSH_HOST <host>`
3. Set the TERMINAL_SSH_USER config: `hermes config set TERMINAL_SSH_USER <username>`
4. Verify the settings: `hermes config get TERMINAL_SSH_HOST` and `hermes config get TERMINAL_SSH_USER`
5. Open a Hermes terminal to test the connection; ensure SSH key/agent is set up for password-less login or be ready to enter password.

## Pitfalls

- Forgetting to set both TERMINAL_SSH_HOST and TERMINAL_SSH_USER will cause SSH environment errors.
- Using the wrong username (e.g., local username instead of remote) leads to authentication failures.
- Ensure the SSH server is running on the remote host and port 22 is accessible.
- If using a non-standard port, configure via SSH config file (~/.ssh/config) as Hermes terminal uses default SSH.

## References

- references/atlas-gpu-example.md: Example configuration for connecting to atlas-gpu-01 (192.168.1.20) as user horushelohim.