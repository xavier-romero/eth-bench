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

As an example / POC, the contract is deployed on zkEVM Cardona at ```0x590B15500B1a2B92395960D5E2d243f4C454EE51```, so you can test it this way:

    SC_ADDR=0x590B15500B1a2B92395960D5E2d243f4C454EE51
    RPC_URL=https://rpc.cardona.zkevm-rpc.com/
    PRIV_KEY=xxxxxxxxxxxx
    OPCODE=0x20
    OFFSET=1

    cast send --legacy --rpc-url $RPC_URL --private-key $PRIV_KEY $SC_ADDR 'TestMemoryOffset(bytes1,uint256)' $OPCODE $OFFSET

An event will be emitted in the transaction with the main purpose to confirm the right opcode has been executed. This is the signature:

    OpcodeTestResult(bytes1 opcode, uint256 offset, uint256 gasUsed)
