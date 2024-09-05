import argparse
import json
import string
from web3 import Web3
from utils import get_profile, init_log, say
from tx import send_transaction, confirm_transactions
from termcolor import colored

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', required=True, help="Profile to use")
ap.add_argument(
    '-f', '--filename', required=False, default="scripted.json",
    help="Profile to use"
)
args = vars(ap.parse_args())

node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
    l1_funded_key = \
    get_profile(args['profile'])

init_log(args['profile'], tool='scripted')
scripted_filename = args['filename']
w = Web3(Web3.HTTPProvider(node_url))
sender = w.eth.account.from_key(str(funded_key))
accounts = {}


def create_accounts(accounts_info):
    # "accounts": [
    #     { "name": "A", "balance": 1 },
    #     { "name": "B", "balance": 1 }
    # ],
    global accounts
    for acct_info in accounts_info:
        account = w.eth.account.create()
        eth_amount = acct_info.get('eth_balance', 0)
        if eth_amount:
            tx_hashes = send_transaction(
                ep=node_url, sender_key=funded_key, eth_amount=eth_amount,
                receiver_address=account.address, wait='last'
            )
        acct = {
            'address': account.address,
            'private_key': account.key.hex(),
            'balance': eth_amount
        }
        accounts[acct_info['name']] = acct
        msg = \
            f"Created account {colored(acct_info['name'], 'yellow')} with " \
            f"address={colored(account.address, 'yellow')} and " \
            f"balance={eth_amount}ETH"

        if eth_amount and tx_hashes:
            msg += f" (tx_hash={tx_hashes[0]})"
        say(msg)


def test_transaction(tx_info):
    global accounts
    say(
        f"Running transaction {tx_info['id']}: "
        f"{colored(tx_info['description'], 'yellow')}"
    )
    tx = tx_info.get('transaction')

    # Sender / from
    sender_name = tx.get('from')
    msg = f"Sending from {colored(sender_name, 'yellow')}"
    sender_key = accounts.get(sender_name).get('private_key')

    # Receiver / to
    sc_call = False
    receiver_addr = None
    receiver_name = tx.get('to')
    if receiver_name:
        receiver_addr = accounts.get(receiver_name).get('address')
        msg += f" to {receiver_name}"
        if accounts.get(receiver_name).get('created_by'):
            sc_call = True

    # Amount / values
    eth_amount = tx.get('eth_amount', 0)
    if eth_amount:
        msg += f" {eth_amount}ETH"

    # Data / bytecode
    d = tx.get('data')
    if d:
        d = tx.get('data')
        if d.startswith('0x'):
            d = d[2:]
        if '$' in d:
            sd = string.Template((d))
            _accounts = {k: v['address'] for k, v in accounts.items()}
            # Could be done in a single step, but just in case at some point we
            #  store addresses without the '0x' prefix
            for k, v in _accounts.items():
                if v.startswith('0x'):
                    _accounts[k] = v[2:]
            d = sd.safe_substitute(_accounts)
        msg += f" with {len(d)//2} bytes of data ({d})"

    # Sending transaction
    say(msg)
    tx_hashes = send_transaction(
        ep=node_url, sender_key=sender_key, receiver_address=receiver_addr,
        gas=tx.get('gas', 21000), eth_amount=eth_amount, data=d,
        sc_call=sc_call, wait=False
    )
    tx_hash = tx_hashes[0]
    say(f"Test tx {tx_info['id']} sent, tx_hash={tx_hash}. Confirming...")
    receipts = \
        confirm_transactions(ep=node_url, tx_hashes=tx_hashes, timeout=30)
    if receipts:
        block = int(receipts[0].get('blockNumber'), 16)
        gas_used = int(receipts[0].get('gasUsed'))
        status = int(receipts[0].get('status'), 16)
        if status == 1:
            status = colored('SUCCESS', 'green')
        elif status == 0:
            status = colored('FAILED', 'red')
        contract_address = receipts[0].get('contractAddress')
        save_as = tx.get('save_as')
        tx_id = colored(tx_info['id'], 'green')
        say(
            f"Transaction {tx_id} ({tx_hash}) mined in block {block} "
            f"with {colored(f"gas_used={gas_used}", 'magenta')} and "
            f"status={status}."
        )
        if contract_address and save_as:
            accounts[tx['save_as']] = {
                'address': contract_address,
                'created_by': sender_name
            }
            say(f"Adding account {save_as} with address {contract_address}")
    else:
        tx_id = colored(tx_info['id'], 'red')
        say(f"ERROR: Transaction {tx_id} ({tx_hash}) failed to mine.")


def check_nonce(tx_info):
    global accounts
    say(
        f"Checking nonce {tx_info['id']}: "
        f"{tx_info['description']}"
    )
    check = tx_info.get('check')

    # Params
    expected_nonce = check.get('nonce')
    sender_name = check.get('account')
    sender_addr = accounts.get(sender_name).get('address')
    nonce = w.eth.get_transaction_count(sender_addr)

    if nonce == expected_nonce:
        say(
            f"Nonce for {colored(sender_name, 'yellow')} "
            f"{colored(f"matches {nonce}", 'green')}."
        )
    else:
        say(
            f"Nonce for {colored(sender_name, 'yellow')} " +
            colored(
                f"does NOT match: expected {expected_nonce} got {nonce}",
                'red'
            )
        )


scripted = json.load(open(scripted_filename))
create_accounts(scripted.get('accounts', []))

tests = scripted.get('tests', [])
for test in tests:
    if test.get('enabled', True):
        say("...")
        if test.get('type') == 'transaction':
            test_transaction(test)
        elif test.get('type') == 'check_nonce':
            check_nonce(test)
    else:
        continue
