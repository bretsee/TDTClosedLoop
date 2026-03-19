function u = mpc_step_use_test(x)
% MPC_STEP_USE_TEST  Wrapper for using mpc_test.m with the current C++ shape.
%
% This file is not used automatically by C++. The executable still calls
% mpc_step(x). Use this wrapper from MATLAB to validate the controller logic
% before you choose to replace mpc_step.m.

    u = mpc_test(x);
end

