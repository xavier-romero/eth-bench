// SPDX-License-Identifier: MIT
pragma solidity 0.8.5;
// 0.8.5 uses the Berlin EVM by default

contract Boundaries {
    event OpcodeTestResult(bytes1 opcode, uint256 gasUsed);
    event OffsetUsed(bytes32 offset);

    // signature 0xa301867d TestMemoryOffset(bytes1,uint256)
    function TestMemoryOffset(bytes1 opcode, uint256 offset) external {

        uint256 gasStart = gasleft();
        uint256 gasEnd;
        bytes32 b_offset = bytes32(offset);

        emit OffsetUsed(b_offset);

        if (opcode == 0x20) {
            // 20 	SHA3 offset size
            bytes memory x;
            assembly { x := keccak256(b_offset, 0x01) }
            gasEnd = gasleft();
        } else if (opcode == 0x37) {
            // 37 	CALLDATACOPY destOffset(mem) dataOffset(calldata) size
            assembly { calldatacopy(b_offset, 0x00, 0x01) }
            gasEnd = gasleft();
        } else if (opcode == 0x39) {
            // 39 	CODECOPY destOffset(mem) codeOffset(code) size
            assembly { codecopy(b_offset, 0x00, 0x01) }
            gasEnd = gasleft();
        } else if (opcode == 0x3C) {
            // 3C 	EXTCODECOPY address destOffset(mem) codeOffset(code) size
            address a_contract = address(0x00);
            assembly { extcodecopy(a_contract, b_offset, 0x00, 0x01) }
            gasEnd = gasleft();
        } else if (opcode == 0x3E) {
            // 3E 	RETURNDATACOPY destOffset(memory) offset(return data) size
            assembly { returndatacopy(b_offset, 0x00, 0x01) }
            gasEnd = gasleft();
        } else if (opcode == 0x51) {
            // 51 	MLOAD offset
            bytes memory x;
            assembly { x := mload(b_offset) }
            gasEnd = gasleft();
        } else if (opcode == 0x52) {
            // 52 	MSTORE offset value
            assembly { mstore(b_offset, 0x00) }
            gasEnd = gasleft();
        } else if (opcode == 0x53) {
            // 53 	MSTORE8 offset value
            assembly { mstore8(b_offset, 0x00) }
            gasEnd = gasleft();
        } else if (opcode == 0x5E) {
            // 5E 	MCOPY destOffset(memory) srcOffset(memory) size
            revert("MCOPY is not supported");
            // Note: Solidity introduces MCOPY for the logic of the contract if compiling
            //  with evm=Cancun, so I need to compile with evm=Berlin, so I can't use
            //  the mcopy hee
            // assembly { mcopy(offset, 0x00, 0x01) }
            // gasEnd = gasleft();
            // opcodeName = "mcopy";
        } else if (opcode == 0xA0) {
            // A0 	LOG0 offset size
            assembly { log0(b_offset, 0x01) }
            gasEnd = gasleft();
        } else if (opcode == 0xA1) {
            // A1 	LOG1 offset size topic
            assembly { log1(b_offset, 0x01, 0x00) }
            gasEnd = gasleft();
        } else if (opcode == 0xA2) {
            // A2 	LOG2 offset size topic topic
            assembly { log2(b_offset, 0x01, 0x00, 0x00) }
            gasEnd = gasleft();
        } else if (opcode == 0xA3) {
            // A3 	LOG4 offset size topic
            assembly { log3(b_offset, 0x01, 0x00, 0x00, 0x00) }
            gasEnd = gasleft();
        } else if (opcode == 0xA4) {
            // A4 	LOG4 offset size topic
            assembly { log4(b_offset, 0x01, 0x00, 0x00, 0x00, 0x00) }
            gasEnd = gasleft();
        } else if (opcode == 0xF0) {
            // F0 	CREATE value offset size
            address a_contract;
            assembly { a_contract := create(0x00, b_offset, 0x01) }
            gasEnd = gasleft();
        } else if (opcode == 0xF1) {
            // F1 	CALL gas address value offset size retOffset retSize
            address a_contract = address(0x00);
            assembly { a_contract := call(0x00, a_contract, 0x00, b_offset, 0x01, 0x00, 0x00) }
            gasEnd = gasleft();
        } else if (opcode == 0xF2) {
            // F2 	CALLCODE gas address value offset size retOffset retSize
            address a_contract = address(0x00);
            assembly { a_contract := callcode(0x00, a_contract, 0x00, b_offset, 0x01, 0x00, 0x00) }
            gasEnd = gasleft();
        } else if (opcode == 0xF3) {
            // F3 	RETURN offset size
            emit OpcodeTestResult(opcode, 0); // can't emit after return
            assembly { return(offset, 0x01) }
        } else if (opcode == 0xF4) {
            // F4 	DELEGATECALL gas address offset size retOffset retSize
            address a_contract = address(0x00);
            assembly { a_contract := delegatecall(0x00, a_contract, b_offset, 0x01, 0x00, 0x00) }
            gasEnd = gasleft();
        } else if (opcode == 0xF5) {
            // F5 	CREATE2 value salt offset size <- (WRONG)
            // assembly { a_contract := create2(0x00, 0x00, b_offset, 0x01) } <- (WRONG)
            // F5 	CREATE2 value offset size salt
            address a_contract;
            assembly { a_contract := create2(0x00, b_offset, 0x01, 0x00) }
            gasEnd = gasleft();
        } else if (opcode == 0xFA) {
            // FA 	STATICCALL gas address offset size retOffset retSize
            address a_contract = address(0x00);
            assembly { a_contract := staticcall(0x00, a_contract, b_offset, 0x01, 0x00, 0x00) }
            gasEnd = gasleft();
        } else if (opcode == 0xFD) {
            // FD 	REVERT offset size
            emit OpcodeTestResult(opcode, 0); // can't emit after revert
            assembly { revert(offset, 0x01) }
        } else {
            revert("Invalid opcode");
        }

        emit OpcodeTestResult(opcode, gasStart-gasEnd);
    }
}

contract PreModExp {
    event Log(uint success, bytes32 result);

    function modexp_test(bytes32[] memory base, bytes32[] memory exponent, bytes32[] memory modulus) public {
        bytes32 result = bytes32(0);
        uint success = 0;

        uint256 baseSize = base.length;
        uint256 exponentSize = exponent.length;
        uint256 modulusSize = modulus.length;
        uint256 total_size = 32*(baseSize + exponentSize + modulusSize) + 96; // 96 == 3 size args

        assembly {
            // free memory pointer
            let memPtr := mload(0x40)
            let live_memPtr := memPtr

            // length of base
            mstore(live_memPtr, mul(baseSize, 32))
            live_memPtr := add(live_memPtr, 0x20)
            // length of exponent
            mstore(live_memPtr, mul(exponentSize, 32))
            live_memPtr := add(live_memPtr, 0x20)
            // length of modulus
            mstore(live_memPtr, mul(modulusSize, 32))
            live_memPtr := add(live_memPtr, 0x20)

            // assign base
            for {let i:= 0} lt(i, baseSize) { i:= add(i, 1) } {
                let offset := mul(add(i, 1), 32)
                mstore(live_memPtr, mload(add(base, offset)))
                live_memPtr := add(live_memPtr, 0x20)
            }

            // assign exponent
            for {let i:= 0} lt(i, exponentSize) { i:= add(i, 1) } {
                let offset := mul(add(i, 1), 32)
                mstore(live_memPtr, mload(add(exponent, offset)))
                live_memPtr := add(live_memPtr, 0x20)
            }

            // assign modulus
            for {let i:= 0} lt(i, modulusSize) { i:= add(i, 1) } {
                let offset := mul(add(i, 1), 32)
                mstore(live_memPtr, mload(add(modulus, offset)))
                live_memPtr := add(live_memPtr, 0x20)
            }

            // call the precompiled contract BigModExp (0x05)
            // gas, address=0x5, value=0, argsOffset=memptr, argsSize=192/0xc0, retOffset=memptr, retSize=32
            success := call(gas(), 0x05, 0x0, memPtr, 0xc0, memPtr, total_size)
            switch success
            case 0 { // reverted
            } default { // success
                result := mload(memPtr)
            }
            sstore(0x1, result)  // set result
            sstore(0x3, success) // set success
        }
        emit Log(success, result);
    }
}