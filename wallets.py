from time import time
from web3 import Web3
from utils import say, create_wallets
from geth import get_gas_price, get_transaction_count
from tx import confirm_transactions, send_transaction


class Wallets():
    def __init__(self, node_url, funded_key, concurrency, txs_per_sender):
        self.funded_key = funded_key
        self.funded_address = Web3().eth.account.from_key(str(funded_key))
        self.node_url = node_url
        self.txs_per_sender = txs_per_sender
        self.concurrency = concurrency

    def get(self, amount):
        funded_nonce = \
            get_transaction_count(self.node_url, self.funded_address, 'latest')
        funded_nonce_pending = \
            get_transaction_count(
                self.node_url, self.funded_address, 'pending')
        funded_gas_factor = 1

        if funded_nonce_pending != funded_nonce:
            say("WARNING: "
                f"Pending ({funded_nonce_pending}) and Latest ({funded_nonce})"
                f" nonces are different for {self.funded_address}"
                )
            # So we can replace existing txs
            funded_gas_factor = 1.5

        _wallets = create_wallets(w, self.concurrency)
        _gas_price = get_gas_price(self.node_url)

        _start = time.time()
        for _sender in _wallets['senders']:
            _tx_hashes = send_transaction(
                self.node_url, self.funded_key, _sender.address,
                amount*self.txs_per_sender, int(_gas_price*funded_gas_factor),
                nonce=funded_nonce, wait=False
            )
            if _tx_hashes:
                funded_nonce += 1

        # Confirming last one is enough (its already an array):
        _ = confirm_transactions(
            self.node_url, _tx_hashes, timeout=600, poll_latency=0.5)
        _end = time()
        _n = len(_wallets['senders'])
        say(
            f"Funded {_n} senders with {amount*self.txs_per_sender:.6f}ETH "
            f"each, using funds from {self.funded_address} in "
            f"{_end-_start:.2f} seconds | Last used nonce: {funded_nonce}"
            # f" | {_n/(_end-_start):.2f} Sequential TPS"
        )

        return _wallets
