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


def init_log(profile_name, tool='bench'):
    global log_file

    log_file = f"{tool}_{profile_name}.log"
    logging.basicConfig(
        filename=log_file, format='%(asctime)s %(levelname)s %(message)s',
        filemode='a')


def get_log_filename():
    global log_file
    return log_file


def say(msg, to_log=True, output=True, end=None, flush=None):
    if to_log:
        logger.info(msg)
    if output:
        kwargs = {}
        if end:
            kwargs['end'] = end
        if flush:
            kwargs['flush'] = flush
        # Forced flush:
        kwargs['flush'] = True
        print(msg, **kwargs)


def get_profile(profile_name):
    profiles = {}

    for filename in [
        'profiles.json', 'private_profiles.json', 'tmp_profiles.json'
    ]:
        try:
            with open(filename) as f:
                profiles |= json.load(f).get('profiles', {})
        except FileNotFoundError:
            pass

    if not profiles:
        raise Exception("No profiles found")

    node_url = profiles[profile_name]['node_url']
    chain_id = profiles[profile_name].get('chain_id', None)
    bridge_ep = profiles[profile_name].get('bridge_ep', None)
    bridge_addr = profiles[profile_name].get('bridge_addr', None)
    l1_ep = profiles[profile_name].get('l1_ep', None)
    l1_funded_key = profiles[profile_name].get('l1_funded_key', None)
    rollup_id = int(profiles[profile_name].get('rollup_id', 1))
    chain_id = int(chain_id) if chain_id else None

    say(f"Using profile: {profile_name} | RPC: {node_url}")

    k_from_env = profiles[profile_name].get('key_from_env', None)
    if k_from_env:
        funded_key = os.environ.get(k_from_env)
        if not funded_key:
            raise Exception(f"Environment variable {k_from_env} not set")
        return node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
            l1_funded_key, rollup_id

    funded_key = profiles[profile_name].get('funded_key', None)
    if funded_key:
        # return node_url, chain_id, funded_key
        return node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
            l1_funded_key, rollup_id

    # File with the private key
    key_file = profiles[profile_name].get('key_file')
    if not key_file:
        raise Exception("Invalid profile: No way provided to get the prv key")

    with open(key_file, 'r') as file:
        funded_key = file.read().strip()

    if not node_url or not funded_key:
        raise Exception("Invalid profile")

    return node_url, chain_id, funded_key, bridge_ep, bridge_addr, l1_ep, \
        l1_funded_key, rollup_id


def abi_encode_addr(address):
    return address.lower().replace('0x', '').rjust(64, '0')
