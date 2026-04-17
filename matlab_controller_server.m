function matlab_controller_server(mode, requestPort, replyPort, outputCount, constantValue)
% MATLAB_CONTROLLER_SERVER  Localhost UDP controller responder for C++ testing.
%
% Usage:
%   matlab_controller_server
%   matlab_controller_server('constant', 31000, 31001, 8, 5)
%   matlab_controller_server('ramp', 31000, 31001, 8, 0)
%
% Protocol:
%   Request  = [uint32 seq][uint32 feature_count][feature_count x float32]
%   Response = [uint32 seq][uint32 output_count][output_count x float32]
%   All integer/float words are sent in network byte order (big-endian).

    if nargin < 1 || isempty(mode)
        mode = 'constant';
    end
    if nargin < 2 || isempty(requestPort)
        requestPort = 31000;
    end
    if nargin < 3 || isempty(replyPort)
        replyPort = 31001;
    end
    if nargin < 4 || isempty(outputCount)
        outputCount = 8;
    end
    if nargin < 5 || isempty(constantValue)
        constantValue = 5;
    end

    mode = lower(string(mode));
    outputCount = max(1, double(outputCount));
    constantValue = double(constantValue);

    u = udpport("datagram", "IPV4", "LocalPort", requestPort, "Timeout", 1.0);
    cleanupObj = onCleanup(@() clear_udp_port(u)); %#ok<NASGU>

    packetCount = 0;
    rampValue = 0;
    rampStep = 5;
    rampMin = 0;
    rampMax = 40;
    rampDirection = 1;

    fprintf('MATLAB localhost controller server ready. mode=%s requestPort=%d replyPort=%d outputCount=%d constantValue=%g\n', ...
            mode, requestPort, replyPort, outputCount, constantValue);
    fprintf('Press Ctrl+C in MATLAB to stop.\n');

    while true
        if u.NumDatagramsAvailable < 1
            pause(0.001);
            continue;
        end

        packets = read(u, u.NumDatagramsAvailable, "uint8");
        for pktIdx = 1:numel(packets)
            packet = packets(pktIdx);
            bytes = uint8(packet.Data);
            packetCount = packetCount + 1;
            senderAddress = string(packet.SenderAddress);
            senderPort = double(packet.SenderPort);

            if numel(bytes) < 8
                fprintf('Ignoring short localhost request #%d from %s:%d (%d bytes)\n', ...
                        packetCount, senderAddress, senderPort, numel(bytes));
                continue;
            end

            seq = unpack_u32_be(bytes(1:4));
            featureCount = unpack_u32_be(bytes(5:8));
            neededBytes = 8 + double(featureCount) * 4;
            if numel(bytes) < neededBytes
                fprintf('Ignoring truncated localhost request #%d seq=%u featureCount=%u bytes=%d\n', ...
                        packetCount, seq, featureCount, numel(bytes));
                continue;
            end

            features = zeros(double(featureCount), 1);
            for i = 1:double(featureCount)
                base = 8 + (i - 1) * 4;
                features(i) = unpack_f32_be(bytes(base + (1:4)));
            end

            switch mode
                case "constant"
                    y = constantValue * ones(outputCount, 1);
                case "ramp"
                    y = rampValue * ones(outputCount, 1);
                    rampValue = rampValue + rampDirection * rampStep;
                    if rampValue >= rampMax
                        rampValue = rampMax;
                        rampDirection = -1;
                    elseif rampValue <= rampMin
                        rampValue = rampMin;
                        rampDirection = 1;
                    end
                otherwise
                    error('matlab_controller_server:UnsupportedMode', ...
                          'Unsupported mode: %s', mode);
            end

            reply = pack_response(seq, y);
            write(u, reply, "uint8", "127.0.0.1", replyPort);

            if packetCount <= 5 || mod(packetCount, 100) == 0
                feature0 = features(1);
                out0 = y(1);
                fprintf('Reply #%d seq=%u sender=%s:%d feature0=%.6f out0=%.6f bytes=%d\n', ...
                        packetCount, seq, senderAddress, senderPort, feature0, out0, numel(reply));
            end
        end
    end
end

function clear_udp_port(u)
    try
        clear u
    catch
    end
end

function value = unpack_u32_be(bytes)
    tmp = typecast(uint8(bytes), 'uint32');
    value = double(swapbytes(tmp));
end

function value = unpack_f32_be(bytes)
    tmp = typecast(uint8(bytes), 'uint32');
    tmp = swapbytes(tmp);
    value = double(typecast(tmp, 'single'));
end

function bytes = pack_response(seq, values)
    values = single(values(:));
    count = uint32(numel(values));
    bytes = zeros(8 + numel(values) * 4, 1, 'uint8');
    bytes(1:4) = typecast(swapbytes(uint32(seq)), 'uint8');
    bytes(5:8) = typecast(swapbytes(count), 'uint8');
    for i = 1:numel(values)
        base = 8 + (i - 1) * 4;
        word = typecast(values(i), 'uint32');
        bytes(base + (1:4)) = typecast(swapbytes(word), 'uint8');
    end
end
