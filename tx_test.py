from web3 import Web3, exceptions

ep = ("xx", 234)
ep2 = ("xx", 234)
sender_key = "xx"  # noqa
receiver_addr = "xx"

w = Web3(Web3.HTTPProvider(ep[0]))
w2 = Web3(Web3.HTTPProvider(ep2[0]))
sender = w.eth.account.from_key(str(sender_key))

pending_nonce = w.eth.get_transaction_count(sender.address, 'pending')
latest_nonce = w.eth.get_transaction_count(sender.address, 'latest')
gas_price = w.eth.gas_price
vers = w.client_version

print(
    f"Endpoint {ep[0]} ({vers}) | chaind {ep[1]} | "
    f"block: {w.eth.block_number}"
)
print(
    f"Sender {sender.address}: pending_nonce={pending_nonce} "
    f"latest_nonce={latest_nonce}, Gas_Price={gas_price}")

tx = {
    'chainId': ep[1],
    'nonce': pending_nonce,
    'to': receiver_addr,
    'value': w.to_wei(1, 'ether'),
    'gas': 21000,
    'gasPrice': gas_price,
}
print(f"Transaction={tx}")

signed_tx = w.eth.account.sign_transaction(tx, sender_key)
print(f"Signed_tx={signed_tx}")

tx_hash = w.eth.send_raw_transaction(signed_tx.rawTransaction)
print(f"tx_hash={tx_hash.hex()}")

r = None
while (not r):
    try:
        r = w.eth.wait_for_transaction_receipt(tx_hash, timeout=5)
    except exceptions.TimeExhausted:
        try:
            r2 = w2.eth.wait_for_transaction_receipt(tx_hash, timeout=1)
        except exceptions.TimeExhausted:
            print("No receipt after 5s. Retrying...")
        else:
            print(f"BUT Got confirmation from {ep2[0]}, receipt={dict(r2)}")

print(f"Got confirmation, receipt={dict(r)}")
