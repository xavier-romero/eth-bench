import os
import json
import logging

# log_file = "bench.log"
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# logging.basicConfig(
#     filename=log_file, format='%(asctime)s %(levelname)s %(message)s',
#     filemode='a')
log_tx_per_line = 10


def init_log(profile_name):
    global log_file

    log_file = f"bench_{profile_name}.log"
    logging.basicConfig(
        filename=log_file, format='%(asctime)s %(levelname)s %(message)s',
        filemode='a')


def get_log_filename():
    global log_file
    return log_file


def say(msg, to_log=True, output=True):
    if to_log:
        logger.info(msg)
    if output:
        print(msg)


def create_wallets(w, n):
    return {
        'senders': [w.eth.account.create() for _ in range(n)],
        'receivers': [w.eth.account.create() for _ in range(n)]
    }


def get_profile(profile_name):
    f = open('profiles.json')
    profiles = json.load(f).get('profiles')
    f.close()
    try:
        f = open('private_profiles.json')
    except FileNotFoundError:
        pass
    else:
        profiles |= json.load(f).get('profiles')
        f.close()

    node_url = profiles[profile_name]['node_url']

    k_from_env = profiles[profile_name].get('key_from_env', None)
    if k_from_env:
        funded_key = os.environ.get(k_from_env)
        if not funded_key:
            raise Exception(f"Environment variable {k_from_env} not set")
        return node_url, funded_key

    funded_key = profiles[profile_name].get('funded_key', None)
    if funded_key:
        return node_url, funded_key

    # File with the private key
    key_file = profiles[profile_name].get('key_file')
    if not key_file:
        raise Exception("Invalid profile: No way provided to get the prv key")

    with open(key_file, 'r') as file:
        funded_key = file.read().strip()

    if not node_url or not funded_key:
        raise Exception("Invalid profile")

    return node_url, funded_key


def abi_encode_addr(address):
    return address.lower().replace('0x', '').rjust(64, '0')
