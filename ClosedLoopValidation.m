SDKPATH = 'C:\Users\brets\Desktop\TDTMatlabSDK\TDTSDK'; % or whatever path you extracted the SDK zip into
addpath(genpath(SDKPATH));
%%
data = TDTbin2mat('C:\Users\brets\Downloads\ClosedLoopTest_LD-260318-145814\ClosedLoopTest_LD-260318-145814');
validata = readtable('flow_validate.csv');

figure;
plot(data.scalars.UDP1.data(5,:));
title('UDP1 Data');

figure;
plot(validata.u0);
title('Validation u0');
%%
u = data.scalars.UDP1.data;
class(u)
u(1:10)
typecast(uint32(u(1:10)), 'single')
typecast(swapbytes(uint32(u(1:10))), 'single')
%%
u = data.scalars.UDP1.data;

fprintf('Class: %s\n', class(u));
fprintf('Length: %d\n', numel(u));
fprintf('Min: %g\n', min(u));
fprintf('Max: %g\n', max(u));
fprintf('Nonzero count: %d\n', nnz(u));

idx = find(u ~= 0, 10, 'first');
disp('First nonzero indices:')
disp(idx)

if ~isempty(idx)
    disp('Values at first nonzero indices:')
    disp(u(idx))
end
%%
idx = find(u ~= 0, 10, 'first');
u_test = u(idx);

disp(u_test)
disp(typecast(uint32(u_test), 'single'))
disp(typecast(swapbytes(uint32(u_test)), 'single'))