# Atlas GPU SSH Configuration Example

This example shows how to configure Hermes terminal SSH to connect to the atlas-gpu-01 machine in the Hermes fleet.

## Configuration

For the atlas-gpu-01 host (192.168.1.20) with user horushelohim:

```bash
hermes config set TERMINAL_SSH_HOST 192.168.1.20
hermes config set TERMINAL_SSH_USER horushelohim
```

## Verification

Check the configuration:
```bash
hermes config get TERMINAL_SSH_HOST
# Should return: 192.168.1.20

hermes config get TERMINAL_SSH_USER
# Should return: horushelohim
```

## Usage

After setting these values, opening a terminal in Hermes will attempt to connect via SSH to horushelohim@192.168.1.20.

Ensure your SSH key is set up for password-less login, or be prepared to enter the password when prompted.

## Fleet Context

This configuration is part of the Hermes fleet setup where:
- Jetson (192.168.1.172) acts as the manager node
- atlas-gpu-01 (192.168.1.20) acts as the operator node with GPU access
- The TERMINAL_SSH_HOST setting directs the Hermes terminal to connect to the GPU node for heavy work