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
ap.add_argument(
    '-r', '--receiver', required=False, default=None, help="Receiver wallet")

args = vars(ap.parse_args())

node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
    l1_funded_key, _ = \
    get_profile(args['profile'])


w = Web3(Web3.HTTPProvider(node_url))
sender = Web3().eth.account.from_key(str(funded_key))

n_wallets = int(args['number'])
ether_amount = int(args['eth'])
receiver = args['receiver']

if receiver:
    n_wallets = 1

for i in range(n_wallets):
    wallet = Web3().eth.account.create()
    wallet_addr = receiver or wallet.address
    wallet_key = 'Unknown' if receiver else wallet.key.hex()

    send_transaction(
        ep=node_url, sender_key=funded_key, receiver_address=wallet_addr,
        eth_amount=float(ether_amount), wait='all'
    )
    print(
        f"Address: {wallet_addr} "
        f"Private key: {wallet_key} "
        f"Balance: {ether_amount}"
    )
