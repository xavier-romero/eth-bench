import argparse
from web3 import Web3
from utils import get_profile
from tx import send_transaction


ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', required=True, help="Profile to use")
ap.add_argument(
    '-n', '--number', required=False, default=1, help="Number of wallets")
ap.add_argument(
    '-e', '--eth', required=False, default=10, help="Amount of ETH per wallet")
args = vars(ap.parse_args())

node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
    l1_funded_key = \
    get_profile(args['profile'])


w = Web3(Web3.HTTPProvider(node_url))
sender = Web3().eth.account.from_key(str(funded_key))

n_wallets = int(args['number'])
ether_amount = int(args['eth'])

for i in range(n_wallets):
    wallet = Web3().eth.account.create()
    send_transaction(
        ep=node_url, sender_key=funded_key, receiver_address=wallet.address,
        eth_amount=float(ether_amount), wait='all'
    )
    print(
        f"Address: {wallet.address} "
        f"Private key: {wallet.key.hex()} "
        f"Balance: {ether_amount}"
    )
