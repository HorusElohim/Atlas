# SSH Preference for Remote Testing

In the Portalis project, the user expressed a strong preference for using SSH directly to run tests on powerful remote machines (like Atlas GPU) rather than using agent delegation (A2A).

Key statements from the user:
- "you should run the test in Atlas, even with ssh that is a more powerfull machine then the jetson"
- "I prefer to disable it [A2A] and use instead ssh chain."

This preference was based on:
1. The remote machine (Atlas GPU) being significantly more powerful than the local Jetson device
2. Avoiding potential complexity or overhead of agent communication
3. Direct access to the hardware and full control over the test environment

When debugging remote test failures, consider offering SSH as an alternative to A2A delegation, especially when:
- The remote machine has superior computational resources
- Direct hardware access is needed (e.g., for GPU-dependent tests)
- Simplifying the debugging environment by removing agent communication layers
- The user has explicitly expressed this preference in past sessions

To implement SSH-based remote testing:
1. Set up SSH aliases and keys for reliable access (e.g., `atlas-gpu-01` in ~/.ssh/config)
2. Use SSH commands directly to execute tests on the remote machine
3. For workflow integration, consider wrapping SSH calls in scripts or Makefiles
4. Verify the remote environment matches expectations before running tests

This approach bypasses the need for A2A setup while providing direct control over the remote testing environment.