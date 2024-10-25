# Tester

Smar Contract [available here](Tester.sol).

## TestMemoryOffset
This function allows to call various opcodes with arbitrary offset.

    TestMemoryOffset(bytes1 opcode, uint256 offset)

The opcode needs to be one of:
- 0x20 	SHA3
- 0x37 	CALLDATACOPY
- 0x39 	CODECOPY
- 0x3C 	EXTCODECOPY
- 0x3E 	RETURNDATACOPY
- 0x51 	MLOAD
- 0x52 	MSTORE
- 0x53 	MSTORE8
- 0xA0 	LOG0
- 0xA1 	LOG1
- 0xA2 	LOG2
- 0xA3 	LOG3
- 0xA4 	LOG4
- 0xF0 	CREATE
- 0xF1 	CALL
- 0xF2 	CALLCODE
- 0xF3 	RETURN
- 0xF4 	DELEGATECALL
- 0xF5  CREATE2
- 0xFA 	STATICCALL
- 0xFD 	REVERT

If your contract is deployed at addr ```0xc0d132bc25972182afc47c37e38ab3d196d963dd```, you can test it this way:

    SC_ADDR=0xc0d132bc25972182afc47c37e38ab3d196d963dd
    RPC_URL=http://127.0.0.1:32921  # Replace with your RPC URL
    PRIV_KEY=xxxxxxxxxxxx
    OPCODE=0x20
    OFFSET=1

    cast send --legacy --rpc-url $RPC_URL --private-key $PRIV_KEY $SC_ADDR 'TestMemoryOffset(bytes1,uint256)' $OPCODE $OFFSET

Two events will be emitted in the transaction with the main purpose to confirm the right opcode has been executed with the right offset. These are the signatures:

    OffsetUsed(bytes32 offset);
    OpcodeTestResult(bytes1 opcode, uint256 gasUsed);
