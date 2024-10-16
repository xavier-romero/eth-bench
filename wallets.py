from time import time
from web3 import Web3
from utils import say, log_tx_per_line
from geth import get_gas_price, get_transaction_count
from tx import confirm_transactions, send_transaction, gas_price_factor
from sc import contracts


class Wallets():
    def __init__(
        self, node_url, funded_key, args, concurrency, txs_per_sender,
        eth_amount, nonce
    ):
        self.node_url = node_url
        self.funded_account = Web3().eth.account.from_key(funded_key)
        self.eth_amount = eth_amount
        self.txs_per_sender = txs_per_sender
        self.concurrency = concurrency
        self.master = Web3().eth.account.create()
        self.args = args

        total_amount = 0
        for a in args:
            if args[a]:
                _test_amount = self.estimate_funds_for(test=a)
                if _test_amount:
                    total_amount += (
                        _test_amount +
                        # Adding the gas to transfer again to the wallet
                        float(Web3().from_wei(
                            21000*get_gas_price(ep=self.node_url), 'ether'
                        ))
                    )
        total_amount = total_amount*gas_price_factor

        say(
            f"Estimated total funds needed: {total_amount:.6f}ETH | "
            f"Current gas price: {get_gas_price(self.node_url)}"
        )

        if not args.get('estimate_only', False):
            say(
                f"Funding Master wallet {self.master.address} with "
                f"{total_amount:.6f}ETH"
            )
            _tx_hashes = send_transaction(
                ep=self.node_url, debug=args['debug'], sender_key=funded_key,
                receiver_address=self.master.address, eth_amount=total_amount,
                wait='all', nonce=nonce
            )
            say(f"Funding Master tx hash: {_tx_hashes[0]}", output=True)

    def estimate_funds_for(self, test):
        if test in ('allconfirmed', 'confirmed', 'unconfirmed'):
            return self.eth_amount*self.txs_per_sender*self.concurrency

        # if test == 'uniswap':
        #     gas_price = get_gas_price(self.node_url)
        #     _txs_per_sender = self.txs_per_sender//uniswapv2_contract_count
        #     t = 0
        #     for x in uniswapv2_contract_names:
        #         _gas = contracts[x]['create_gas']
        #         t += self.concurrency*_txs_per_sender*float(
        #             Web3().from_wei(_gas*gas_price*gas_price_factor, 'ether')
        #         )
        #     return t

        if test in (
            'erc20', 'precompileds', 'pairings', 'keccaks', 'eventminter',
            'uv2_pair', 'uv2_factory', 'uv2_erc20'
        ):
            gas_price = get_gas_price(self.node_url)
            gas = contracts[test]['create_gas']
            gas += contracts[test].get('call_gas', 0)

            return self.concurrency*self.txs_per_sender*float(
                Web3().from_wei(gas*gas_price*gas_price_factor, 'ether')
            )

        return 0

    def create_wallets(self, n):
        return {
            'senders': [Web3().eth.account.create() for _ in range(n)],
            'receivers': [Web3().eth.account.create() for _ in range(n)]
        }

    def get_wallets(self, test):
        amount = self.estimate_funds_for(test)
        master_nonce = \
            get_transaction_count(self.node_url, self.master.address, 'latest')
        master_nonce_pending = \
            get_transaction_count(
                self.node_url, self.master.address, 'pending')
        master_gas_factor = 1

        if master_nonce_pending != master_nonce:
            say("WARNING: "
                f"Pending ({master_nonce_pending}) and Latest ({master_nonce})"
                f" nonces are different for {self.master.address}"
                )
            # So we can replace existing txs
            master_gas_factor = 1.5

        _wallets = self.create_wallets(self.concurrency)
        _gas_price = get_gas_price(self.node_url)

        amoun_per_sender = amount/len(_wallets['senders'])
        _start = time()
        for _sender in _wallets['senders']:
            _tx_hashes = send_transaction(
                self.node_url, self.master.key.hex(), _sender.address,
                amoun_per_sender, int(_gas_price*master_gas_factor),
                nonce=master_nonce, wait=False, check_balance=False
            )
            if _tx_hashes:
                master_nonce += 1

        # Confirming last one is enough (its already an array):
        _ = confirm_transactions(
            self.node_url, _tx_hashes, timeout=600, poll_latency=0.5)
        _end = time()
        _n = len(_wallets['senders'])
        say(
            f"Funded {_n} senders with {amoun_per_sender:.6f}ETH "
            f"each, using funds from {self.master.address} in "
            f"{_end-_start:.2f} seconds | Last used nonce: {master_nonce}"
            # f" | {_n/(_end-_start):.2f} Sequential TPS"
        )

        return _wallets

    def recover_funds(self, wallets):
        if not self.args['recover']:
            return

        _priv_keys_hex = [x.key.hex() for x in wallets['senders']]
        _priv_keys_hex += [x.key.hex() for x in wallets['receivers']]

        _start = time()
        _all_tx_hashes = []
        if self.args['debug']:
            say("Recovering funds from senders/receivers back to main account")
        for _priv_key_hex in _priv_keys_hex:
            _tx_hashes = send_transaction(
                ep=self.node_url, debug=self.args['debug'],
                sender_key=_priv_key_hex,
                receiver_address=self.funded_account.address,
                all_balance=True, wait=False, check_balance=True,
                raise_on_error=False, gas_from_amount=True
            )
            _all_tx_hashes.extend(_tx_hashes)
        if _all_tx_hashes:
            _ = confirm_transactions(
                self.node_url, _all_tx_hashes[-1:], timeout=600,
                poll_latency=0.5)
        _end = time()

        _n = len(_tx_hashes)
        if _tx_hashes:
            say("Recover funds Tx Hashes:", output=False)
            for x in range(0, len(_tx_hashes), log_tx_per_line):
                say(_tx_hashes[x:x+log_tx_per_line], output=False)

        say(f"Time to recover funds from {_n} senders/receivers back to "
            f"main account {self.funded_account.address}: "
            f"{_end-_start:.2f} seconds | "
            f"Avg speed: {_n/(_end-_start):.2f} TPS | "
            f"Confirmed txs, +nonce check, +balance check, +gas price check")

    def close(self):
        say(f"Recovering funds from master wallet {self.master.address}"
            f" back to {self.funded_account.address}")
        _tx_hashes = send_transaction(
            ep=self.node_url, debug=self.args['debug'],
            sender_key=self.master.key.hex(),
            receiver_address=self.funded_account.address,
            all_balance=True, wait='all', raise_on_error=False,
            gas_from_amount=True
        )
        say(f"Master recover funds Tx Hash: {_tx_hashes}", output=False)
