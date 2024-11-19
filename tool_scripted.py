#!/usr/bin/env python3
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
ap.add_argument('-p', '--profile', help="Profile to use", default='default')
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
say(f"Executing scripted transactions from {scripted_filename}")
w = Web3(Web3.HTTPProvider(node_url))
sender = w.eth.account.from_key(str(funded_key))
accounts = {}

MAX_GAS = 29999999


def _wrap_deployedcode(code: str) -> str:
    if code.startswith('0x'):
        code = code[2:]

    codecopy_size = len(code) // 2
    codecopy_offset = 10 + 8  # 10 for CODECOPY + 8 for RETURN

    # CODECOPY destOffset, offset, size
    # RETURN offset, size

    # 0x63{codecopy_size:08x} --> PUSH4 for the size of the data
    # 0x60{codecopy_offset:02x} --> PUSH1 for code offset
    # 0x6000 --> PUSH1 00 to indicate the destination offset in memory
    # 0x39 --> CODECOPY
    # 0x63{codecopy_size:08x} --> PUSH4 for the size of the data
    # 0x6000 --> PUSH1 00 to indicate that it starts from offset 0
    # 0xF3 --> RETURN
    return \
        f"63{codecopy_size:08x}" \
        f"60{codecopy_offset:02x}" \
        "6000" \
        "39" \
        f"63{codecopy_size:08x}" \
        "6000" \
        "F3" \
        f"{code}"


def create_accounts(accounts_info):
    # "accounts": [
    #     { "name": "A", "eth_balance": 1 },
    #     { "name": "B", "eth_balance": 1 }
    #     { "name": "C", "code": 0x001122334455 }
    # ],
    global accounts
    last_txhash = None
    for acct_info in accounts_info:
        eth_amount = 0
        if 'eth_balance' in acct_info and not acct_info.get('code'):
            _account = w.eth.account.create()
            acct_address = Web3.to_checksum_address(_account.address)
            eth_amount = acct_info['eth_balance']
            if eth_amount:
                tx_hashes = send_transaction(
                    ep=node_url, sender_key=funded_key, eth_amount=eth_amount,
                    receiver_address=acct_address, wait=None
                )
                last_txhash = tx_hashes[0]
            acct = {
                'address': acct_address,
                'private_key': _account.key.hex(),
                'balance': eth_amount
            }
            msg = \
                f"Created account {colored(acct_info['name'], 'yellow')} " \
                f"with address={colored(acct_address, 'yellow')} and " \
                f"balance={eth_amount}ETH"
            if eth_amount and tx_hashes:
                msg += f" (tx_hash: {tx_hashes[0]})"
        elif acct_info.get('code'):
            # Code is deployed bytecode so we need to wrap it
            bytecode = _wrap_deployedcode(acct_info['code'])
            tx_hashes = send_transaction(
                ep=node_url, sender_key=funded_key, data=bytecode,
                wait=None, gas=29999999
            )
            _receipts = confirm_transactions(
                    ep=node_url, tx_hashes=tx_hashes, receipts=True
            )
            last_txhash = None  # Already confirmed
            acct_address = \
                Web3.to_checksum_address(_receipts[0]['contractAddress'])
            acct = {
                'address': acct_address,
                'balance': 0,
                'created_by': 'master',
                'abi': None
            }
            msg = \
                f"Created contract {colored(acct_info['name'], 'yellow')} " \
                f"with address={colored(acct_address, 'yellow')}" \
                f" (tx_hash: {tx_hashes[0]})"

        else:
            raise Exception("Account without balance or code")

        accounts[acct_info['name']] = acct
        say(msg)

    if last_txhash:
        confirm_transactions(ep=node_url, tx_hashes=[last_txhash], timeout=30)


def test_transaction(tx_info):
    global accounts
    say(
        f"Running transaction {tx_info['id']}: "
        f"{colored(tx_info['description'], 'yellow')}"
    )
    tx = tx_info.get('transaction')

    # Sender / from
    sender_name = tx.get('from')
    sender_addr = accounts.get(sender_name, {}).get('address')
    sender_key = accounts.get(sender_name, {}).get('private_key')
    if not (sender_addr and sender_key):
        say(f"Skipping transaction {tx_info['id']}, sender not found")
        return
    sender_nonce = w.eth.get_transaction_count(sender_addr)
    msg = \
        f"Sending from {colored(sender_name, 'yellow')}(nonce={sender_nonce})"

    # Count
    tx_count = tx.get('count', 1)

    # Gas
    tx_gas = min(
        max(tx.get('gas', 21000), 21000),
        MAX_GAS
    )

    # Contract ABI
    # Var is writen when SC created, and read when SC called
    contract_abi = None

    # Receiver / to
    sc_call = False
    receiver_addr = None
    receiver_name = tx.get('to')
    if receiver_name and receiver_name != '0x':
        receiver_addr = accounts.get(receiver_name, {}).get('address')
        # Some tests from zkevm-testvector use the address directly
        if not receiver_addr:
            try:
                receiver_addr = Web3.to_checksum_address(receiver_name)
            except ValueError:
                say(
                    colored(f"Receiver {receiver_name} not valid, "
                            "setting 0x0 instead", 'red')
                )
                receiver_addr = "0x0000000000000000000000000000000000000000"
            msg += " DIRECT_ADDR"
        msg += f" to {receiver_name}"
        if accounts.get(receiver_name, {}).get('created_by'):
            sc_call = True
        contract_abi = accounts.get(receiver_name, {}).get('abi')

    # Amount / values
    eth_amount = tx.get('eth_amount', 0)
    wei_amount = tx.get('wei_amount', 0)
    if eth_amount:
        msg += f" {eth_amount}ETH"
    elif wei_amount:
        msg += f" {wei_amount}wei"

    tx_chain_id = tx.get('chain_id', chain_id)

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
                gas=tx_gas, chain_id=tx_chain_id, raw_retries=3
            )
            _tx_hashes = [_tx_hash]
        else:
            kwargs = {
                'ep': node_url,
                'sender_key': sender_key,
                'receiver_address': receiver_addr,
                'gas': tx_gas,
                'data': d,
                'sc_call': sc_call,
                'wait': False,
                'raise_on_error': False,
                'chain_id': tx_chain_id,
                'raw_retries': 3,
            }
            if eth_amount:
                kwargs['eth_amount'] = eth_amount
            elif wei_amount:
                kwargs['wei_amount'] = wei_amount

            _tx_hashes = send_transaction(**kwargs)

        if not _tx_hashes:
            say(
                colored(f"ERROR: Transaction {tx_info['id']} "
                        "failed to send.", 'red')
            )
            return
        else:
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
                'address': Web3.to_checksum_address(contract_address),
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
    wei_balance = w.eth.get_balance(sender_addr)
    balance = w.from_wei(wei_balance, 'ether')

    say(f"Balance in wei is: {colored(wei_balance, 'magenta')}")
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


def _check_storage_key(acct_name, k, v):
    if isinstance(k, str):
        k = int(k, base=16)
    if isinstance(v, str):
        v = int(v, base=16)

    say(f"Checking storage key {k} for {colored(acct_name, 'yellow')}")

    # If the account name is not found, use the name as address.
    act_addr = \
        accounts.get(acct_name, {}) \
        .get('address', Web3.to_checksum_address(acct_name))
    storage_value = w.eth.get_storage_at(act_addr, k)
    storage_value = int(storage_value.hex(), base=16)

    if storage_value == v:
        say(
            f"Storage for {colored(acct_name, 'yellow')} "
            f"key {colored(k, 'yellow')} "
            f"{colored(f'matches {v}', 'green')}."
        )
    else:
        say(
            f"Storage for {colored(acct_name, 'yellow')} "
            f"key {colored(k, 'yellow')} " +
            colored(
                f"does NOT match: expected {v} got "
                f"{storage_value}", 'red'
            )
        )


def check_storage(tx_info):
    global accounts
    check = tx_info.get('check')
    acct_name = check.get('account')

    # Params
    k = check.get('storage_key')
    if k:
        expected_value = check.get('storage_value')
        _check_storage_key(acct_name, k, expected_value)

    storage = check.get('storage', {})
    for k, v in storage.items():
        _check_storage_key(acct_name, k, v)


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
        elif test.get('type') == 'check_storage':
            check_storage(test)
        elif test.get('type') == 'stop':
            say("Stopping execution")
            break
    else:
        continue
