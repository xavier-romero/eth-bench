# Ethereum Benchmarks
## OS Setup
Install ```python3``` and ```pip3```, in ubuntu that can be done by:
```bash
sudo apt-get install python3 python3-pip
```

Then install requirements:
```bash
pip3 install -r requirements.txt
```

### Solc
For tests with SC you need to have solc installed on your system:
```bash
https://docs.soliditylang.org/en/latest/installing-solidity.html
```

### Uniswap V2
To run Uniswap v2 deployment you need to update the submodule:
```bash
git submodule init
git submodule update
```

## Profiles setup
Use default ```profiles.json``` to add your own network.
You need to set the RPC url and provide the private key by any of the 3 available methods:
- Set the path to a file holding the private key in plain text
- Set the private key directly in the profiles.json
- Set the private key through a ENV VAR
Please see default example profiles

## Execute test
Minimal test to check everything works:
  ```bash
  python3 bench.py -p testnet -c 1 -t 1 --unconfirmed
  ```

  Replace *testnet* with the desired profile.

Extensive test:
```bash
  python3 bench.py -p testnet -c 10 -t 150 --all
  ```


  ### Bench options
  Mandatory options:
  - ```-p <string>``` To set the profile, must be filled on profiles.json
  - ```-c <int>``` How many paralel processes to run
  - ```-t <int>``` Number of transactions per process, we will refer to this number as **t**
  
  Available tests to run:
- ```--allconfirmed``` Each process launch **t** txs and confirm all of them one by one
- ```--confirmed``` Each process lanch **t** txs and confirm just the last one
- ```--unconfirmed``` Each process launch **t** txs but it does not confirm any of them
- ```--erc20``` Each process creates **t** ERC20 tokens + **t** token transfers
- ```--uniswap``` Each process creates **t** sets of Uniswap v2 smart contracts (3 SC per set).
- ```--precompileds``` Each process creates **t** SC with 4 precompiled functions, and then each process calls **t** times each one of these 4 functions for the first SC.
- ```--pairings``` Each process creates **t** SC with a pairings function. the first SC.
- ```--keccaks``` Each process creates **t** SC with a keccaks loop constructor.
- ```--eventminter``` Each process creates **t** SC with a Event minter constructor.

Run all previous tests:
- ```--all``` 

Other flags:

- ```--recover``` Recover remaining funds in all created accounts -sent back the funded account- as long as they're enough to pay tx fees. (enabled by default)
- ```--nonce``` Set the nonce for master account. Not required, just to perform tricky tests in paralel !

### Logging
Each execution is incrementally logged to ```bench_{profile_name}.log``` file. You can find there all past results.
```bash
grep Results bench_{profile_name}.log
```
You will also find on the log file all the transaction hashes for all the transactions sent.


### Mixed tests
Each tests is paralelized but only 1 kind of test runs at a time. If you want to execute multiple tests at once you can easily achieve these by spanning multiple instances in paralel.
That's a simple example to launch all tests at same time using ```tmux```:
```bash
PROFILE=bali
RPC=https://rpc.internal.zkevm-rpc.com/
MASTER=0x229A5bDBb09d8555f9214F7a6784804999BA4E0D

# Using tool cast to fetch the nonce, otherwise you can just it set here manually
nonce=$(cast nonce $MASTER --rpc-url $RPC)

for test in confirmed allconfirmed unconfirmed erc20 uniswap precompileds pairings keccaks eventminter; do
    tmux new-session -d -s "$test-$PROFILE"
    echo "Running $test with funded nonce $nonce"
    tmux send-keys -t "$test-$PROFILE" python3 Space bench.py Space -p Space $PROFILE Space -c Space 2 Space -t Space 200 Space --$test Space --nonce Space $nonce C-m
    nonce=$(($nonce+1))
    tmux send-keys -t "$test-$PROFILE" exit C-m
done
```
