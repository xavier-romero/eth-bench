import argparse
import time
from web3 import Web3, exceptions
from utils import get_profile

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', required=True, help="Profile to use")
args = vars(ap.parse_args())

node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
    l1_funded_key, rollup_id = \
    get_profile(args['profile'])

sender_key = funded_key
sender_addr = Web3().eth.account.from_key(sender_key).address
receiver_addr = sender_addr

w = Web3(Web3.HTTPProvider(node_url))
sender = w.eth.account.from_key(str(sender_key))
chain_id = chain_id or w.eth.chain_id


def sender_info(sender):
    pending_nonce = w.eth.get_transaction_count(sender.address, 'pending')
    latest_nonce = w.eth.get_transaction_count(sender.address, 'latest')
    latest_balance = w.eth.get_balance(sender.address, 'latest')
    _gas_price = w.eth.gas_price

    print(
        f"-> Sender {sender.address}: pending_nonce={pending_nonce} "
        f"latest_nonce={latest_nonce}, Gas_Price={_gas_price}, "
        f"Balance={latest_balance}"
    )

    return pending_nonce, latest_balance


vers = w.client_version
gas_price = w.eth.gas_price
pending_nonce, before_balance = sender_info(sender)

print(
    f"-> Endpoint {node_url} ({vers}) | chaind {chain_id} | "
    f"block: {w.eth.block_number}"
)

tx = {
    'chainId': chain_id,
    'nonce': pending_nonce,
    'to': receiver_addr,
    'value': w.to_wei(0, 'ether'),
    'gas': 21000,
    'gasPrice': gas_price,
}
print(f"-> Transaction={tx}")


signed_tx = w.eth.account.sign_transaction(tx, sender_key)
print(f"-> Signed_tx={signed_tx}")

tx_hash = w.eth.send_raw_transaction(signed_tx.raw_transaction)
print(signed_tx.raw_transaction)
print(f"-> tx_hash={tx_hash.hex()}")

r = None
start = time.time()
while (not r):
    try:
        r = w.eth.wait_for_transaction_receipt(tx_hash, timeout=5)
    except exceptions.TimeExhausted:
        elapsed = int(time.time() - start)
        print(f"No receipt after {elapsed}s. Retrying...")
        # try:
        #     r2 = w2.eth.wait_for_transaction_receipt(tx_hash, timeout=1)
        # except exceptions.TimeExhausted:
        #     print("No receipt after 5s. Retrying...")
        # else:
        #     print(f"BUT Got confirmation from {ep2[0]}, receipt={dict(r2)}")

print(f"-> Got confirmation, receipt={dict(r)}")

_, after_balance = sender_info(sender)
print(
    f"-> Balance before={before_balance} after={after_balance} "
    f"delta={after_balance - before_balance} "
    f"gas_used={r['gasUsed']} gas_price={gas_price} "
    f"gas*gprice={r['gasUsed']*gas_price}"
)
