import time
import json
import requests
from utils import say


def get_transaction_count(ep, address, mode='latest'):
    nonce_hex = geth_request(
        ep=ep,
        method='eth_getTransactionCount',
        params=[address, mode]
    )
    return int(nonce_hex, base=16)


def get_transaction_receipt(ep, tx_hash, timeout=0, poll_latency=0):
    if not tx_hash.startswith('0x'):
        tx_hash = '0x' + tx_hash
    kwargs = {
        'ep': ep,
        'method': 'eth_getTransactionReceipt',
        'params': [tx_hash],
        'none_ok': True
    }
    result = geth_request(**kwargs)
    if result or not poll_latency:
        return result

    counter = timeout/poll_latency
    while counter and not result:
        time.sleep(poll_latency)
        result = geth_request(**kwargs)
        # print(f"Kwargs={kwargs} result={result} poll_latency={poll_latency}")
        counter -= 1

    return result


def get_gas_price(ep):
    return int(geth_request(ep=ep, method='eth_gasPrice'), base=16)


def get_balance(ep, address, mode='latest'):
    balance_hex = geth_request(
        ep=ep,
        method='eth_getBalance',
        params=[address, mode]
    )
    return int(balance_hex, base=16)


def send_raw_transaction(ep, tx):
    tx_bytes = tx.hex()
    if not tx_bytes.startswith('0x'):
        tx_bytes = '0x' + tx_bytes
    return geth_request(
        ep=ep,
        method='eth_sendRawTransaction',
        params=[tx_bytes]
    )


def endpoint_request(
    method='GET', endpoint=None, path='/', url=None, params=None, body=None,
    data=None, headers=None, auth=None, max_attempts=10, trhottle_cooldown=10,
    error_handler={}, debug=False
):
    if not path.startswith('/'):
        path = f'/{path}'

    # IF URL is provided (it must be full URL) it's used disregarding
    #  whatever is the value for endpoint and path
    if url:
        kwargs = {'method': method, 'url': url}
    else:
        kwargs = {'method': method, 'url': f'{endpoint}{path}'}

    if params:
        kwargs['params'] = params
    if body:
        kwargs['data'] = json.dumps(body)
    elif data:
        kwargs['data'] = data
    if headers:
        kwargs['headers'] = headers
    if auth:
        kwargs['auth'] = auth

    if debug:
        say(f'kwargs:{kwargs}')

    for attempt in range(1, max_attempts+1):
        try:
            req = requests.request(**kwargs)
            try:
                content = req.json()
            except ValueError:
                content = req.reason
            rcode = req.status_code

            if debug:
                say(f'rcode:{rcode} content:{content}')

            if rcode in error_handler:
                function = error_handler.get(rcode)
                function()
                raise requests.exceptions.HTTPError(
                    f'Handle attempt: {rcode}: {content} for url {req.url}')

            if rcode == 429:
                time.sleep(trhottle_cooldown)
                raise requests.exceptions.HTTPError(
                    f'Throttled!! {rcode}: {content} for url {req.url}')
            if rcode >= 500:
                raise requests.exceptions.HTTPError(
                    f'{rcode} Error: {content} for url {req.url}')

            return rcode, content

        except requests.exceptions.RequestException as e:
            if attempt < max_attempts:
                say(e)
                time.sleep(attempt*attempt)
            else:
                say(e)
                raise


def geth_request(ep, method, params=[], retries=3, debug=False, none_ok=False):
    (rcode, content) = endpoint_request(
        method='POST', endpoint='Unused', url=ep,
        body={'jsonrpc':'2.0', 'method': method, 'params': params, 'id': 1},
        headers={'Content-Type': 'application/json'},
        debug=False
    )
    if rcode == 200:
        if r := content.get('result'):
            return r
        elif r_err := content.get('error'):
            raise ValueError(r_err)
        elif none_ok and content.get('result', False) is None:
            return None
        else:
            say(
                f"geth_request ep={ep} method={method} params={params} "
                f"retries={retries} answer={content}")
            return None
    else:
        say(
            f"utils.geth_request rcode=={rcode} content={content}")
        return None


def geth_request_multi(ep, requests, retries=5, map_from_id='number'):
    (rcode, content) = endpoint_request(
        method='POST', endpoint='Unused', url=ep, body=requests,
        headers={'Content-Type': 'application/json'},
    )
    if rcode == 200:
        result = []
        for c in content:
            if r := c.get('result'):
                # The id has been set to batch number when querying
                if map_from_id:
                    r[map_from_id] = c.get('id')
                result.append(r)
            elif c.get('error') and retries:
                retry_in = (10-retries)*2
                say(
                    f"RETRY for geth_request ep={ep} "
                    f"retries={retries} answer={c} sleep={retry_in}")
                time.sleep(retry_in)
                return geth_request_multi(
                    ep, requests, retries-1, map_from_id=map_from_id)
            else:
                say(
                    f"geth_request ep={ep} request={requests} "
                    f"retries={retries} answer={c}")
                return None
        return result
    else:
        say(
            f"utils.geth_request rcode=={rcode} content={content}")
        return None
