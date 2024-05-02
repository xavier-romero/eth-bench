import time
import argparse
import multiprocessing as mp
from termcolor import colored
from web3 import Web3
from utils import init_log, say, get_log_filename, create_wallets, \
    get_profile, log_tx_per_line, abi_encode_addr
from tx import send_transaction, confirm_transactions, token_transfer, \
    gas_price_factor
from geth import get_gas_price, get_transaction_count
from sc import compile_contract, contracts

eth_amount = 0.001  # Eth amount to send in txs

ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', required=True, help="Profile to use")
ap.add_argument(
    "-c", "--concurrency", required=True, help="concurrent senders")
ap.add_argument("-t", "--txs", required=True, help="txs per sender")
options = (
    ('confirmed', False), ('allconfirmed', False), ('unconfirmed', False),
    ('erc20create', False), ('erc20txs', False), ('uniswap', False),
    ('recover', True), ('race', False), ('gasprice', False), ('all', False),
    ('precompileds', False), ('pairings', False), ('complex', False),
    ('debug', False)
)
action = argparse.BooleanOptionalAction
for (option, default_value) in options:
    ap.add_argument(f'--{option}', action=action, default=default_value)

args = vars(ap.parse_args())

# Number of processes to run concurrently, and txs per process
concurrency = int(args['concurrency'])
txs_per_sender = int(args['txs'])

# If --all, set all tests but NO race
if args['all']:
    for x in options:
        args[x[0]] = True if x[0] not in ('race', 'gasprice', 'debug') \
            else args[x[0]]
# ERc20 txs requires erc20create
if args['erc20txs']:
    args['erc20create'] = True
# All confirmed can not be run on race mode
if args['race']:
    args['allconfirmed'] = False
    args['unconfirmed'] = False
    args['erc20txs'] = False  # Right now we send 1 token per contract
    if txs_per_sender < 2:
        raise ValueError("txs must be at least 2 for race mode")
# If sc deploy, set tx count multiple of deployed scs
if args['uniswap'] or args['precompileds']:
    _adjusted_txs = False
    _multiple_of = 12
    uniswap_contract_count = 3
    precompiled_contract_count = 4

    if not args['uniswap']:
        # just precompileds enabled:
        _multiple_of = precompiled_contract_count
    elif not args['precompileds']:
        # just uniswap enabled:
        _multiple_of = uniswap_contract_count

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
funded_account = w.eth.account.from_key(str(funded_key))

send_tx_kwargs = {
    'ep': node_url,
    'chain_id': chain_id,
    'debug': args['debug'],
}

# If eth_amount is not enough to cover gasPrice, increase by 10% until it does
gas_price = get_gas_price(node_url)
while gas_price*21000 > w.to_wei(eth_amount, 'ether'):
    say(f"{eth_amount}ETH does not cover gasPrice, increasing by 10%")
    eth_amount = eth_amount * 1.10


def _prepare_wallets(amount=eth_amount*txs_per_sender):
    funded_nonce = \
        get_transaction_count(node_url, funded_account.address, 'latest')
    funded_nonce_pending = \
        get_transaction_count(node_url, funded_account.address, 'pending')
    funded_gas_factor = 1

    if funded_nonce_pending != funded_nonce:
        say("WARNING: "
            f"Pending ({funded_nonce_pending}) and Latest ({funded_nonce}) "
            f"nonces are different for {funded_account.address}"
            )
        # So we can replace existing txs
        funded_gas_factor = 1.5

    _wallets = create_wallets(w, concurrency)
    _gas_price = get_gas_price(node_url)

    _start = time.time()
    for _sender in _wallets['senders']:
        _tx_hashes = send_transaction(
            sender_key=funded_key, receiver_address=_sender.address,
            eth_amount=amount, nonce=funded_nonce,
            gas_price=int(_gas_price*funded_gas_factor), wait=False,
            **send_tx_kwargs
        )
        if _tx_hashes:
            funded_nonce += 1

    # Confirming last one is enough (its already an array):
    _ = confirm_transactions(
        node_url, _tx_hashes, timeout=600, poll_latency=0.5)
    _end = time.time()
    _n = len(_wallets['senders'])
    say(
        f"Funded {_n} senders with {amount*txs_per_sender:.6f}ETH each, using "
        f"funds from {funded_account.address} in {_end-_start:.2f} seconds"
        f" | Last used nonce: {funded_nonce}"
        # f" | {_n/(_end-_start):.2f} Sequential TPS"
    )

    return _wallets


def _recover_funds(wallets):
    if not args['recover']:
        return

    _priv_keys_hex = [x.key.hex() for x in wallets['senders']]
    _priv_keys_hex += [x.key.hex() for x in wallets['receivers']]

    _start = time.time()
    _all_tx_hashes = []
    if args['debug']:
        say("Recovering funds from senders/receivers back to main account")
    for _priv_key_hex in _priv_keys_hex:
        _tx_hashes = send_transaction(
            sender_key=_priv_key_hex, receiver_address=funded_account.address,
            all_balance=True, wait=False, check_balance=True,
            raise_on_error=False, gas_from_amount=True, **send_tx_kwargs
        )
        _all_tx_hashes.extend(_tx_hashes)
    if _all_tx_hashes:
        _ = confirm_transactions(
            node_url, _all_tx_hashes[-1:], timeout=600, poll_latency=0.5)
    _end = time.time()

    _n = len(_tx_hashes)
    if _tx_hashes:
        say("Recover funds Tx Hashes:", output=False)
        for x in range(0, len(_tx_hashes), log_tx_per_line):
            say(_tx_hashes[x:x+log_tx_per_line], output=False)

    say(f"Time to recover funds from {_n} senders/receivers back to "
        f"main account {funded_account.address}: "
        f"{_end-_start:.2f} seconds | Avg speed: {_n/(_end-_start):.2f} TPS | "
        f"Confirmed txs, +nonce check, +balance check, +gas price check")


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
    colored(f"{get_log_filename()}", 'magenta'),
    to_log=False
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


if args['allconfirmed']:
    say(colored("** All confirmed tests", "red"), to_log=False)

    def _do_all_confirmed(q, sender, receiver):
        _gas_price = get_gas_price(node_url)
        _tx_hashes = send_transaction(
            sender_key=sender.key.hex(), receiver_address=receiver.address,
            eth_amount=eth_amount, gas_price=_gas_price, nonce=0, wait='all',
            gas_from_amount=True, check_balance=False, count=txs_per_sender,
            **send_tx_kwargs
        )
        q.put(_tx_hashes)

    _wallets = _prepare_wallets()
    processes = []
    queues = []
    for x in range(len(_wallets['senders'])):
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_all_confirmed,
            args=(q, _wallets['senders'][x], _wallets['receivers'][x])
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

    say("All confirmed Tx Hashes:", output=False)
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
        colored("All Confirmed txs", "blue"),
        to_log=False
        )

    bench_results.append(f"all_confirmed:{_tps:.2f},{_gps}")
    _recover_funds(_wallets)


if args['confirmed']:
    _msg = "** Confirmed tests"
    if args['race']:
        _msg += " (RACE MODE)"
    say(colored(_msg, "red"), to_log=False)

    gas_price = get_gas_price(node_url)

    def _do_confirmed(q, sender, receiver):
        if args['race']:
            _tx_hashes = send_transaction(
                sender_key=sender.key.hex(), receiver_address=receiver.address,
                eth_amount=eth_amount, gas_price=gas_price, nonce=1,
                wait=False, gas_from_amount=True, check_balance=False,
                count=txs_per_sender-1, **send_tx_kwargs
            )
            _tx_hash_list = send_transaction(
                sender_key=sender.key.hex(), receiver_address=receiver.address,
                eth_amount=eth_amount, gas_price=gas_price, nonce=0,
                wait=False, gas_from_amount=True, check_balance=False, count=1,
                **send_tx_kwargs
            )
            _tx_hashes.insert(0, _tx_hash_list[0])
            # That will confirm just the last tx because of receipts=False
            confirm_transactions(node_url, _tx_hashes, receipts=False)
        else:
            _tx_hashes = send_transaction(
                sender_key=sender.key.hex(), receiver_address=receiver.address,
                eth_amount=eth_amount, gas_price=gas_price, nonce=0,
                wait='last', gas_from_amount=True, check_balance=False,
                count=txs_per_sender, **send_tx_kwargs
            )
        q.put(_tx_hashes)

    _wallets = _prepare_wallets()
    processes = []
    queues = []
    for x in range(len(_wallets['senders'])):
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_confirmed,
            args=(q, _wallets['senders'][x], _wallets['receivers'][x])
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

    say("Last confirmed Tx Hashes:", output=False)
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
        colored("Confirmed txs", "blue") + " (last one confirmed)",
        to_log=False
        )

    bench_results.append(f"confirmed:{_tps:.2f},{_gps}")
    _recover_funds(_wallets)


if args['unconfirmed']:
    say(colored("** Unconfirmed tests", "red"), to_log=False)
    gas_price = get_gas_price(node_url)

    def _do_unconfirmed(q, sender, receiver):
        _tx_hashes = send_transaction(
            sender_key=sender.key.hex(), receiver_address=receiver.address,
            eth_amount=eth_amount, gas_price=gas_price, nonce=0, wait=False,
            gas_from_amount=True, check_balance=False, count=txs_per_sender,
            **send_tx_kwargs
        )
        q.put(_tx_hashes)

    _wallets = _prepare_wallets()
    processes = []
    queues = []
    for x in range(len(_wallets['senders'])):
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_unconfirmed,
            args=(q, _wallets['senders'][x], _wallets['receivers'][x])
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
        say("Waiting for unconfirmed txs to be confirmed...")
        confirm_transactions(
            node_url, tx_hashes, timeout=600, poll_latency=0.5, receipts=False)

    _total_gas = _gas_used_for(tx_hashes)
    _gps = int(_total_gas/_total_time)

    say("Unconfirmed Tx Hashes:", output=False)
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
        colored("Unconfirmed txs", "blue"),
        to_log=False
        )

    bench_results.append(f"unconfirmed:{_tps:.2f},{_gps}")
    _recover_funds(_wallets)


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


if args['erc20create']:
    say(colored("** ERC20 create tests", "red"), to_log=False)
    erc20_abi, bytecode = \
        compile_contract(contract='erc20')
    gas = contracts['erc20']['create_gas']
    gas_price = get_gas_price(node_url)

    to_fund = txs_per_sender*float(
        w.from_wei(gas*gas_price*gas_price_factor, 'ether')
    )
    if args['debug']:
        say(
            f"To fund: {to_fund} | gas={gas}, gas_price={gas_price}, "
            f"gas_factor={gas_price_factor}, txs={txs_per_sender}"
        )
    _wallets = _prepare_wallets(amount=to_fund)
    if args['erc20txs']:
        token_receivers = _wallets['receivers']

    processes = []
    queues = []
    for x in range(len(_wallets['senders'])):
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_sc_deploy,
            args=(q, _wallets['senders'][x], bytecode, gas)
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
    for q in queues:
        while not q.empty():
            results.append(q.get())
    tx_hashes = []
    for r in results:
        tx_hashes.extend(r[1])
    _total_gas = _gas_used_for(tx_hashes)
    _gps = int(_total_gas/_total_time)

    say("ERC20 create Tx Hashes:", output=False)
    for x in range(0, len(tx_hashes), log_tx_per_line):
        say(tx_hashes[x:x+log_tx_per_line], output=False)

    if args['erc20txs']:
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
            f"{txs_per_sender} tokens for {concurrency} senders", "blue") +
        f" (total of {_tx_count} tokens): " +
        colored(f"{_total_time:.2f}s", "yellow") + " | " +
        colored(f"TPS:{_tps:.2f}", "green") + " | " +
        colored(f"Gas:{_total_gas}", "yellow") + " | " +
        colored(f"Gas/s:{_gps}", "green") + " | " +
        colored("Confirmed SC", "blue"),
        to_log=False
        )

    bench_results.append(f"erc20_create:{_tps:.2f},{_gps}")
    if not args['erc20txs']:
        _recover_funds(_wallets)
    else:
        erc20_wallets = _wallets


if args['erc20txs']:
    if not args['erc20create']:
        raise ValueError("ERC20 txs requested without ERC20 create")

    say(colored("** ERC20 transfer tests", "red"), to_log=False)

    def _do_erc20txs(q, sender_key, dst_addr, sender_nonce, contract_addrs):
        _w = Web3(Web3.HTTPProvider(node_url))
        _gas_price = get_gas_price(node_url)
        _tx_hashes = []
        _nonce = sender_nonce
        for addr in contract_addrs:
            wei_amount = w.to_wei(1, 'ether')
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
    _recover_funds(erc20_wallets)


if args['uniswap']:
    say(colored("** Uniswap tests", "red"), to_log=False)
    assert txs_per_sender % uniswap_contract_count == 0, \
        "txs_per_sender must be multiple of 3"
    _txs_per_sender = txs_per_sender//uniswap_contract_count
    gas_price = get_gas_price(node_url)
    to_fund = 0
    _bytecodes_gas = []

    for x in ('uv2_pair', 'uv2_factory', 'uv2_erc20'):
        (_, _bytecode) = compile_contract(contract=x)
        if x == 'uv2_factory':
            _bytecode += abi_encode_addr(funded_account.address)
        _gas = contracts[x]['create_gas']
        _bytecodes_gas.append((_bytecode, _gas))
        to_fund += _txs_per_sender*float(
            w.from_wei(_gas*gas_price*gas_price_factor, 'ether')
        )

    _wallets = _prepare_wallets(amount=to_fund)

    processes = []
    queues = []
    for x in range(len(_wallets['senders'])):
        _nonce = 0
        for (_b, _g) in _bytecodes_gas:
            # Using the same queue for all make it slow as they're mutexed
            q = mp.Queue()
            process = mp.Process(
                target=_do_sc_deploy,
                args=(
                    q, _wallets['senders'][x], _b, _g, _nonce, _txs_per_sender)
            )
            queues.append(q)
            processes.append(process)
            _nonce += _txs_per_sender

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
            _, _tx_hashes = q.get()
            tx_hashes.extend(_tx_hashes)
    _total_gas = \
        _gas_used_for(tx_hashes, search_for_diff=uniswap_contract_count)
    _gps = int(_total_gas/_total_time)

    say("Uniswap Tx Hashes:", output=False)
    for x in range(0, len(tx_hashes), log_tx_per_line):
        say(tx_hashes[x:x+log_tx_per_line], output=False)

    say("Time to deploy " +
        colored(
            f"{txs_per_sender} uniswap v2 sc "
            f"for {concurrency} senders", "blue"
        ) + f" (total of {_tx_count} sc create): " +
        colored(f"{_total_time:.2f}s", "yellow") + " | " +
        colored(f"TPS:{_tps:.2f}", "green") + " | " +
        colored(f"Gas:{_total_gas}", "yellow") + " | " +
        colored(f"Gas/s:{_gps}", "green") + " | " +
        colored("Uniswap SC last confirmed", "blue"),
        to_log=False
        )

    bench_results.append(f"uniswap:{_tps:.2f},{_gps}")
    _recover_funds(_wallets)


# Part1: precompileds create contracts
if args['precompileds']:
    say(colored("** precompileds create tests", "red"), to_log=False)
    _, bytecode = \
        compile_contract(contract='laia1')
    gas = contracts['laia1']['create_gas']
    call_gas = contracts['laia1']['call_gas']
    gas_price = get_gas_price(node_url)

    to_fund = txs_per_sender*float(
        w.from_wei(gas*gas_price*gas_price_factor, 'ether') +
        w.from_wei(call_gas*gas_price*gas_price_factor*4, 'ether')
    )
    _wallets = _prepare_wallets(amount=to_fund)

    processes = []
    queues = []
    for x in range(len(_wallets['senders'])):
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_sc_deploy,
            args=(q, _wallets['senders'][x], bytecode, gas)
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

    say("precompileds create Tx Hashes:", output=False)
    for x in range(0, len(tx_hashes), log_tx_per_line):
        say(tx_hashes[x:x+log_tx_per_line], output=False)

    # Just to keep same structure as other tests, its always True
    if args['precompileds']:
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
            f"{txs_per_sender} precompileds sc for "
            f"{concurrency} senders", "blue") +
        f" (total of {_tx_count} laia1 scs): " +
        colored(f"{_total_time:.2f}s", "yellow") + " | " +
        colored(f"TPS:{_tps:.2f}", "green") + " | " +
        colored(f"Gas:{_total_gas}", "yellow") + " | " +
        colored(f"Gas/s:{_gps}", "green") + " | " +
        colored("precompileds SC last confirmed", "blue"),
        to_log=False
        )

    bench_results.append(f"precompileds_create:{_tps:.2f},{_gps}")
    laia1_wallets = _wallets


# Part2: precompileds tests
if args['precompileds']:
    say(colored("** precompileds tests", "red"), to_log=False)
    assert txs_per_sender % precompiled_contract_count == 0, \
        "txs_per_sender must be multiple of 4"
    _txs_per_sender = txs_per_sender//precompiled_contract_count

    def _do_laia1(q, sender_key, sender_nonce, contract_addr):
        _gas_price = get_gas_price(node_url)
        _all_tx_hashes = []
        _nonce = sender_nonce
        call_gas = contracts['laia1']['call_gas']

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
        f" (total of {_tx_count} laia1 txs): " +
        colored(f"{_total_time:.2f}s", "yellow") + " | " +
        colored(f"TPS:{_tps:.2f}", "green") + " | " +
        colored(f"Gas:{_total_gas}", "yellow") + " | " +
        colored(f"Gas/s:{_gps}", "green") + " | " +
        colored("precompileds Tx last confirmed", "blue"),
        to_log=False
        )

    bench_results.append(f"precompileds_txs:{_tps:.2f},{_gps}")
    _recover_funds(laia1_wallets)


# Part1: Laia2 create contracts
if args['pairings']:
    say(colored("** pairings create tests", "red"), to_log=False)
    _, bytecode = \
        compile_contract(contract='laia2')
    gas = contracts['laia2']['create_gas']
    # call_gas = contracts['laia2']['call_gas']
    call_gas = 0
    gas_price = get_gas_price(node_url)

    to_fund = txs_per_sender*float(
        w.from_wei(gas*gas_price*gas_price_factor, 'ether') +
        w.from_wei(call_gas*gas_price*gas_price_factor, 'ether')
    )
    _wallets = _prepare_wallets(amount=to_fund)

    processes = []
    queues = []
    for x in range(len(_wallets['senders'])):
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_sc_deploy,
            args=(q, _wallets['senders'][x], bytecode, gas)
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

    say("pairings create Tx Hashes:", output=False)
    for x in range(0, len(tx_hashes), log_tx_per_line):
        say(tx_hashes[x:x+log_tx_per_line], output=False)

    # Just to keep same structure as other tests, its always True
    if args['pairings']:
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
            f"{txs_per_sender} pairings sc for "
            f"{concurrency} senders", "blue") +
        f" (total of {_tx_count} laia1 scs): " +
        colored(f"{_total_time:.2f}s", "yellow") + " | " +
        colored(f"TPS:{_tps:.2f}", "green") + " | " +
        colored(f"Gas:{_total_gas}", "yellow") + " | " +
        colored(f"Gas/s:{_gps}", "green") + " | " +
        colored("pairings SC last confirmed", "blue"),
        to_log=False
        )

    bench_results.append(f"pairings_create:{_tps:.2f},{_gps}")
    laia2_wallets = _wallets
    _recover_funds(laia2_wallets)


if args['complex']:
    say(colored("** complex create tests", "red"), to_log=False)
    _, bytecode = \
        compile_contract(contract='complex')
    gas = contracts['complex']['create_gas']
    gas_price = get_gas_price(node_url)

    to_fund = txs_per_sender*float(
        w.from_wei(gas*gas_price*gas_price_factor, 'ether')
    )
    _wallets = _prepare_wallets(amount=to_fund)

    processes = []
    queues = []
    for x in range(len(_wallets['senders'])):
        # Using the same queue for all make it slow as they're mutexed
        q = mp.Queue()
        process = mp.Process(
            target=_do_sc_deploy,
            args=(q, _wallets['senders'][x], bytecode, gas)
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

    say("complex create Tx Hashes:", output=False)
    for x in range(0, len(tx_hashes), log_tx_per_line):
        say(tx_hashes[x:x+log_tx_per_line], output=False)

    say("Time to create " +
        colored(
            f"{txs_per_sender} complex sc for "
            f"{concurrency} senders", "blue") +
        f" (total of {_tx_count} laia1 scs): " +
        colored(f"{_total_time:.2f}s", "yellow") + " | " +
        colored(f"TPS:{_tps:.2f}", "green") + " | " +
        colored(f"Gas:{_total_gas}", "yellow") + " | " +
        colored(f"Gas/s:{_gps}", "green") + " | " +
        colored("pairings SC last confirmed", "blue"),
        to_log=False
        )

    bench_results.append(f"complex_create:{_tps:.2f},{_gps}")
    _recover_funds(_wallets)


say(f"Results: {bench_results}", output=False)
say(colored(bench_results, "magenta"), to_log=False)
