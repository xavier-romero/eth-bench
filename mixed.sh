#!/bin/bash

# Take this as example, set the PROFILE name you want to use from your profiles file.
# MASTER should match the address for the private key provided in the profile.
# RPC is the rpc url to query the nonce from.

#Erigon5
PROFILE=erigon5s
MASTER=0x406C6e412895f32573442365d0BA5027ae369cC7
RPC=http://34.175.214.161:8005

#Bali
# PROFILE=bali
# RPC=https://rpc.internal.zkevm-rpc.com/
# MASTER=0x229A5bDBb09d8555f9214F7a6784804999BA4E0D

nonce=$(cast nonce $MASTER --rpc-url $RPC)


PROCESSES_PER_TEST=2
TXS_PER_TEST=300

for test in confirmed allconfirmed unconfirmed erc20 uniswap precompileds pairings keccaks eventminter; do
    tmux new-session -d -s "$test-$PROFILE"
    echo "Running $test with funded nonce $nonce"
    tmux send-keys -t "$test-$PROFILE" python3 Space bench.py Space -p Space $PROFILE Space -c Space $PROCESSES_PER_TEST Space -t Space $TXS_PER_TEST Space --$test Space --nonce Space $nonce C-m
    nonce=$(($nonce+1))
    tmux send-keys -t "$test-$PROFILE" exit C-m
done
