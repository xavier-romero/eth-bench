import argparse
import time
from web3 import Web3, exceptions
from utils import get_profile
from tx import send_transaction
from geth import get_chainid

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', required=True, help="Profile to use")
ap.add_argument(
    '-f', '--flood', required=False, action='store_true', default=False,
    help="Do NOT wait for tx to be mined",
)
ap.add_argument(
    '-e', '--eth', required=False, default=5,
    help="ETHs to fund sender account",
)
args = vars(ap.parse_args())

node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
    l1_funded_key, _ = \
    get_profile(args['profile'])

chain_id = chain_id or get_chainid(node_url)

flood = bool(args['flood'])

sender = Web3().eth.account.create()
sender_addr = sender.address
sender_key = sender.key.hex()

send_transaction(
    ep=node_url, sender_key=funded_key, receiver_address=sender_addr,
    eth_amount=float(args['eth']), wait='all'
)

receiver_addr = sender_addr

w = Web3(Web3.HTTPProvider(node_url))

pending_nonce = w.eth.get_transaction_count(sender_addr, 'pending')
latest_nonce = w.eth.get_transaction_count(sender_addr, 'latest')
gas_price = w.eth.gas_price
vers = w.client_version

print(
    f"Endpoint {node_url} ({vers}) | chaind {chain_id} | "
    f"block: {w.eth.block_number}"
)
print(
    f"Sender {sender_addr}: pending_nonce={pending_nonce} "
    f"latest_nonce={latest_nonce}, Gas_Price={gas_price}")

nonce = pending_nonce
counter = 0
while True:
    tx = {
        'chainId': chain_id,
        'nonce': nonce,
        'to': receiver_addr,
        'value': w.to_wei(0, 'ether'),
        'gas': 21000,
        'gasPrice': gas_price,
    }
    signed_tx = w.eth.account.sign_transaction(tx, sender_key)
    tx_hash = w.eth.send_raw_transaction(signed_tx.raw_transaction)
    counter += 1
    nonce += 1
    print(f"tx_count={counter} tx_hash={tx_hash.hex()}")
    if flood:
        continue

    start = time.time()
    r = None
    while (not r):
        try:
            r = w.eth.wait_for_transaction_receipt(tx_hash, timeout=5)
        except exceptions.TimeExhausted:
            elapsed = int(time.time() - start)
            print(f"No receipt after {elapsed}s. Retrying...")

    elapsed = int(time.time() - start)
    print(f"Got confirmation after {elapsed}s")
