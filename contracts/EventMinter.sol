// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.18;

contract EventMinter {
    uint256 public total = 20;
    event NumberEvent(uint256 index, uint256 total);

    constructor() {
        for (uint256 i = 0; i < total; i++) {
            emit NumberEvent(i+1, total);
        }
    }
}
