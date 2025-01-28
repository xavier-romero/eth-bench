import json
# requirements: pip install web3
from web3 import Web3
from eth_keyfile import create_keyfile_json


keystore_password = "super_secret!"
keystore_output_file = "my_address.keystore"

# Create wallet using Web3 lib
wallet = Web3().eth.account.create()
address = wallet.address
private_key = wallet.key.hex()

# Print address and private key
print(f"New address: {address} PrivKey: {private_key}")

# Create keystore content using eth lib
ks = create_keyfile_json(
    int(private_key, 16).to_bytes(32, 'little'),
    bytes(keystore_password, 'utf-8')
)

# keystore generated into var, dump to json file
with open(keystore_output_file, "w") as f:
    json.dump(ks, f, indent=2)

print(f"Created keystore file {keystore_output_file}")
