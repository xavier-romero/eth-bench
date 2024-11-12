from solcx import compile_files, exceptions, install_solc

# uniswapv2_contract_count = 3
# uniswapv2_contract_names = ['uv2_pair', 'uv2_factory', 'uv2_erc20']

contracts = {
    'erc20': {
        'file': 'contracts/ERC20Token.sol',
        'contract': 'ERC20Token',
        'create_gas': 1125589,
        'transfer_gas': 75000,
        'compile_kwargs': {'evm_version': 'paris', 'solc_version': '0.8.18'}
    },
    'uv2_pair': {
        'file': 'contracts/v2-core/contracts/UniswapV2Pair.sol',
        'contract': 'UniswapV2Pair',
        'create_gas': 3500000,
        'compile_kwargs': {'solc_version': '0.5.16'}
    },
    'uv2_factory': {
        'file': 'contracts/v2-core/contracts/UniswapV2Factory.sol',
        'contract': 'UniswapV2Factory',
        'create_gas': 4500000,
        'compile_kwargs': {'solc_version': '0.5.16'}
    },
    'uv2_erc20': {
        'file': 'contracts/v2-core/contracts/UniswapV2ERC20.sol',
        'contract': 'UniswapV2ERC20',
        'create_gas': 1000000,
        'compile_kwargs': {'solc_version': '0.5.16'}
    },
    'precompileds': {  # Laia1 contracts
        'file': 'contracts/laia1.sol',
        'contract': 'RandomPre',
        'create_gas':  3000000,
        'call_gas': 350000,
        'compile_kwargs': {'solc_version': '0.8.18'}
    },
    'pairings': {  # Laia2 contracts
        'file': 'contracts/laia2.sol',
        'contract': 'RandomEcPairing',
        'create_gas':  200000,
        'call_gas': 200000,
        'compile_kwargs': {'solc_version': '0.8.18'}
    },
    'keccaks': {
        'file': 'contracts/keccaks.sol',
        'contract': 'bornToHash',
        'create_gas':  620000,
        'compile_kwargs': {'solc_version': '0.8.18'}
    },
    'eventminter': {
        'file': 'contracts/EventMinter.sol',
        'contract': 'EventMinter',
        'create_gas':  175000,
        'compile_kwargs': {'solc_version': '0.8.18'}
    },
    'boundaries': {
        'file': 'contracts/Tester.sol',
        'contract': 'Boundaries',
        'create_gas':  175000,
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'premodexp': {
        'file': 'contracts/Tester.sol',
        'contract': 'PreModExp',
        'create_gas':  175000,
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
}


def compile_contract(contract):
    contract_file = contracts[contract]['file']
    contract_name = contracts[contract]['contract']
    compile_kwargs = contracts[contract].get('compile_kwargs', {})

    # Compile the contract from the file
    try:
        compiled_contracts = compile_files(
            [contract_file], output_values=["bin", "abi"], **compile_kwargs)
    except exceptions.SolcNotInstalled:
        install_solc(compile_kwargs.get('solc_version', 'latest'))
        return compile_contract(contract)

    # Get the bytecode of the contract
    bytecode = compiled_contracts[f"{contract_file}:{contract_name}"]["bin"]
    abi = compiled_contracts[f"{contract_file}:{contract_name}"]["abi"]

    return abi, bytecode
