#!/usr/bin/env python3
import argparse
import json
from utils import get_profile
from geth import (
    get_chainid, get_blocknumber, get_batchnumber, get_block,
    get_transaction_receipt, get_lastverifiedbatch, get_lastvirtualbatch)

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', help="Profile to use", default='default')
args = vars(ap.parse_args())

node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
    l1_funded_key, rollup_id = \
    get_profile(args['profile'])


net_info = {
    'node_url': node_url,
    'chain_id': get_chainid(node_url),
    'last_block': get_blocknumber(node_url),
    'last_batch': get_batchnumber(node_url),
    'last_verified_batch': get_lastverifiedbatch(node_url),
    'last_virtual_batch': get_lastvirtualbatch(node_url),
}

tx_count = 0
tx_gasused = 0
tx_ok = 0
tx_ko = 0
for block in range(net_info['last_block']+1):
    block_info = get_block(node_url, block)
    tx_count += len(block_info['transactions'])
    tx_hashes = [tx['hash'] for tx in block_info['transactions']]
    for tx_hash in tx_hashes:
        tx_receipt = get_transaction_receipt(node_url, tx_hash)
        if tx_receipt:
            tx_gasused += int(tx_receipt['gasUsed'], 16)
            if tx_receipt['status'] == '0x1':
                tx_ok += 1
            else:
                tx_ko += 1
        else:
            tx_ko += 1

net_info['tx_count'] = tx_count
net_info['tx_gasused'] = tx_gasused
net_info['tx_success'] = tx_ok
net_info['tx_failed'] = tx_ko

print(json.dumps(net_info, indent=4))
# print(net_info)
