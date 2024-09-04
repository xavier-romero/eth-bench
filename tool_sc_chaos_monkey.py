import argparse
import random
import time
from web3 import Web3
from utils import get_profile, init_log, say
from tx import send_transaction, confirm_transactions
from geth import get_transaction_count
from evm_table import random_bytecode


ap = argparse.ArgumentParser()
ap.add_argument('-p', '--profile', required=True, help="Profile to use")
ap.add_argument('-e', '--eth', required=True, help="Eth to fund each sender")
ap.add_argument(
    '-s', '--senders', required=True, help="Number of senders per round")
ap.add_argument('-r', '--rounds', required=True, help="Number of rounds")
ap.add_argument(
    '-t', '--txs', required=True, help="Number of txs per sender per round")
ap.add_argument(
    '-f', '--fundrecover', required=False, default=False, help="Recover funds")
ap.add_argument(
    '-w', '--wait', required=False, default=0, help="Pause between rounds")
ap.add_argument(
    '-d', '--maxdatalen', required=False, default=8192,
    help="Max bytes for data"
)
ap.add_argument(
    '-x', '--bytecodes_to_file', required=False, action='store_true',
    help="Save all bytecodes to file",
)
ap.add_argument(
    '-xx', '--bytecodes_from_file', required=False, action='store_true',
    help="Load bytecodes from file"
)

args = vars(ap.parse_args())

node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
    l1_funded_key = \
    get_profile(args['profile'])

w = Web3(Web3.HTTPProvider(node_url))
funded_wallet = Web3().eth.account.from_key(str(funded_key))
gas_price = w.eth.gas_price
vers = w.client_version
n_senders = int(args['senders'])
n_rounds = int(args['rounds'])
round_pause = int(args['wait'])
n_txs = int(args['txs'])
recover_funds = args['fundrecover']
max_data_len = int(args['maxdatalen'])
save_bytecodes = args['bytecodes_to_file']
load_bytecodes = args['bytecodes_from_file']
init_log(args['profile'], tool='sc_chaos_monkey')
total_txs = 0
tx_map = {i: {} for i in range(n_senders)}

if save_bytecodes:
    bytecodes_file = open('bytecodes.log', 'w')
elif load_bytecodes:
    bytecodes_file = open('bytecodes.log', 'r')
    loaded_bytecodes = bytecodes_file.readlines()
    bytecodes_file.close()
    loaded_bytecodes_index = 0


def _get_sender(
    create=True, previous_sender_addr=None, previous_sender_key=None
):
    if previous_sender_addr:
        say(f"Recovering funds from {previous_sender_addr}...")
        tx_hashes = send_transaction(
            ep=node_url, sender_key=previous_sender_key,
            receiver_address=funded_wallet.address, all_balance=True,
            gas_from_amount=True, wait='all', debug=False, raw_retries=2
        )
        say(f"Recovered funds: {tx_hashes}")

    if not create:
        return None

    # funded_nonce = \
    #     w.eth.get_transaction_count(funded_wallet.address, 'pending')
    funded_nonce = get_transaction_count(
        node_url, funded_wallet.address, 'pending')
    new_sender = Web3().eth.account.create()
    new_sender_addr = new_sender.address
    new_sender_key = new_sender.key.hex()
    send_transaction(
        ep=node_url, sender_key=funded_key, receiver_address=new_sender_addr,
        eth_amount=float(args['eth']), wait='all', nonce=funded_nonce
    )
    balance = w.eth.get_balance(new_sender_addr)

    say(
        f"Endpoint {node_url} ({vers}) | block: {w.eth.block_number} | "
        f"Master: {funded_wallet.address} | "
        f"Wallet: {new_sender_addr} ({new_sender_key}) Balance: {balance} | "
        f"GasPrice={gas_price}")

    return (new_sender_addr, new_sender_key)


def _sender_round(
        sender_addr, sender_key, n_txs, expected_nonce, round, sender_id):
    global total_txs
    global tx_map
    if load_bytecodes:
        global loaded_bytecodes_index

    sender_nonce = get_transaction_count(node_url, sender_addr, 'pending')
    sender_latest_nonce = \
        get_transaction_count(node_url, sender_addr, 'latest')
    say(
        f"Sender id: {sender_id} | "
        f"Sender addr: {sender_addr} | "
        f"Sender key: {sender_key} | "
        f"Expected nonce: {expected_nonce} | "
        f"Pending nonce: {sender_nonce} | "
        f"Latest nonce: {sender_latest_nonce}"
    )
    tx_hash_to_confirm = tx_map[sender_id].get(sender_nonce-1)
    if tx_hash_to_confirm:
        say(
            f"Confirming tx: {tx_hash_to_confirm} | "
            f"nonce: {sender_nonce-1}"
        )
        receipts = \
            confirm_transactions(
                ep=node_url, tx_hashes=[tx_hash_to_confirm], timeout=5)
        if receipts:
            blocknum = receipts[0].get('blockNumber')
            contractAddress = receipts[0].get('contractAddress')
            status = receipts[0].get('status')
            say(
                f"Receipt for {tx_hash_to_confirm}: "
                f"blocknum:{int(blocknum, base=16)} | "
                f"contractAddress:{contractAddress} | "
                f"status:{'ok' if status == '0x1' else 'fail'}"
            )
        # Just in case something has been processed in the meantime
        sender_nonce = \
            get_transaction_count(node_url, sender_addr, 'pending')
        # w.eth.get_transaction_count(sender_addr, 'pending')

    gas_price = w.eth.gas_price
    if sender_nonce < expected_nonce:
        gas_price = int(gas_price * 1.1)

    tx_hash = None
    for k in range(n_txs):
        if load_bytecodes:
            data = loaded_bytecodes[loaded_bytecodes_index].strip()
            data_len = len(data)
            loaded_bytecodes_index += 1
        else:
            data_len = random.randint(1, max_data_len)
            data = random_bytecode(data_len)
            if save_bytecodes:
                bytecodes_file.write(data + '\n')
        real_data_len = (len(data)//2) - 1
        # data = ""
        tx = {
            'nonce': sender_nonce,
            'gas': 29999999,
            'gasPrice': gas_price,
            'data': data
        }
        signed_tx = w.eth.account.sign_transaction(tx, sender_key)

        try:
            tx_hash = w.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_map[sender_id][sender_nonce] = tx_hash.hex()
        except ValueError as e:
            err_dict = e.args[0]
            say(f"Error sending tx: {err_dict}")
            if 'invalid' in err_dict.get('message'):
                say(f"Invalid: {data}", output=False)
                # We will send a replacement tx with the same nonce
                gas_price = int(gas_price * 1.1)
            elif 'insufficient funds' in err_dict.get('message'):
                say("Insufficient funds!")
                return
            elif (
                ('nonce too low' in err_dict.get('message')) or
                ('could not replace existing tx' in err_dict.get('message'))
            ):
                # sender_nonce = w.eth.get_transaction_count(
                #     sender_addr, 'pending')
                sender_nonce = get_transaction_count(
                    node_url, sender_addr, 'pending')
                say(f"Setting nonce to: {sender_nonce}")
            # to avoid nonce increment
            continue
        else:
            total_txs += 1
            say(
                f"sender={sender_addr} nonce={sender_nonce} "
                f"hash={tx_hash.hex()} data={data}", output=False
            )
            data_sample = '...' + data[-16:]
            say(
                f"ttxs:{total_txs} round:{round} tx:{k} sender:{sender_id} "
                f"nonce:{sender_nonce}: tx_hash={tx_hash.hex()} | "
                # 5 bytes as prefix to all bytecodes on func random_bytecode()
                f"data={data_sample} ({real_data_len} bytes ({data_len}))"
            )
            # Next nonce to send
            sender_nonce += 1


senders = []
say(f"Creating {n_senders} senders...")
for i in range(n_senders):
    senders.append(_get_sender())

for i in range(n_rounds):
    for j in range(n_senders):
        (sender_addr, sender_key) = senders[j]
        say(f"Round {i} | Sender {j} | {sender_addr} - {sender_key}")
        _sender_round(
            sender_addr, sender_key, n_txs, i*n_txs, round=i, sender_id=j)
    time.sleep(round_pause)

# just to recover funds:
if recover_funds:
    for i in range(n_senders):
        (sender_addr, sender_key) = senders[j]
        _get_sender(
            create=False,
            previous_sender_addr=senders[j][0],
            previous_sender_key=senders[j][1]
        )
