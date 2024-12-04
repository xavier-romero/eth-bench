import argparse
import time
from web3 import Web3
from utils import get_profile

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', required=True, help="Profile to use")
ap.add_argument(
    '-i', '--interval', required=False, default=3, help="Check interval")
args = vars(ap.parse_args())

node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
    l1_funded_key, rollup_id = \
    get_profile(args['profile'])
interval = int(args['interval'])

w = Web3(Web3.HTTPProvider(node_url))

while (True):
    gas_price = w.eth.gas_price
    print(f"Gas_Price: {gas_price}")
    time.sleep(interval)
