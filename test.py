import time
from web3 import Web3
from tx import send_transaction


node_url = 'http://34.175.214.161:18123'
private_key = \
    '0xe861f24697bdc8f299060864eeec0ab1d400bca4d436ce44c9acf1b68fa79f39'
w = Web3(Web3.HTTPProvider(node_url))
account = w.eth.account.from_key(str(private_key))

nonce = w.eth.get_transaction_count(account.address, 'pending')
balance = w.eth.get_balance(account.address)
print(f"Status: sender={account.address} with nonce={nonce} and balance={balance}")

print(f"Sending SC Create with infinite loop, nonce={nonce}")
tx_hashes = send_transaction(
    ep=node_url, sender_key=account.key.hex(), gas=299999, data='0x5b3456',
    sc_create=True, wait=False, nonce=nonce
)

nonce = w.eth.get_transaction_count(account.address, 'pending')
balance = w.eth.get_balance(account.address)
print(f"Status: sender={account.address} with nonce={nonce} and balance={balance}")

print("Waiting for 5 seconds")
time.sleep(5)

nonce = w.eth.get_transaction_count(account.address, 'pending')
balance = w.eth.get_balance(account.address)
print(f"Status: sender={account.address} with nonce={nonce} and balance={balance}")
