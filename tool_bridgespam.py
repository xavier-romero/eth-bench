#!/usr/bin/env python3
import argparse
import requests
from time import sleep, time
from web3 import Web3
from utils import get_profile, say
from bridge import bridge_abi, bridge_asset

# CONST STATUS
STATUS_DEPOSIT = 'deposit'
STATUS_READY_TO_CLAIM = 'ready_to_claim'

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', help="Profile to use", default='default')
ap.add_argument(
    '-s', '--sleep', required=False, default=10,
    help="Time to sleep between loops")
ap.add_argument(
    '-b2', '--bridges2l2', required=False, default=5,
    help="Number of bridges to l2 to keep busy")
ap.add_argument(
    '-b1', '--bridges2l1', required=False, default=5,
    help="Number of bridges to l1 to keep busy")
args = vars(ap.parse_args())

node_url, chain_id, l2_funded_key, bridge_ep, bridge_addr, l1_ep, \
    l1_funded_key, rollup_id = \
    get_profile(args['profile'])

# ARGS
sleep_time = int(args['sleep'])
n_b1 = int(args['bridges2l1'])
n_b2 = int(args['bridges2l2'])

# L1 setup for bridges to L2
w1 = Web3(Web3.HTTPProvider(l1_ep))
c1 = w1.eth.contract(
    address=Web3.to_checksum_address(bridge_addr),
    abi=bridge_abi
)
l1_sender_addr = Web3().eth.account.from_key(str(l1_funded_key)).address
say(f"l1_sender_addr: {l1_sender_addr}")
# As they're autoclaimed, we won't find them in pending-bridges_
# l1_bridges_url = \
#     f"{bridge_ep}/pending-bridges" \
#     f"?dest_net={rollup_id}&dest_addr={l1_sender_addr}&limit={n_b2}"
l1_bridges_url = f"{bridge_ep}/bridges/{l1_sender_addr}?limit=1000"
l1_claims_url = f"{bridge_ep}/claims/{l1_sender_addr}"
l1_merkleproof_url = f"{bridge_ep}/merkle-proof"

# L2 setup for bridges to L1
w2 = Web3(Web3.HTTPProvider(node_url))
c2 = w2.eth.contract(
    address=Web3.to_checksum_address(bridge_addr),
    abi=bridge_abi
)
l2_sender_addr = Web3().eth.account.from_key(str(l2_funded_key)).address
# l2_bridges_url = f"{bridge_ep}/bridges/{l2_sender_addr}"
l2_bridges_url = \
    f"{bridge_ep}/pending-bridges" \
    f"?dest_net=0&dest_addr={l1_sender_addr}&limit={n_b1}"

# Main vars
amount = Web3.to_wei(0.0001, 'ether')
b1 = {}
b2 = {}
total_claims_l1 = 0
total_claims_l2 = 0
# So, we only bridge to L1 as many times as we already done before to L2
l1_to_l2_diff = 0


def l1_claim_log(
    deposit_cnt, smtProofLocalExitRoot, smtProofRollupExitRoot, globalIndex,
    mainnetExitRoot, rollupExitRoot, originNetwork, originTokenAddress,
    destinationNetwork, destinationAddress, amount, metadata, _from,
    nonce, status, e, tx_hash
):
    say(f"Logging claim on L1: {tx_hash}")
    # Log claim
    ts = int(time())
    with open(f'bridge-claim-log-{deposit_cnt}-{ts}-{status}.log', 'w') as f:
        f.write(
            f"deposit_cnt={deposit_cnt}\n"
            f"smtProofLocalExitRoot={smtProofLocalExitRoot}\n"
            f"smtProofRollupExitRoot={smtProofRollupExitRoot}\n"
            f"globalIndex={globalIndex}\n"
            f"mainnetExitRoot={mainnetExitRoot}\n"
            f"rollupExitRoot={rollupExitRoot}\n"
            f"originNetwork={originNetwork}\n"
            f"originTokenAddress={originTokenAddress}\n"
            f"destinationNetwork={destinationNetwork}\n"
            f"destinationAddress={destinationAddress}\n"
            f"amount={amount}\n"
            f"metadata={metadata}\n"
            f"_from={_from}\n"
            f"nonce={nonce}\n"
            f"status={status}\n"
            f"e={e}\n"
            f"tx_hash={tx_hash}\n"
        )


# Main loop
while True:
    # Bridges to L2
    while len(b2) < n_b2:
        tx_hash = bridge_asset(
            w1, c1, l1_sender_addr, l1_funded_key, amount, to_l2=True,
            rollup_id=rollup_id
        )
        b2[tx_hash.lower()] = {'status': STATUS_DEPOSIT, 'init_time': time()}
        say(f"+ L1 {len(b2)}/{n_b2} Deposit {tx_hash}")

    # Bridges to L1
    while (len(b1) < n_b1) and (l1_to_l2_diff > 0):
        tx_hash = bridge_asset(
            w2, c2, l2_sender_addr, l2_funded_key, amount, to_l2=False)
        b1[tx_hash.lower()] = {'status': STATUS_DEPOSIT, 'init_time': time()}
        l1_to_l2_diff -= 1
        say(f"+ L2 {len(b1)}/{n_b1} Deposit {tx_hash}")
    if len(b1) < n_b1 and l1_to_l2_diff <= 0:
        say(f"= L2 {len(b1)}/{n_b1} "
            "Can not deposit on L2 until something has been claimed.")

    # Get bridges for both networks
    try:
        l2_resp = requests.get(url=l1_bridges_url)  # Bridges to L2
        l1_resp = requests.get(url=l2_bridges_url)  # Bridges to L1
    except requests.exceptions.RequestException:
        continue
    else:
        l2_data = l2_resp.json()  # Bridges to L2
        l1_data = l1_resp.json()  # Bridges to L1

    # Check bridges to L2 ready to claim
    # say("Checking bridges to L2 ready to claim...")
    for deposit in l2_data['deposits']:
        if (
            deposit['ready_for_claim'] and
            deposit['claim_tx_hash'] and
            deposit['dest_net'] == rollup_id
        ):
            tx_hash = deposit['tx_hash']
            claim_tx_hash = deposit['claim_tx_hash']

            if tx_hash in b2 and b2[tx_hash]['status'] == STATUS_DEPOSIT:
                b2[tx_hash]['status'] = STATUS_READY_TO_CLAIM
                b2[tx_hash]['claim_tx_hash'] = claim_tx_hash
                say(f"= L1 {len(b2)}/{n_b2} Deposit ready to claim on L2, "
                    f"txhash: {tx_hash} claim_txhash: {claim_tx_hash}")

    # Check bridges to L1 ready to claim
    # say("Checking bridges to L1 ready to claim...")
    # The URL already filters by dest_net=0
    for deposit in l1_data['deposits']:
        if deposit['ready_for_claim']:
            tx_hash = deposit['tx_hash']
            claim_tx_hash = deposit['claim_tx_hash']
            deposit_cnt = deposit['deposit_cnt']
            global_index = deposit['global_index']
            network_id = deposit['network_id']

            if tx_hash in b1 and b1[tx_hash]['status'] == STATUS_DEPOSIT:
                b1[tx_hash]['status'] = STATUS_READY_TO_CLAIM
                b1[tx_hash]['claim_tx_hash'] = claim_tx_hash
                b1[tx_hash]['deposit_cnt'] = deposit_cnt
                b1[tx_hash]['global_index'] = global_index
                b1[tx_hash]['network_id'] = network_id
                say(f"= L2 {len(b1)}/{n_b1} Deposit ready to claim on L1, "
                    f"txhash: {tx_hash} claim_txhash: {claim_tx_hash}")
            elif tx_hash not in b1:
                b1[tx_hash] = {
                    'status': STATUS_READY_TO_CLAIM,
                    'claim_tx_hash': claim_tx_hash,
                    'deposit_cnt': deposit_cnt,
                    'global_index': global_index,
                    'network_id': network_id,
                    'init_time': time()
                }
                say(f"+ L2 {len(b1)}/{n_b1} ZOMBIE Deposit ready to claim on "
                    f"L1, txhash: {tx_hash} claim_txhash: {claim_tx_hash}")

    # Check and finalize claims on L2
    try:
        l2_resp = requests.get(url=l1_claims_url)  # Bridges to L2
    except requests.exceptions.RequestException:
        continue
    else:
        l2_data = l2_resp.json()  # Bridges to L2

    # say("Checking claims on L2...")
    for claim in l2_data['claims']:
        claim_tx_hash = claim['tx_hash'].lower()
        keys_to_remove = []
        for k, v in b2.items():
            if (
                v['status'] == STATUS_READY_TO_CLAIM and
                v['claim_tx_hash'] == claim_tx_hash
            ):
                total_claims_l2 += 1
                spent = int(time() - v['init_time'])
                l1_to_l2_diff += 1
                keys_to_remove.append(k)
                say(f"- L1 {len(b2)-len(keys_to_remove)}/{n_b2} "
                    f"Claim on L2: {claim_tx_hash}. "
                    f"Bridge to L2 complete, total time: {spent}s. "
                    f"Total L2 claims: {total_claims_l2}")
        for k in keys_to_remove:
            del b2[k]

    # Check and finalize claims on L1
    # say("Checking claims on L1...")
    keys_to_remove = []
    for k, v in b1.items():
        if v['status'] == STATUS_READY_TO_CLAIM:
            # GET MERKLE PROOF
            deposit_cnt = int(v['deposit_cnt'])
            network_id = int(v['network_id'])
            global_index = int(v['global_index'])
            resp = requests.get(
                url=l1_merkleproof_url,
                params={'deposit_cnt': deposit_cnt, 'net_id': network_id})
            data = resp.json()
            merkle_proof = data['proof']['merkle_proof']
            main_exit_root = data['proof']['main_exit_root']
            rollup_exit_root = data['proof']['rollup_exit_root']
            rollup_merkle_proof = data['proof']['rollup_merkle_proof']
            say(f"= L2 {len(b1)}/{n_b1} "
                f"Got merkle proof for L2 deposit {deposit_cnt}, "
                f"main_exit_root: {main_exit_root}, "
                f"rollup_exit_root: {rollup_exit_root}")
            # CLAIM ASSET
            merkle_proof_bytes = [bytes.fromhex(x[2:]) for x in merkle_proof]
            rollup_merkle_proof_bytes = [
                bytes.fromhex(x[2:]) for x in rollup_merkle_proof
            ]

            token = "0x0000000000000000000000000000000000000000"
            nonce = w1.eth.get_transaction_count(l1_sender_addr, 'pending')
            tx_status = 'PENDING'
            tx_exception = None
            tx_hash = None
            try:
                tx = c1.functions.claimAsset(
                    smtProofLocalExitRoot=merkle_proof_bytes,
                    smtProofRollupExitRoot=rollup_merkle_proof_bytes,
                    globalIndex=global_index,
                    mainnetExitRoot=bytes.fromhex(main_exit_root[2:]),
                    rollupExitRoot=bytes.fromhex(rollup_exit_root[2:]),
                    originNetwork=0,
                    originTokenAddress=token,
                    destinationNetwork=0,
                    destinationAddress=l1_sender_addr,
                    amount=amount,
                    metadata=bytes("", 'utf-8')
                ).build_transaction(
                    {
                        'gasPrice': int(w1.eth.gas_price*1.5),
                        'from': l1_sender_addr,
                        'nonce': nonce,
                        'value': 0,
                    }
                )
                signed_tx = w1.eth.account.sign_transaction(tx, l1_funded_key)
                send_tx = \
                    w1.eth.send_raw_transaction(signed_tx.raw_transaction)
            except Exception as e:
                if '0x646cf558' in str(e):
                    say(f"ERROR. Already claimed: {deposit_cnt} ")
                    keys_to_remove.append(k)
                else:
                    say(f"ERROR CLAIMING deposit {deposit_cnt}: {str(e)}")
                tx_status = 'ERROR'
                tx_exception = e
            else:
                tx_status = 'SUCCESS'
                tx_hash = send_tx.hex()
            finally:
                l1_claim_log(
                    deposit_cnt=deposit_cnt,
                    smtProofLocalExitRoot=merkle_proof_bytes,
                    smtProofRollupExitRoot=rollup_merkle_proof_bytes,
                    globalIndex=global_index,
                    mainnetExitRoot=bytes.fromhex(main_exit_root[2:]),
                    rollupExitRoot=bytes.fromhex(rollup_exit_root[2:]),
                    originNetwork=0,
                    originTokenAddress=token,
                    destinationNetwork=0,
                    destinationAddress=l1_sender_addr,
                    amount=amount,
                    metadata=bytes("", 'utf-8'),
                    _from=l1_sender_addr,
                    nonce=nonce,
                    status=tx_status,
                    e=tx_exception,
                    tx_hash=tx_hash
                )

            if tx_status == 'ERROR':
                continue

            total_claims_l1 += 1
            spent = int(time() - v['init_time'])
            keys_to_remove.append(k)
            say(f"- L2 {len(b1)-len(keys_to_remove)}/{n_b1} "
                f"Claim on L1: {send_tx.hex()}. Deposit: {deposit_cnt}. "
                f"Bridge to L1 complete, total time: {spent}s. "
                f"Total L1 claims: {total_claims_l1}")
    for k in keys_to_remove:
        del b1[k]

    # Sleep
    # say(f"Waiting {sleep_time}s before next loop...")
    sleep(sleep_time)
