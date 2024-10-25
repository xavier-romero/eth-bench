import argparse
import json
import string
import random
from web3 import Web3
from utils import get_profile, init_log, say
from tx import send_transaction, confirm_transactions, sc_function_call
from sc import compile_contract
from termcolor import colored

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', required=True, help="Profile to use")
ap.add_argument(
    '-f', '--filename', required=False, default="scripted.json",
    help="Profile to use"
)
args = vars(ap.parse_args())

node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
    l1_funded_key, _ = \
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
            msg += f" (tx_hash: {tx_hashes[0]})"
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
    sender_key = accounts.get(sender_name).get('private_key')
    sender_addr = accounts.get(sender_name).get('address')
    sender_nonce = w.eth.get_transaction_count(sender_addr)
    msg = \
        f"Sending from {colored(sender_name, 'yellow')}(nonce={sender_nonce})"

    # Count
    tx_count = tx.get('count', 1)

    # Contract ABI
    # Var is writen when SC created, and read when SC called
    contract_abi = None

    # Receiver / to
    sc_call = False
    receiver_addr = None
    receiver_name = tx.get('to')
    if receiver_name:
        receiver_addr = accounts.get(receiver_name).get('address')
        msg += f" to {receiver_name}"
        if accounts.get(receiver_name).get('created_by'):
            sc_call = True
        contract_abi = accounts.get(receiver_name).get('abi')

    # Amount / values
    eth_amount = tx.get('eth_amount', 0)
    if eth_amount:
        msg += f" {eth_amount}ETH"

    tx_hashes = []
    for i in range(tx_count):
        # Loop, so we replace random_byte for each tx

        # Data / bytecode / method
        d = tx.get('data')
        dfc = tx.get('data_from_contract')
        method = tx.get('method')
        method_params = tx.get('method_params', [])

        # Incompatible params
        if d and dfc:
            raise Exception("Cannot have both data and data_from_contract")
        if method:
            if not sc_call:
                raise Exception("Method call without contract destination")
            if (d or dfc):
                raise Exception("Cannot have both method and data")

        if d:
            if d.startswith('0x'):
                d = d[2:]
            if '$' in d:
                sd = string.Template((d))
                _accounts = {k: v['address'] for k, v in accounts.items()}
                _accounts['random_byte'] = f"{random.randint(0, 256):02x}"
                # Could be done in a single step, but just in case at some
                #  point we store addresses without the '0x' prefix
                for k, v in _accounts.items():
                    if v.startswith('0x'):
                        _accounts[k] = v[2:]
                d = sd.safe_substitute(_accounts)
            msg_i = f" with {len(d)//2} bytes of data ({d})"
            say(msg + msg_i)
        elif dfc:
            try:
                contract_abi, d = compile_contract(dfc)
            except KeyError:
                raise Exception(f"Contract {dfc} not found")
            msg_i = f" with {len(d)//2} bytes of data ({d})"
            say(msg + msg_i)
        elif method:
            msg_i = f" calling method {colored(method, 'magenta')} " \
                f"with params {colored(method_params, 'magenta')}"
            say(msg + msg_i)
        else:
            say(msg)
        # Sending transaction
        if method:
            assert contract_abi, "Contract ABI not found"
            _tx_hash, _ = sc_function_call(
                ep=node_url, w=w, caller_privkey=sender_key,
                contract_addr=receiver_addr, contract_abi=contract_abi,
                contract_function=method, contract_params=method_params,
                gas=tx.get('gas', 21000)
            )
            _tx_hashes = [_tx_hash]
        else:
            _tx_hashes = send_transaction(
                ep=node_url, sender_key=sender_key,
                receiver_address=receiver_addr, gas=tx.get('gas', 21000),
                eth_amount=eth_amount, data=d, sc_call=sc_call, wait=False,
                count=1
            )
        tx_hashes.extend(_tx_hashes)
    tx_hash = tx_hashes[0]
    if tx_count > 1:
        tx_hash = tx_hashes[-1]
        say(
            f"Test {tx_count} txs {tx_info['id']} sent, "
            f"last tx_hash: {tx_hash}"
        )
    else:
        say(f"Test tx {tx_info['id']} sent, tx_hash: {tx_hash}")
    receipts = \
        confirm_transactions(ep=node_url, tx_hashes=tx_hashes, timeout=30)
    for receipt in receipts:
        block = int(receipt.get('blockNumber'), 16)
        gas_used = int(receipt.get('gasUsed'))
        status = int(receipt.get('status'), 16)
        tx_hash = receipt.get('transactionHash')
        if status == 1:
            status = colored('SUCCESS', 'green')
        elif status == 0:
            status = colored('FAILED', 'red')
        contract_address = receipt.get('contractAddress')
        save_as = tx.get('save_as')
        tx_id = colored(tx_info['id'], 'green')
        say(
            f"Transaction {tx_id} ({tx_hash}) mined in block {block} "
            f"with {colored(f'gas_used={gas_used}', 'magenta')} and "
            f"status={status}."
        )
        # If count > 1, the address for the last one will be saved
        if contract_address and save_as:
            accounts[tx['save_as']] = {
                'address': contract_address,
                'created_by': sender_name,
                'abi': contract_abi
            }
            say(f"Adding account {save_as} with address {contract_address}")
    if not receipts:
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
            f"{colored(f'matches {nonce}', 'green')}."
        )
    else:
        say(
            f"Nonce for {colored(sender_name, 'yellow')} " +
            colored(
                f"does NOT match: expected {expected_nonce} got {nonce}",
                'red'
            )
        )


def check_balance(tx_info):
    global accounts
    say(
        f"Checking balance {tx_info['id']}: "
        f"{tx_info['description']}"
    )
    check = tx_info.get('check')

    # Params
    gt = check.get('gt')
    lt = check.get('lt')
    sender_name = check.get('account')
    sender_addr = accounts.get(sender_name).get('address')
    balance = w.eth.get_balance(sender_addr)
    balance = w.from_wei(balance, 'ether')

    if gt is not None and balance > gt:
        say(
            f"Balance for {colored(sender_name, 'yellow')} "
            f"{colored(f'is greater than {gt}: {balance}', 'red')}."
        )
    elif lt is not None and balance < lt:
        say(
            f"Balance for {colored(sender_name, 'yellow')} "
            f"{colored(f'is less than {lt}: {balance}', 'red')}."
        )
    else:
        say(
            f"Balance for {colored(sender_name, 'yellow')} "
            f"{colored(f'is {balance}', 'green')}, within expected range."
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
        elif test.get('type') == 'check_balance':
            check_balance(test)
        elif test.get('type') == 'stop':
            say("Stopping execution")
            break
    else:
        continue
