import time
import uuid
from utils import say
from requests.exceptions import SSLError, ChunkedEncodingError, HTTPError
from sc import contracts
from web3 import Web3
from geth import (
    get_transaction_receipt, get_transaction_count, get_gas_price, get_balance,
    send_raw_transaction
)


gas_price_factor = 1.15
global_w = Web3()


def wrapped_send_raw_transaction(
    ep, tx, prvkey, retries=5, retry_reason=None, debug=False
):
    if debug:
        say(f"wrapped_send: {tx}")

    signed_transaction = global_w.eth.account.sign_transaction(tx, prvkey)
    try:
        tx_hash = send_raw_transaction(
            ep=ep,
            tx=signed_transaction.raw_transaction
        )
    except (SSLError, ChunkedEncodingError, HTTPError) as e:
        if debug:
            say(f"Exception:{e}--> Retries:{retries} left (tx={tx})")
        if retries:
            sleep_time = int((1/retries)*10)
            say(">>Retrying send_raw_transaction in "
                f"{sleep_time}s ({retries} left)")
            time.sleep(sleep_time)
            return wrapped_send_raw_transaction(
                ep, tx, prvkey, retry_reason='http', retries=retries-1
            )
    except ValueError as e:
        if e.args and e.args[0] and isinstance(e.args[0], dict):
            message = e.args[0].get('message')
        else:
            message = str(e)
        if debug:
            say(f"Exception:{e} --> Retries:{retries} left (tx={tx})")
        if retries:
            responses_to_retry = (
                'replacement transaction underpriced',
                'effective gas price: gas price too low',
                'could not replace existing tx'
            )
            _do_retry = [
                elem for elem in responses_to_retry if elem in message
            ]
            if _do_retry:
                tx['gasPrice'] = int(tx['gasPrice'] * gas_price_factor)
                say(
                    f"Adjusting gasPrice to {tx['gasPrice']} "
                    "(gasprice too low)")
                return wrapped_send_raw_transaction(
                    ep, tx, prvkey, retries=retries-1, debug=debug
                )
            elif message == 'replacement transaction underpriced':
                tx['gasPrice'] = int(tx['gasPrice'] * gas_price_factor)
                say(
                    f"Adjusting gasPrice to {tx['gasPrice']} "
                    "(replacement underpriced)")
                return wrapped_send_raw_transaction(
                    ep, tx, prvkey, retries=retries-1, debug=debug
                )
            sleep_time = int((1/retries)*10)
            say(">Retrying send_raw_transaction in "
                f"{sleep_time}s ({retries} left) | {message}")
            time.sleep(sleep_time)
            return wrapped_send_raw_transaction(
                ep, tx, prvkey, retry_reason=message,
                retries=retries-1
            )
        else:
            if debug:
                say("EXCEPTION")
            raise
    else:
        if debug:
            say(f"tx_hash:{tx_hash} for:{tx}")
        return tx_hash


def send_transaction(
    ep, sender_key, receiver_address=None, eth_amount=0, gas_price=None,
    nonce=None, wait='last', gas_from_amount=False, check_balance=True,
    count=1, print_hash=False, all_balance=False, data=None, gas=21000,
    chain_id=None, debug=False, wait_timeout=180, raise_on_error=True,
    wei_amount=None, raw_retries=5, sc_create=False, sc_call=False
):
    account = global_w.eth.account.from_key(str(sender_key))
    sender_address = account.address

    if debug:
        debug_id = uuid.uuid4()
        say(
            f">{debug_id} send_transaction: sender_address={sender_address}, "
            f"eth_amount={eth_amount}, receiver_address={receiver_address}, "
            f"gas_price={gas_price}, nonce={nonce}, wait={wait}, "
            f"gas_from_amount={gas_from_amount}, "
            f"check_balance={check_balance}, count={count}"
        )

    tx_hashes = []

    if nonce is None:
        nonce = get_transaction_count(
            ep=ep, address=sender_address, mode='pending')

    if gas_price is None:
        gas_price = get_gas_price(ep)
    if all_balance:
        amount = get_balance(ep=ep, address=sender_address)
    else:
        amount = wei_amount
        if not amount:
            amount = global_w.to_wei(eth_amount, 'ether')

    funds_required = amount * count

    if gas_from_amount:
        original_amount = amount
        amount = amount - (gas * gas_price)
    else:
        funds_required += gas * gas_price

    if amount < 0:
        if not all_balance:
            say(
                f"ERROR: amount is negative. original_amount:"
                f"{original_amount}, amount:{amount}, gas:{gas} "
                f"gas_price:{gas_price} gas*gas_price:{gas*gas_price}"
            )
        return tx_hashes

    elif (
        (not sc_create) and (not sc_call) and (amount == 0) and
        (receiver_address is not None)
    ):
        say("WARN: amount for tx is ZERO, aborting")
        if raise_on_error:
            raise ValueError("amount for tx is ZERO")
        return tx_hashes

    if check_balance:
        balance = get_balance(ep=ep, address=sender_address)
        if balance < funds_required:
            say(
                f"ERROR: balance is less than funds_required: "
                f"{balance} < {funds_required}"
            )
            if raise_on_error:
                raise AssertionError("balance is less than amount * count")
            return tx_hashes

    for i in range(count):
        transaction = {
            'to': receiver_address and
            Web3.to_checksum_address(receiver_address),
            'value': amount,
            'gas': gas,
            'gasPrice': gas_price,
            'nonce': nonce + i,
        }

        if chain_id:
            transaction['chainId'] = chain_id

        if data:
            transaction['data'] = data

        tx_hash = ''
        if debug:
            say(
                f">>{debug_id} sender={sender_address}, "
                f"transaction={transaction}"
            )
        try:
            tx_hash = wrapped_send_raw_transaction(
                ep, transaction, sender_key, debug=debug, retries=raw_retries
            )
        except ValueError as e:
            say(
                f"Error sending {amount} from {sender_address} to "
                f"{receiver_address} (nonce: {nonce+i} txhash: "
                f"{tx_hash}): {e}"
            )
        except Exception:
            raise
        else:
            tx_hashes.append(tx_hash)
            if print_hash:
                say(f"(print_hash) tx_hash: {tx_hash}")

    if wait and tx_hashes:
        if wait == 'all':
            for tx_hash in tx_hashes:
                if debug:
                    say(f"waiting for each, txhash={tx_hash}")
                get_transaction_receipt(
                    ep=ep,
                    tx_hash=tx_hash,
                    timeout=wait_timeout, poll_latency=0.1
                )
        elif wait == 'last':
            if debug:
                say(f"waiting for last, txhash={tx_hashes[-1]}")
            get_transaction_receipt(
                ep=ep,
                tx_hash=tx_hashes[-1],
                timeout=wait_timeout, poll_latency=0.1
            )

        else:
            raise ValueError(f"Invalid wait value: {wait}")

    return tx_hashes


def confirm_transactions(
    ep, tx_hashes, timeout=180, poll_latency=0.1, receipts=True
):
    if receipts is False:
        _receipt = get_transaction_receipt(
            ep=ep,
            tx_hash=tx_hashes[-1],
            timeout=timeout,
            poll_latency=poll_latency
        )
        if not _receipt:
            say(f"ERROR: no receipt for tx_hash={tx_hashes[-1]}")

        return _receipt

    tx_and_receipts = []
    for tx_hash in tx_hashes:
        tx_and_receipts.append(
            (
                tx_hash,
                get_transaction_receipt(
                    ep=ep,
                    tx_hash=tx_hash,
                    timeout=timeout,
                    poll_latency=poll_latency
                )
            )
        )

    receipts = []
    for (_tx_hash, _receipt) in tx_and_receipts:
        if not _receipt:
            say(f"ERROR: no receipt for tx_hash={_tx_hash}")
            continue
        try:
            _receipt['gasUsed'] = int(_receipt['gasUsed'], base=16)
        except TypeError:
            say(f"ERROR: unknown gasUsed on receipt={_receipt}")
        else:
            receipts.append(_receipt)

    return receipts


def token_transfer(
    ep, w, token_contract, token_abi, src_prvkey, dst_addr, wei_amount,
    gas_price, nonce=0, wait=True, debug=False
):
    token_transfer_gas = contracts['erc20']['transfer_gas']
    c = w.eth.contract(
        address=Web3.to_checksum_address(token_contract),
        abi=token_abi
    )

    tx = c.functions.transfer(dst_addr, wei_amount).build_transaction({
        'nonce': nonce,
        'gas': token_transfer_gas,
        'gasPrice': gas_price,
        # 'chainId': l2_chainid,
    })
    if debug:
        say(f"tx={tx}")

    tx_hash = wrapped_send_raw_transaction(ep, tx, src_prvkey)
    if debug:
        say(f"tx_hash={tx_hash}")

    if wait:
        if debug:
            say(f"waiting for tx_hash={tx_hash}")
        _ = w.eth.wait_for_transaction_receipt(
            tx_hash, timeout=120, poll_latency=0.2
        )
    return tx_hash


def sc_function_call(
    ep, w, caller_privkey, contract_addr, contract_abi, contract_function,
    contract_params, gas_price, gas, nonce=0, result_function=None
):
    c = w.eth.contract(
        address=Web3.to_checksum_address(contract_addr),
        abi=contract_abi
    )

    tx = getattr(c.functions, contract_function)(*contract_params) \
        .build_transaction(
            {
                'nonce': nonce,
                'gas': gas,
                'gasPrice': gas_price,
            }
        )
    _tx_hash = wrapped_send_raw_transaction(ep, tx, caller_privkey)
    _result = None
    if result_function:
        # If we dont wait for confirm, we may not get the right output result
        confirm_transactions(ep, [_tx_hash], timeout=120, poll_latency=0.1)
        _result = getattr(c.functions, result_function)().call()

    return (_tx_hash, _result)
