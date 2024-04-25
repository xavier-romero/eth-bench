pragma solidity >=0.8.10;

contract bornToHash {
    constructor () {
        for(uint256 i = 0; i < 1616; i++) {
            keccak256(new bytes(0));
        }
    }
}
