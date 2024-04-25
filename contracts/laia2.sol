// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.9;

// edge cases tests all to 0's

contract RandomEcPairing {
    bytes32 public output;
    function ecPairings(
        uint256 x1num,
        uint256 y1num,
        uint256 x2num,
        uint256 y2num,
        uint256 x3num,
        uint256 y3num
    ) external {
        bytes32 x1 = bytes32(x1num);
        bytes32 y1 = bytes32(y1num);
        bytes32 x2 = bytes32(x2num);
        bytes32 y2 = bytes32(y2num);
        bytes32 x3 = bytes32(x3num);
        bytes32 y3 = bytes32(y3num);
        bytes32[1] memory output2;
        assembly {
            let pointer := 0x40
            mstore(pointer, x1)
            mstore(add(pointer, 0x20), y1)
            mstore(add(pointer, 0x40), x2)
            mstore(add(pointer, 0x60), y2)
            mstore(add(pointer, 0x80), x3)
            mstore(add(pointer, 0xa0), y3)
            let resultCall := call(gas(), 0x08, 0, pointer, 192, output2, 0x20)
        }
        output = output2[0];
    }
}
