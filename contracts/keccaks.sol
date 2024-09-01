// SPDX-License-Identifier: MIT
pragma solidity >=0.8.10;

// 1616 for legacy, 226 for erigon -> 1198 -> 246
contract bornToHash {
    constructor () {
        for(uint256 i = 0; i < 246; i++) {
            keccak256(new bytes(0));
        }
    }
}
