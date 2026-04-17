# Repo Cleanup Notes

This is a short review list for deciding what to keep, delete, or `.gitignore`.

## Keep

- `MpcPo8eUdpClosedLoop.cpp`: main closed-loop executable source under active development.
- `TDTUDP.cpp`, `TDTUDP.h`: active UDP transport code used by the main executable.
- `run_closed_loop.bat`, `build_closed_loop.bat`: active run/build entry points.
- `matlab_controller_server.m`: active MATLAB localhost controller server.
- `mpc_step.m`, `mpc_test.m`: active MATLAB controller logic and test logic.
- `compat.h`, `PO8e.h`: active headers required by the main build.
- `PO8eStreaming.dll`, `PO8eStreaming.lib`, `TdtApi820_x64.dll`: required runtime/build dependencies if they are intentionally vendored here.

## Maybe Remove

- `AllModels.mat`: keep only if still needed by MATLAB controller experiments or future offline tuning.
- `ClosedLoopValidation.m`: useful if you still run validation workflows; otherwise may be archival.
- `ReplayPseudoClosedLoopDemo.m`: keep if still useful as an offline/demo harness.
- `create_example_allmodels.m`: keep only if `AllModels.mat` is still part of the workflow.
- `set_mpc_test_target.m`: likely useful only if `mpc_test.m` retargeting is still part of active testing.
- `mpc_step_use_test.m`: likely an experiment/helper file; keep only if you still use it.
- `ReceiveSendTest.cpp`: keep if you still want a standalone transport test harness.
- `UDPExample.cpp`: keep if you still want a minimal UDP reference example.
- `RZ2UdpBarebones.cpp`: keep if you still want a barebones TDT/RZ UDP example.
- `engine_hello.cpp`: keep only if MATLAB Engine bring-up examples are still worth preserving for reference.
- `PO8eExample.cpp`: keep only if the vendor sample is still useful locally.

## Likely Remove Or Ignore

- `MpcPo8eUdpClosedLoop.exe`: local build artifact; usually should not live in source control.
- `MpcPo8eUdpClosedLoop.obj`: local build artifact.
- `TDTUDP.obj`: local build artifact.
- `engine_hello.exe`: local build artifact.
- `engine_hello.obj`: local build artifact.
- `UDPExample.exe`: local build artifact.
- `UDPExample.obj`: local build artifact.
- `RZ2UdpBarebones.exe`: local build artifact.
- `RZ2UdpBarebones.obj`: local build artifact.
- `mpc_test_debug.csv`: temporary diagnostic output.
- `mpc_test_validate.csv`: temporary diagnostic output.
- `flow_validate.csv`: temporary diagnostic output.

## Suggested First Pass

- Delete or ignore the `.exe` and `.obj` files first.
- Delete or ignore the CSV outputs if they are regenerated and not part of a reproducible record.
- Review the demo/example files one-by-one only after the build artifacts are cleaned up.
