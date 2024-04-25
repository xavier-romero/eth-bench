// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.9;

// edge cases tests all to 0's

contract RandomPre {
    bytes32 public res0;
    bytes32 public res1;

    fallback() external payable {
        uint select = msg.value % 4;
        if (select == 1) {
            // 1 wei ecAdd
            ecAdd();
        } else if (select == 2) {
            // 2 weis ecMul
            ecMul();
        } else if (select == 3) {
            // 4 weis SHA256
            preSha256();
        } else {
            // 5 weis modexp
            modexp();
        }
    }

    function ecAdd() internal {
        bytes32 initHash = keccak256(
            abi.encodePacked(uint256(blockhash(block.number - 1)) + msg.value)
        );
        uint256 maxNum = uint256(
            0x30644e72e131a029b85045b68181585d97816a916871ca8d3c208c16d87cfd45
        ) / 2;
        uint256 initHashNum = uint256(initHash);
        uint256 newRandom = initHashNum % maxNum;
        uint256 newRandom2 = uint256(sha256(abi.encodePacked(newRandom))) %
            maxNum;
        uint256 x = 1;
        uint256 y = 2;
        bytes32[2] memory outEcAdd1;
        bytes32[2] memory outEcAdd2;
        bytes32[2] memory output;
        assembly {
            let pointer := mload(0x40)
            mstore(pointer, x)
            mstore(add(pointer, 0x20), y)
            mstore(add(pointer, 0x40), newRandom)
            let resultCall := call(
                gas(),
                0x07,
                0,
                pointer,
                0x60,
                outEcAdd1,
                0x40
            )
            sstore(0x13, resultCall)
            mstore(add(pointer, 0x40), newRandom2)
            resultCall := call(gas(), 0x07, 0, pointer, 0x60, outEcAdd2, 0x40)
            sstore(0x14, resultCall)
            resultCall := call(gas(), 0x06, 0, outEcAdd1, 0x80, output, 0x40)
            sstore(0x15, resultCall)
        }
        res0 = output[0];
        res1 = output[1];
    }

    function ecMul() internal {
        bytes32 initHash = keccak256(
            abi.encodePacked(uint256(blockhash(block.number - 1)) + msg.value)
        );
        uint256 maxNum = uint256(
            0x30644e72e131a029b85045b68181585d97816a916871ca8d3c208c16d87cfd45
        ) / 2;
        uint256 initHashNum = uint256(initHash);
        uint256 newRandom = uint256(
            sha256(abi.encodePacked(initHashNum % maxNum))
        ) % maxNum;
        uint256 x = 1;
        uint256 y = 2;
        bytes32[2] memory output;
        assembly {
            let pointer := mload(0x40)
            mstore(pointer, x)
            mstore(add(pointer, 0x20), y)
            mstore(add(pointer, 0x40), newRandom)
            let resultCall := call(gas(), 0x07, 0, pointer, 0x60, output, 0x40)
        }
        res0 = output[0];
        res1 = output[1];
    }

    function preSha256() internal {
        bytes32 initHash = keccak256(
            abi.encodePacked(uint256(blockhash(block.number - 1)) + msg.value)
        );
        bytes32 newRandomHash = sha256(abi.encodePacked(initHash));
        uint256 randomLength = uint256(newRandomHash) % 312; // 10000 / 32 ~= 312
        bytes32[1] memory output;
        bytes memory result;
        bytes32[312] memory random;
        for (uint i = 0; i < randomLength; i++) {
            newRandomHash = sha256(abi.encodePacked(newRandomHash));
            assembly {
                mstore(add(random, mul(0x20, i)), newRandomHash)
            }
        }

        assembly {
            let resultCall := call(
                gas(),
                0x02,
                0x0,
                random,
                mul(randomLength, 0x20),
                output,
                0x20
            )
        }
        res0 = output[0];
        res1 = 0;
    }

    function modexp() internal {
        bytes32 initHash = keccak256(
            abi.encodePacked(uint256(blockhash(block.number - 1)) + msg.value)
        );
        bytes32 newHash = sha256(abi.encodePacked(initHash));
        bytes32[99] memory random;
        assembly {
            mstore(random, 1024)
            mstore(add(random, 0x20), 1024)
            mstore(add(random, 0x40), 1024)
        }
        for (uint i = 3; i < 99; i++) {
            assembly {
                mstore(add(random, mul(0x20, i)), newHash)
            }
            newHash = sha256(abi.encodePacked(newHash));
        }
        bytes32[32] memory result;
        assembly {
            // call the precompiled contract BigModExp (0x05)
            let success := call(gas(), 0x05, 0x0, random, 0xc60, result, 0x400)
        }
        for (uint i = 0; i < 32; i++) {
            assembly {
                let auxresult := mload(add(result, mul(0x20, i)))
                sstore(i, auxresult)
            }
        }
    }

    function withdraw() public {
        address payable to = payable(msg.sender);
        to.transfer(address(this).balance);
    }
}