import time
import json
import random
import argparse
import multiprocessing as mp
from termcolor import colored
from web3 import Web3
from utils import init_log, say, get_log_filename, get_profile, \
    log_tx_per_line, abi_encode_addr
from tx import send_transaction, confirm_transactions, token_transfer, \
    sc_function_call
from geth import get_gas_price
from sc import compile_contract, contracts
from wallets import Wallets

eth_amount = 0.001  # Eth amount to send in txs

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', required=True, help="Profile to use")
ap.add_argument(
    "-c", "--concurrency", required=True, help="concurrent senders")
ap.add_argument("-t", "--txs", required=True, help="txs per sender")
ap.add_argument("-n", "--nonce", required=False, help="funded nonce")
options = (
    ('confirmed', False), ('allconfirmed', False), ('unconfirmed', False),
    ('erc20', False), ('uniswap', False), ('recover', True), ('race', False),
    ('gasprice', False), ('all', False), ('precompileds', False),
    ('pairings', False), ('keccaks', False), ('eventminter', False),
    ('debug', False)
)
action = argparse.BooleanOptionalAction
for (option, default_value) in options:
    ap.add_argument(f'--{option}', action=action, default=default_value)

args = vars(ap.parse_args())

# Number of processes to run concurrently, and txs per process
concurrency = int(args['concurrency'])
txs_per_sender = int(args['txs'])
nonce = int(args['nonce']) if args['nonce'] else None

# If --all, set all tests but NO race
if args['all']:
    for x in options:
        args[x[0]] = True if x[0] not in ('race', 'gasprice', 'debug') \
            else args[x[0]]

# All confirmed can not be run on race mode
if args['race']:
    args['allconfirmed'] = False
    args['unconfirmed'] = False
    args['erc20'] = False  # Right now we send 1 token per contract
    if txs_per_sender < 2:
        raise ValueError("txs must be at least 2 for race mode")

# Set subtests for uniswap
if args['uniswap']:
    args['uv2_pair'] = True
    args['uv2_factory'] = True
    args['uv2_erc20'] = True

# If sc deploy, set tx count multiple of deployed scs
if args['precompileds']:
    _adjusted_txs = False
    precompiled_contract_count = 4
    _multiple_of = precompiled_contract_count

    while (txs_per_sender % _multiple_of != 0):
        _adjusted_txs = True
        txs_per_sender += 1

    if _adjusted_txs:
        say(
            f"Adjusted txs_per_sender to {txs_per_sender} "
            f"to be divisible by {_multiple_of}")


init_log(args['profile'])
node_url, chain_id, funded_key = get_profile(args['profile'])
w = Web3(Web3.HTTPProvider(node_url))
funded_account = Web3().eth.account.from_key(str(funded_key))

send_tx_kwargs = {
    'ep': node_url,
    'chain_id': chain_id,
    'debug': args['debug'],
}

# If eth_amount is not enough to cover gasPrice, increase by 10% until it does
gas_price = get_gas_price(node_url)
while gas_price*21000 > Web3().to_wei(eth_amount, 'ether'):
    say(f"{eth_amount}ETH does not cover gasPrice, increasing by 10%")
    eth_amount = eth_amount * 1.10


def _gas_used_for(tx_hashes, estimate=True, search_for_diff=1):
    # search_for_diff is the number of different gasUsed values to find
    if not tx_hashes:
        return 0

    if len(tx_hashes) % search_for_diff != 0:
        raise ValueError(
            f"tx_hashes length ({len(tx_hashes)}) is not divisible by "
            f"search_for_diff ({search_for_diff})")

    gasused_found = []

    if estimate:
        i = 0
        while (len(gasused_found) < search_for_diff):
            receipts = confirm_transactions(node_url, [tx_hashes[i]])
            if receipts[0]['gasUsed'] not in gasused_found:
                gasused_found.append(receipts[0]['gasUsed'])
            i += 1
        return int((len(tx_hashes)/search_for_diff) * sum(gasused_found))
    else:
        gas_used = 0
        receipts = confirm_transactions(node_url, tx_hashes)
        for receipt in receipts:
            gas_used += receipt['gasUsed']
        return gas_used


bench_results = [
    f"{node_url}:{w.client_version}",
    f"profile:{args['profile']}",
    f"processes:{concurrency}",
    f"tx_per_sender:{txs_per_sender}"
]
say(
    "** Starting Benchmark | Logging everything to " +
    colored(f"{get_log_filename()}", 'magenta') +
    " | URL: " + colored(f"{node_url} ({w.client_version})", 'magenta') +
    " | Master account: " + colored(f"{funded_account.address}", 'magenta'),
    to_log=False
    )

wallets_mgr = Wallets(
    node_url=node_url, funded_key=funded_key, args=args,
    concurrency=concurrency, txs_per_sender=txs_per_sender,
    eth_amount=eth_amount, nonce=nonce
)


if args['gasprice']:
    def _do_gasprice():
        for i in range(txs_per_sender):
            _ = get_gas_price(node_url)

    processes = []
    for x in range(concurrency):
        process = mp.Process(target=_do_gasprice())
        processes.append(process)

    start_time = time.time()
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    end_time = time.time()
    _total_time = end_time - start_time
    _qps = (concurrency*txs_per_sender)/_total_time

    say(f"Time to query gas {txs_per_sender} times for {concurrency} procs: "
        f"{_total_time:.2f} seconds | Avg speed: {_qps:.2f} QPS | Query gas")
    bench_results.append(f"gasprice:{_qps:.2f}")


def _test_simple_tx(test_name):
    say(colored(f"**  {test_name} tests", "red"), to_log=False)

    def _do_test(test_name, q, sender, receiver):
        _gas_price = get_gas_price(node_url)
        if test_name == 'allconfirmed':
            _wait = 'all'
        elif test_name == 'confirmed':
            _wait = 'last'
        elif test_name == 'unconfirmed':
            _wait = False

        if args['race'] and test_name == 'confirmed':
            _tx_hashes = send_transaction(
                sender_key=sender.key.hex(), receiver_address=receiver.address,
                eth_amount=eth_amount, gas_price=gas_price, nonce=1,
                wait=False, gas_from_amount=True, check_balance=False,
                count=txs_per_sender-1, **send_tx_kwargs
            )
            _tx_hash_list = send_transaction(
                sender_key=sender.key.hex(), receiver_address=receiver.address,
                eth_amount=eth_amount, gas_price=_gas_price, nonce=0,
                wait=False, gas_from_amount=True, check_balance=False, count=1,
                **send_tx_kwargs
            )
            _tx_hashes.insert(0, _tx_hash_list[0])
            # That will confirm just the last tx because of receipts=False
            confirm_transactions(node_url, _tx_hashes, receipts=False)
        else:
            _tx_hashes = send_transaction(
                sender_key=sender.key.hex(), receiver_address=receiver.address,
                eth_amount=eth_amount, gas_price=_gas_price, nonce=0,
                wait=_wait, gas_from_amount=True, check_balance=False,
                count=txs_per_sender, **send_tx_kwargs
            )
        q.put(_tx_hashes)

    _wallets = wallets_mgr.get_wallets(test_name)
    processes = []
    queues = []
    for x in range(len(_wallets['senders'])):
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_test,
            args=(
                test_name, q, _wallets['senders'][x], _wallets['receivers'][x]
            )
        )
        queues.append(q)
        processes.append(process)

    start_time = time.time()
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    end_time = time.time()
    _total_time = end_time - start_time
    _tx_count = concurrency*txs_per_sender
    _tps = _tx_count/_total_time

    tx_hashes = []
    for q in queues:
        while not q.empty():
            tx_hashes.extend(q.get())

    if tx_hashes:
        say(f"Double check for {test_name} txs confirmation...")
        confirm_transactions(
            node_url, tx_hashes, timeout=600, poll_latency=0.5, receipts=False)

    _total_gas = _gas_used_for(tx_hashes)
    _gps = int(_total_gas/_total_time)

    say(f"{test_name} Tx Hashes:", output=False)
    for x in range(0, len(tx_hashes), log_tx_per_line):
        say(tx_hashes[x:x+log_tx_per_line], output=False)

    say("Time to send " +
        colored(
            f"{txs_per_sender} txs for {concurrency} senders to "
            f"{concurrency} receivers", "blue"
        ) + f" (total of {_tx_count} txs): " +
        colored(f"{_total_time:.2f}s", "yellow") + " | " +
        colored(f"TPS:{_tps:.2f}", "green") + " | " +
        colored(f"Gas:{_total_gas}", "yellow") + " | " +
        colored(f"Gas/s:{_gps}", "green") + " | " +
        colored(f"{test_name} txs", "blue"),
        to_log=False
        )

    bench_results.append(f"{test_name}:{_tps:.2f},{_gps}")
    wallets_mgr.recover_funds(_wallets)


if args['allconfirmed']:
    _test_simple_tx('allconfirmed')


if args['confirmed']:
    _test_simple_tx('confirmed')


if args['unconfirmed']:
    _test_simple_tx('unconfirmed')


def _do_sc_deploy(q, creator, bytecode, gas, nonce=0, count=txs_per_sender):
    _gas_price = get_gas_price(node_url)
    if args['race']:
        _tx_hashes = send_transaction(
            sender_key=creator.key.hex(), gas_price=_gas_price, count=count-1,
            nonce=nonce+1, data=bytecode, gas=gas, wait=False, **send_tx_kwargs
        )
        _tx_hash_list = send_transaction(
            sender_key=creator.key.hex(), gas_price=_gas_price, count=1,
            nonce=nonce, data=bytecode, gas=gas, wait=False, **send_tx_kwargs
        )
        _tx_hashes.insert(0, _tx_hash_list[0])
    else:
        _tx_hashes = send_transaction(
            sender_key=creator.key.hex(), gas_price=_gas_price, count=count,
            nonce=nonce, data=bytecode, gas=gas, wait='last',
            # We allow up to 2 second per global tx
            wait_timeout=max(5, 2*concurrency*txs_per_sender),
            **send_tx_kwargs
        )
    q.put((creator.key.hex(), _tx_hashes))


def _test_create_sc(test_name, recover=True, extra_bytecode=None):
    say(colored(f"** {test_name} create tests", "red"), to_log=False)
    abi, bytecode = \
        compile_contract(contract=test_name)
    _gas = contracts[test_name]['create_gas']
    _wallets = wallets_mgr.get_wallets(test_name)

    if extra_bytecode:
        bytecode += extra_bytecode

    processes = []
    queues = []
    for x in range(len(_wallets['senders'])):
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_sc_deploy,
            args=(q, _wallets['senders'][x], bytecode, _gas)
        )
        queues.append(q)
        processes.append(process)

    start_time = time.time()
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    end_time = time.time()
    _total_time = end_time - start_time
    _tx_count = concurrency*txs_per_sender
    _tps = _tx_count/_total_time

    results = []
    tx_hashes = []
    for q in queues:
        while not q.empty():
            r = q.get()
            results.append(r)
        tx_hashes.extend(r[1])
    _total_gas = _gas_used_for(tx_hashes)
    _gps = int(_total_gas/_total_time)

    say(f"{test_name} create Tx Hashes:", output=False)
    for x in range(0, len(tx_hashes), log_tx_per_line):
        say(tx_hashes[x:x+log_tx_per_line], output=False)

    contracts_info = []
    for r in results:
        private_key = r[0]
        tx_hashes = r[1]
        receipts = confirm_transactions(node_url, tx_hashes)
        _contracts = []
        for receipt in receipts:
            _contracts.append(receipt['contractAddress'])
        contracts_info.append((private_key, _contracts))

    say("Time to create " +
        colored(
            f"{txs_per_sender} {test_name} sc for "
            f"{concurrency} senders", "blue") +
        f" (total of {_tx_count} {test_name} scs): " +
        colored(f"{_total_time:.2f}s", "yellow") + " | " +
        colored(f"TPS:{_tps:.2f}", "green") + " | " +
        colored(f"Gas:{_total_gas}", "yellow") + " | " +
        colored(f"Gas/s:{_gps}", "green") + " | " +
        colored(f"{test_name} SC last confirmed", "blue"),
        to_log=False
        )

    bench_results.append(f"{test_name}_create:{_tps:.2f},{_gps}")

    if recover:
        wallets_mgr.recover_funds(_wallets)

    return (contracts_info, _wallets, abi)


if args['erc20']:
    (contracts_info, erc20_wallets, erc20_abi) = \
        _test_create_sc(test_name='erc20', recover=False)
    token_receivers = erc20_wallets['receivers']

    say(colored("** ERC20 transfer tests", "red"), to_log=False)

    def _do_erc20txs(q, sender_key, dst_addr, sender_nonce, contract_addrs):
        _w = Web3(Web3.HTTPProvider(node_url))
        _gas_price = get_gas_price(node_url)
        _tx_hashes = []
        _nonce = sender_nonce
        for addr in contract_addrs:
            wei_amount = Web3().to_wei(1, 'ether')
            _tx_hash = token_transfer(
                node_url, _w, token_contract=addr, token_abi=erc20_abi,
                src_prvkey=sender_key, dst_addr=dst_addr, gas_price=_gas_price,
                wei_amount=wei_amount, nonce=_nonce, wait=False
            )
            _nonce += 1
            _tx_hashes.append(_tx_hash)
        # We confirm just the last one
        _ = confirm_transactions(node_url, [_tx_hash])
        q.put(_tx_hashes)

    processes = []
    queues = []
    for c_info in contracts_info:
        private_key = c_info[0]
        _contracts = c_info[1]
        dst_addr = token_receivers.pop(0).address
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_erc20txs,
            args=(q, private_key, dst_addr, txs_per_sender, _contracts)
        )
        queues.append(q)
        processes.append(process)

    start_time = time.time()
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    end_time = time.time()
    _total_time = end_time - start_time
    _tx_count = concurrency*txs_per_sender
    _tps = _tx_count/_total_time

    tx_hashes = []
    for q in queues:
        while not q.empty():
            tx_hashes.extend(q.get())
    _total_gas = _gas_used_for(tx_hashes)
    _gps = int(_total_gas/_total_time)

    say("ERC20 transfer Tx Hashes:", output=False)
    for x in range(0, len(tx_hashes), log_tx_per_line):
        say(tx_hashes[x:x+log_tx_per_line], output=False)

    say("Time to send " +
        colored(
            f"{txs_per_sender} token txs for {concurrency} senders", "blue") +
        f" (total of {_tx_count} token txs): " +
        colored(f"{_total_time:.2f}s", "yellow") + " | " +
        colored(f"TPS:{_tps:.2f}", "green") + " | " +
        colored(f"Gas:{_total_gas}", "yellow") + " | " +
        colored(f"Gas/s:{_gps}", "green") + " | " +
        colored("Last confirmed Token Tx", "blue"),
        to_log=False
        )

    bench_results.append(f"erc20_txs:{_tps:.2f},{_gps}")
    wallets_mgr.recover_funds(erc20_wallets)


if args['uniswap']:
    _test_create_sc(test_name='uv2_pair')
    _test_create_sc(
        test_name='uv2_factory',
        extra_bytecode=abi_encode_addr(funded_account.address))
    _test_create_sc(test_name='uv2_erc20')


if args['precompileds']:
    (contracts_info, laia1_wallets, _) = \
        _test_create_sc(test_name='precompileds', recover=False)

    say(colored("** precompileds tests", "red"), to_log=False)
    assert txs_per_sender % precompiled_contract_count == 0, \
        "txs_per_sender must be multiple of 4"
    _txs_per_sender = txs_per_sender//precompiled_contract_count

    def _do_laia1(q, sender_key, sender_nonce, contract_addr):
        _gas_price = get_gas_price(node_url)
        _all_tx_hashes = []
        _nonce = sender_nonce
        call_gas = contracts['precompileds']['call_gas']

        for _wei_amount in (1, 2, 3, 4):
            _tx_hashes = send_transaction(
                sender_key=sender_key, receiver_address=contract_addr,
                gas_price=_gas_price, nonce=_nonce, wait='last',
                check_balance=False, gas=call_gas, wei_amount=_wei_amount,
                count=_txs_per_sender, **send_tx_kwargs
            )
            _nonce += _txs_per_sender
            _all_tx_hashes.extend(_tx_hashes)
        q.put(_all_tx_hashes)

    processes = []
    queues = []
    for c_info in contracts_info:
        private_key = c_info[0]
        _contracts = c_info[1]
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_laia1,
            # Only using first contract to send all the tests
            args=(q, private_key, txs_per_sender, _contracts[0])
        )
        queues.append(q)
        processes.append(process)

    start_time = time.time()
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    end_time = time.time()
    _total_time = end_time - start_time
    _tx_count = concurrency*txs_per_sender
    _tps = _tx_count/_total_time

    tx_hashes = []
    for q in queues:
        while not q.empty():
            tx_hashes.extend(q.get())
    _total_gas = \
        _gas_used_for(tx_hashes, search_for_diff=precompiled_contract_count)
    _gps = int(_total_gas/_total_time)

    say("precompileds Tx Hashes:", output=False)
    for x in range(0, len(tx_hashes), log_tx_per_line):
        say(tx_hashes[x:x+log_tx_per_line], output=False)

    say("Time to send " +
        colored(
            f"{txs_per_sender} precompileds txs for "
            f"{concurrency} senders", "blue") +
        f" (total of {_tx_count} precompileds txs): " +
        colored(f"{_total_time:.2f}s", "yellow") + " | " +
        colored(f"TPS:{_tps:.2f}", "green") + " | " +
        colored(f"Gas:{_total_gas}", "yellow") + " | " +
        colored(f"Gas/s:{_gps}", "green") + " | " +
        colored("precompileds Tx last confirmed", "blue"),
        to_log=False
        )

    bench_results.append(f"precompileds_txs:{_tps:.2f},{_gps}")
    wallets_mgr.recover_funds(laia1_wallets)


if args['pairings']:
    PAIRINGS_FILE = './contracts/randomNumsECPARIGINS.json'
    p = open(PAIRINGS_FILE, 'r')
    all_pairings = json.load(p)

    (contracts_info, laia2_wallets, laia2_abi) = \
        _test_create_sc(test_name='pairings', recover=False)

    say(colored("** pairings tests", "red"), to_log=False)

    def _do_laia2(q, sender_key, sender_nonce, contract_addr):
        _gas_price = get_gas_price(node_url)
        _all_tx_hashes = []
        _nonce = sender_nonce
        call_gas = contracts['pairings']['call_gas']

        for _i in range(txs_per_sender):
            w_key_params = random.choice(all_pairings)
            params = [int(x) for x in w_key_params.values()]
            (_tx_hash, _result) = sc_function_call(
                node_url, w, sender_key, contract_addr,
                laia2_abi, 'ecPairings',
                params, gas_price=_gas_price,
                gas=call_gas, nonce=_nonce, result_function='output'
            )
            say(f"pairs:{params} | result:{_result}")
            _nonce += 1
            _all_tx_hashes.append(_tx_hash)
        q.put(_all_tx_hashes)

    processes = []
    queues = []
    for c_info in contracts_info:
        private_key = c_info[0]
        _contracts = c_info[1]
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_laia2,
            # Only using first contract to send all the tests
            args=(q, private_key, txs_per_sender, _contracts[0])
        )
        queues.append(q)
        processes.append(process)

    start_time = time.time()
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    end_time = time.time()
    _total_time = end_time - start_time
    _tx_count = concurrency*txs_per_sender
    _tps = _tx_count/_total_time

    tx_hashes = []
    for q in queues:
        while not q.empty():
            tx_hashes.extend(q.get())
    _total_gas = \
        _gas_used_for(tx_hashes)
    _gps = int(_total_gas/_total_time)

    say("pairings Tx Hashes:", output=False)
    for x in range(0, len(tx_hashes), log_tx_per_line):
        say(tx_hashes[x:x+log_tx_per_line], output=False)

    say("Time to send " +
        colored(
            f"{txs_per_sender} pairings txs for "
            f"{concurrency} senders", "blue") +
        f" (total of {_tx_count} pairings txs): " +
        colored(f"{_total_time:.2f}s", "yellow") + " | " +
        colored(f"TPS:{_tps:.2f}", "green") + " | " +
        colored(f"Gas:{_total_gas}", "yellow") + " | " +
        colored(f"Gas/s:{_gps}", "green") + " | " +
        colored("pairings Tx last confirmed", "blue"),
        to_log=False
        )

    bench_results.append(f"pairings_txs:{_tps:.2f},{_gps}")
    wallets_mgr.recover_funds(laia2_wallets)


if args['keccaks']:
    _test_create_sc(test_name='keccaks')


if args['eventminter']:
    _test_create_sc(test_name='eventminter')


say(f"Results: {bench_results}", output=False)
say(colored(bench_results, "magenta"), to_log=False)
wallets_mgr.close()
