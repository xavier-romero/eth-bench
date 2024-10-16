import os
import signal
import requests
import time
import datetime
from web3 import Web3
from utils import say


now = datetime.datetime.now()
id_called = f"{now.hour:02}{now.minute:02}{now.second:02}"

l1_to_l2_timeout_s = 1800
l2_to_l1_timeout_s = 7200

bridge_abi = [
    {
        "inputs": [
            {"internalType": "uint32", "name": "destinationNetwork", "type": "uint32"},  # noqa
            {"internalType": "address", "name": "destinationAddress","type": "address"},  # noqa
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "bool", "name": "forceUpdateGlobalExitRoot", "type": "bool"},  # noqa
            {"internalType": "bytes", "name": "permitData", "type": "bytes"}
        ],
        "name": "bridgeAsset",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "bytes32[32]",
                "name": "smtProofLocalExitRoot",
                "type": "bytes32[32]"
            },
            {
                "internalType": "bytes32[32]",
                "name": "smtProofRollupExitRoot",
                "type": "bytes32[32]"
            },
            {
                "internalType": "uint256",
                "name": "globalIndex",
                "type": "uint256"
            },
            {
                "internalType": "bytes32",
                "name": "mainnetExitRoot",
                "type": "bytes32"
            },
            {
                "internalType": "bytes32",
                "name": "rollupExitRoot",
                "type": "bytes32"
            },
            {
                "internalType": "uint32",
                "name": "originNetwork",
                "type": "uint32"
            },
            {
                "internalType": "address",
                "name": "originTokenAddress",
                "type": "address"
            },
            {
                "internalType": "uint32",
                "name": "destinationNetwork",
                "type": "uint32"
            },
            {
                "internalType": "address",
                "name": "destinationAddress",
                "type": "address"
            },
            {
                "internalType": "uint256",
                "name": "amount",
                "type": "uint256"
            },
            {
                "internalType": "bytes",
                "name": "metadata",
                "type": "bytes"
            }
        ],
        "name": "claimAsset",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
]


def bridge_asset(
    web3, contract, addr, priv_key, amount, to_l2=True, rollup_id=1
):
    token = "0x0000000000000000000000000000000000000000"
    destination_network = 0
    if to_l2:
        # thats needs to be the rollupid
        destination_network = rollup_id

    tx = contract.functions.bridgeAsset(
        destinationNetwork=destination_network,
        destinationAddress=addr,
        amount=amount,
        token=token,
        forceUpdateGlobalExitRoot=True,
        permitData=bytes("", 'utf-8')
    ).build_transaction(
        {
            'gasPrice': web3.eth.gas_price,
            'from': addr,
            'nonce': web3.eth.get_transaction_count(addr),
            'value': amount,
        }
    )
    # gas_estimate = w.eth.estimate_gas(tx)
    signed_tx = web3.eth.account.sign_transaction(tx, priv_key)
    send_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

    tx_hash = send_tx.hex()
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash

    return tx_hash


def bridge_wait_ready(bridge_ep, addr, tx_hash, verbose=True, to_l2=True):
    url = f"{bridge_ep}/bridges/{addr}"
    wait_interval_seconds = 10

    if verbose:
        wait_count = 0
        say("Waiting for bridge to be ready to claim ", end='', flush=True)

    while (True):
        resp = requests.get(url=url)
        data = resp.json()

        for deposit in data['deposits']:
            if (
                deposit['tx_hash'].lower() == tx_hash.lower() and
                deposit['ready_for_claim'] and
                (deposit['claim_tx_hash'] or not to_l2)
            ):
                claim_tx_hash = deposit['claim_tx_hash']
                deposit_cnt = deposit['deposit_cnt']
                global_index = deposit['global_index']
                network_id = deposit['network_id']
                if verbose:
                    say(
                        f"Ready! claim tx_hash:{claim_tx_hash} "
                        f"deposit_cnt:{deposit_cnt} network_id:{network_id}"
                    )
                return (claim_tx_hash, deposit_cnt, network_id, global_index)
        time.sleep(wait_interval_seconds)
        if verbose:
            wait_count += wait_interval_seconds
            if wait_count >= 60:
                say("* ", end='', flush=True)
                wait_count = 0
            else:
                say(". ", end='', flush=True)


def bridge_merkle_proof(bridge_ep, deposit_cnt, network_id):
    url = f"{bridge_ep}/merkle-proof"

    resp = requests.get(
        url=url, params={'deposit_cnt': deposit_cnt, 'net_id': network_id})
    data = resp.json()
    merkle_proof = data['proof']['merkle_proof']
    main_exit_root = data['proof']['main_exit_root']
    rollup_exit_root = data['proof']['rollup_exit_root']
    rollup_merkle_proof = data['proof']['rollup_merkle_proof']

    return (
        merkle_proof, main_exit_root, rollup_exit_root, rollup_merkle_proof
    )


def bridge_claim_asset(
    web3, contract, addr, priv_key, global_index, merkle_proof, main_exit_root,
    rollup_exit_root, amount, rollup_merkle_proof
):
    token = "0x0000000000000000000000000000000000000000"
    merkle_proof_bytes = [bytes.fromhex(x[2:]) for x in merkle_proof]
    rollup_merkle_proof_bytes = [
        bytes.fromhex(x[2:]) for x in rollup_merkle_proof
    ]
    tx = contract.functions.claimAsset(
        smtProofLocalExitRoot=merkle_proof_bytes,
        smtProofRollupExitRoot=rollup_merkle_proof_bytes,
        globalIndex=int(global_index),
        mainnetExitRoot=bytes.fromhex(main_exit_root[2:]),
        rollupExitRoot=bytes.fromhex(rollup_exit_root[2:]),
        originNetwork=0,
        originTokenAddress=token,
        destinationNetwork=0,
        destinationAddress=addr,
        amount=amount,
        metadata=bytes("", 'utf-8')
    ).build_transaction(
        {
            'gasPrice': int(web3.eth.gas_price*1.5),
            'from': addr,
            'nonce': web3.eth.get_transaction_count(addr),
            'value': 0,
        }
    )

    signed_tx = web3.eth.account.sign_transaction(tx, priv_key)
    send_tx = web3.eth.send_raw_transaction(signed_tx.raw_transaction)

    return send_tx.hex()


def bridge_wait_claimed(bridge_ep, addr, claim_tx_hash, verbose=True):
    url = f"{bridge_ep}/claims/{addr}"

    if verbose:
        say("Waiting for bridge to claim tx ", end='', flush=True)
    while (True):
        resp = requests.get(url=url)
        data = resp.json()

        for claim in data['claims']:
            if claim['tx_hash'].lower() == claim_tx_hash.lower():
                if verbose:
                    say("Claimed!")
                return True
        if verbose:
            say(". ", end='', flush=True)
        time.sleep(2)


def bridge_to_l2(l1_ep, bridge_ep, bridge_addr, sender_privkey, rollup_id=1):
    signal.alarm(l2_to_l1_timeout_s)

    w = Web3(Web3.HTTPProvider(l1_ep))
    c = w.eth.contract(
        address=Web3.to_checksum_address(bridge_addr),
        abi=bridge_abi
    )
    amount = w.to_wei(0.0001, 'ether')
    sender_addr = Web3().eth.account.from_key(str(sender_privkey)).address

    start = time.time()
    try:
        tx_hash = bridge_asset(
            w, c, sender_addr, sender_privkey, amount, to_l2=True,
            rollup_id=rollup_id)
        say(f"bridge_asset tx_hash: {tx_hash}")
        (claim_tx_hash, _, _, _) = \
            bridge_wait_ready(bridge_ep, sender_addr, tx_hash, verbose=False)
        say(f"tx_hash {tx_hash} ready to be claimed: {claim_tx_hash}")

        bridge_wait_claimed(
            bridge_ep, sender_addr, claim_tx_hash, verbose=False)
    except Exception as e:
        elapsed = time.time() - start
        say(f"Exception after {elapsed}s: {e}")
        os._exit(1)
    else:
        elapsed = time.time() - start
        say(f"Bridge to L2 completed after {elapsed}s")
        signal.alarm(0)


def bridge_to_l1(l1_ep, l2_ep, bridge_ep, bridge_addr, sender_privkey):
    signal.alarm(l2_to_l1_timeout_s)

    w = Web3(Web3.HTTPProvider(l2_ep))
    c = w.eth.contract(
        address=Web3.to_checksum_address(bridge_addr),
        abi=bridge_abi
    )
    amount = w.to_wei(0.00001, 'ether')
    sender_addr = Web3().eth.account.from_key(str(sender_privkey)).address

    start = time.time()
    try:
        tx_hash = bridge_asset(
            w, c, sender_addr, sender_privkey, amount, to_l2=False)
        say(f"bridge_asset tx_hash: {tx_hash}")
        (claim_tx_hash, deposit_cnt, network_id, global_index) = \
            bridge_wait_ready(
                bridge_ep, sender_addr, tx_hash, verbose=False, to_l2=False)
        say(f"tx_hash {tx_hash} ready to be claimed: {claim_tx_hash}")
        (merkle_proof, main_exit_root, rollup_exit_root,
         rollup_merkle_proof) = \
            bridge_merkle_proof(bridge_ep, deposit_cnt, network_id)
        say(f"Got merkle proof and rer: {rollup_exit_root}")
        w = Web3(Web3.HTTPProvider(l1_ep))
        c = w.eth.contract(address=bridge_addr, abi=bridge_abi)
        claimed_tx_hash = bridge_claim_asset(
            w, c, sender_addr, sender_privkey, global_index, merkle_proof,
            main_exit_root, rollup_exit_root, amount, rollup_merkle_proof
        )
    except Exception as e:
        elapsed = time.time() - start
        say(f"Exception after {elapsed}s: {e}")
        os._exit(1)
    else:
        elapsed = time.time() - start
        say(f"Claimed tx hash: {claimed_tx_hash}")
        say(f"Bridge to L1 completed after {elapsed}s")
        signal.alarm(0)
