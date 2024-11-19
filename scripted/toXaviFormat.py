import sys
import json
import os
from web3 import Web3

# input_file = sys.argv[1]
# output_file = sys.argv[2]
input_folder = sys.argv[1]
output_folder = sys.argv[2]

max_test_balance_per_account = 5
master_account_name = "master"
default_chain_id = 1000

for intput_file in os.listdir(input_folder):
    input_file = os.path.join(input_folder, intput_file)
    output_file = os.path.join(output_folder, intput_file)
    if not input_file.endswith(".json"):
        continue
    print(f"Processing {input_file} to {output_file}")

    accounts = {
        master_account_name: {"name": "master", "eth_balance": 2}
    }
    tests = []

    with open(input_file, 'r') as f:
        test_vectors = json.load(f)

        # when diff contracts with same addr, we need to remap
        address_map = {}

        # Loop over the test vectors
        for test_vector in test_vectors:
            test_id = test_vector.get('id', None)
            test_description = test_vector.get('description', None)
            assert test_id is not None, "Test vector must have an id"
            print(f"Test vector {test_id}: {test_description}")

            # Loop over the genesis elements to get addresses to create
            for genesis_element in test_vector.get('genesis', []):
                _addr = genesis_element.get('address', None)
                _wei_balance = int(genesis_element.get('balance', 0))
                _eth_balance = int(Web3().from_wei(_wei_balance, 'ether'))
                _code = genesis_element.get('bytecode', None)
                if _addr:
                    if _addr in accounts:
                        _existing_code = accounts[_addr].get('code', None)
                        if _code == _existing_code:
                            _new_balance = \
                                accounts[_addr].get('eth_balance', 0) \
                                + _eth_balance
                            if _new_balance:
                                accounts[_addr]['eth_balance'] = _new_balance
                        else:
                            _acct_address = \
                                Web3.to_checksum_address(
                                    Web3().eth.account.create().address)
                            accounts[_acct_address] = {
                                'name': _acct_address,
                                'eth_balance': _eth_balance,
                                'code': _code,
                            }
                            address_map[_addr] = _acct_address
                    else:
                        accounts[_addr] = {
                            'name': _addr,
                            'eth_balance': _eth_balance,
                            'code': _code,
                        }
                else:
                    print("Genesis element without address")
                    sys.exit(1)

            i = 0
            # Loop over the transaction elements to create the tests
            for transaction_element in test_vector.get('txs', []):
                _tx_id = f"{test_id}-{i}"
                i += 1
                _from = transaction_element.get('from', None)
                _from = address_map.get(_from, _from)
                _to = transaction_element.get('to', None)
                _to = address_map.get(_to, _to)
                _value = int(transaction_element.get('value', 0))
                _data = transaction_element.get('data', None)
                _gas = int(transaction_element.get('gasLimit', 29999999))
                _chain_id = transaction_element.get('chainId', None)
                if not _from:
                    continue

                _test = {
                    "enabled": True,
                    "type": "transaction",
                    "id": _tx_id,
                    "description":
                        f"{test_description} | "
                        f"Tx {_tx_id} from file {input_file}",
                    "transaction": {
                        "from": _from,
                        "gas": _gas,
                        "count": 1,
                    }
                }
                if _to:
                    _test["transaction"]["to"] = _to
                if _value:
                    _test["transaction"]["wei_amount"] = _value
                if _data:
                    _test["transaction"]["data"] = _data
                if _chain_id and _chain_id != default_chain_id:
                    _test["transaction"]["chain_id"] = _chain_id

                tests.append(_test)

            # Loop over the expectedNewLeafs elements to check storage
            expected_new_leafs = test_vector.get('expectedNewLeafs', {})
            for _addr, _info in expected_new_leafs.items():
                if _addr == '0x000000000000000000000000000000005ca1ab1e':
                    # SYSTEMA_ADDR VARS WONT MATCH
                    continue
                _addr = address_map.get(_addr, _addr)
                if _info.get('storage', {}):
                    _test_check = {
                        "enabled": True,
                        "type": "check_storage",
                        "id": f"{test_id}-check-{_addr}",
                        "description":
                            f"{test_description} | Check storage for {_addr}",
                        "check": {
                            "account": _addr,
                            "storage": _info['storage']
                        }
                    }
                    tests.append(_test_check)

    for _addr, _info in accounts.items():
        _eth_balance = _info.get('eth_balance', 0)
        if _eth_balance > max_test_balance_per_account:
            _info['eth_balance'] = max_test_balance_per_account

    with open(output_file, 'w') as f:
        content = {
            "accounts": list(accounts.values()),
            "tests": tests
        }
        json.dump(content, f, indent=4)
