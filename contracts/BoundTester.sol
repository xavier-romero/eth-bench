// SPDX-License-Identifier: MIT
pragma solidity ^0.8.18;

contract BoundTester {
    event OpcodeTestResult(string opcode, bytes offset, uint256 gasUsed);

    function execute(bytes1 opcode, bytes memory offset) external {

        uint256 gasStart = gasleft();
        uint256 gasEnd;
        string memory opcodeName;

        if (opcode == 0x20) {
            // 20 	SHA3 offset size
            bytes memory x;
            assembly { x := keccak256(offset, 0x01) }
            gasEnd = gasleft();
            opcodeName = "keccak256";
        } else if (opcode == 0x37) {
            // 37 	CALLDATACOPY destOffset(mem) dataOffset(calldata) size
            assembly { calldatacopy(offset, 0x00, 0x01) }
            gasEnd = gasleft();
            opcodeName = "calldatacopy";
        } else if (opcode == 0x39) {
            // 39 	CODECOPY destOffset(mem) codeOffset(code) size
            assembly { codecopy(offset, 0x00, 0x01) }
            gasEnd = gasleft();
            opcodeName = "codecopy";
        } else if (opcode == 0x3C) {
            // 3C 	EXTCODECOPY address destOffset(mem) codeOffset(code) size
            address a_contract = address(0x00);
            assembly { extcodecopy(a_contract, offset, 0x00, 0x01) }
            gasEnd = gasleft();
            opcodeName = "extcodecopy";
        } else if (opcode == 0x3E) {
            // 3E 	RETURNDATACOPY destOffset(memory) offset(return data) size
            assembly { returndatacopy(offset, 0x00, 0x01) }
            gasEnd = gasleft();
            opcodeName = "returndatacopy";
        } else if (opcode == 0x51) {
            // 51 	MLOAD offset
            bytes memory x;
            assembly { x := mload(offset) }
            gasEnd = gasleft();
            opcodeName = "mload";
        } else if (opcode == 0x52) {
            // 52 	MSTORE offset value
            assembly { mstore(offset, 0x00) }
            gasEnd = gasleft();
            opcodeName = "mstore";
        } else if (opcode == 0x53) {
            // 53 	MSTORE8 offset value
            assembly { mstore8(offset, 0x00) }
            gasEnd = gasleft();
            opcodeName = "mstore8";
        } else {
            revert("Invalid opcode");
        }

        emit OpcodeTestResult(opcodeName, offset, gasStart-gasEnd);
    }
}


// 5E 	MCOPY
// A0 	LOG0
// A1 	LOG1
// A2 	LOG2
// A3 	LOG3
// A4 	LOG4
// F0 	CREATE
// F1 	CALL
// F2 	CALLCODE
// F3 	RETURN
// F4 	DELEGATECALL
// FA 	STATICCALL
// FD 	REVERT