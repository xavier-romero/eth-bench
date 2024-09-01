import argparse
import sys
from web3 import Web3
from utils import get_profile, init_log, say
from tx import send_transaction, confirm_transactions
from evm_table import all_bytecode_combinations


ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', required=True, help="Profile to use")
ap.add_argument('-e', '--eth', required=True, help="Eth to fund each sender")
ap.add_argument('-c', '--confirm', required=True, help="N txs to confirm")
ap.add_argument(
    '-s', '--startfrom', required=False, default=None,
    help="Start from that bytecode")
args = vars(ap.parse_args())

node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
    l1_funded_key = \
    get_profile(args['profile'])

init_log(args['profile'], tool='bruteforce')
w = Web3(Web3.HTTPProvider(node_url))
sender = w.eth.account.from_key(str(funded_key))
eth_amount = int(args['eth'])
confirm_each = int(args['confirm'])
start_from = args['startfrom']

account = w.eth.account.create()
tx_hashes = send_transaction(
    ep=node_url, sender_key=funded_key, eth_amount=eth_amount,
    receiver_address=account.address, wait='last'
)
say(f"Created account, address={account.address} and balance={eth_amount}ETH")

nonce = 0
for i in range(1, 4):
    bytecodes = all_bytecode_combinations(i, start=start_from)
    print(f"Number of bytecodes with {i} byte(s): {len(bytecodes)}")

    n_txs = 0
    for data in bytecodes:
        tx_hashes = send_transaction(
            ep=node_url, sender_key=account.key.hex(), gas=299999, data=data,
            sc_call=True, wait=False, nonce=nonce
        )
        # say(f"Transaction with data={data} and nonce={nonce} sent")
        n_txs += 1
        if n_txs and (n_txs % confirm_each == 0):
            receipts = \
                confirm_transactions(
                    ep=node_url, tx_hashes=tx_hashes, timeout=120)
            if receipts:
                block = int(receipts[0].get('blockNumber'), 16)
                status = int(receipts[0].get('status'), 16)
                say(
                    f"Confirmed tx with data={data} and nonce={nonce} mined "
                    f"in block {block} with status {status}"
                )
            else:
                say(
                    f"ERROR: Transaction with data {data} and nonce {nonce} "
                    "not confirmed"
                )
                sys.exit(1)

        nonce += 1
