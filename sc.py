import os
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
    'op_invalid': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'InvalidOpcodeTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_revert': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'LargeRevertTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_recursivecall': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'RecursiveCallTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_storagebomb': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'StorageBombTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_largecodecopy': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'LargeExtcodecopyTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_create2': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'Create2SpamTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_largelog': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'LargeLogTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_sload': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'SLoadSpamTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_opcodeinject': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'OpcodeInjectionTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_gaslimit': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'GasLimitTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_sstorespam': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'SstoreSpam',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_memalloc': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'MemoryAllocationTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_l12l2spam': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'L1ToL2Spam',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_txpoolspam': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'TxPoolSpam',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_masscreate2': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'MassCreate2',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_reentrancy': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'ReentrancyAttack',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_noncereuse': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'NonceReuseTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_selfdestruct': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'SelfDestructTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },




    'op_infinitestackbomb': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'InfiniteStackBomb',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_memoverflow': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'MemoryOverflow',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_eventflooder': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'EventFlooder',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_selfdestructresurrector': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'SelfDestructResurrector',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_gasrefund': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'GasRefundAbuser',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_l1l2race': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'L1L2RaceCondition',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_txloop': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'TransactionLoop',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_extcodesizetest': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'ExtcodeSizeTest',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_precompiledexploiter': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'PrecompileExploiter',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_calldataflooder': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'CalldataFlooder',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_selfdestructloop': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'SelfDestructLoop',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },
    'op_maxgasblockfiller': {
        'file': 'contracts/OptimismTest.sol',
        'contract': 'MaxGasBlockFiller',
        'compile_kwargs': {'solc_version': '0.8.5'}
    },


}


def compile_contract(contract):
    script_folder = os.path.dirname(os.path.realpath(__file__))
    contract_file = \
        os.path.join(script_folder, contracts[contract]['file'])
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
    try:
        bytecode = \
            compiled_contracts[f"{contract_file}:{contract_name}"]["bin"]
        abi = compiled_contracts[f"{contract_file}:{contract_name}"]["abi"]
    except KeyError:
        _k = contracts[contract]['file']
        bytecode = compiled_contracts[f"{_k}:{contract_name}"]["bin"]
        abi = compiled_contracts[f"{_k}:{contract_name}"]["abi"]

    return abi, bytecode
