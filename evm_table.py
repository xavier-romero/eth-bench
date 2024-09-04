import random


opcodes = {
    # hex, opcode, pushed_bytes, stack_input, stack_output, min_gas
    0x0: ("STOP", 0, 0, 0, 0, "Halts execution."),
    0x1: ("ADD", 0, 2, 1, 3, "Addition operation."),
    0x2: ("MUL", 0, 2, 1, 5, "Multiplication operation."),
    0x3: ("SUB", 0, 2, 1, 3, "Subtraction operation."),
    0x4: ("DIV", 0, 2, 1, 5, "Integer division operation."),
    0x5: ("SDIV", 0, 2, 1, 5, "Signed integer division operation(truncated)."),
    0x6: ("MOD", 0, 2, 1, 5, "Modulo remainder operation."),
    0x7: ("SMOD", 0, 2, 1, 5, "Signed modulo remainder operation."),
    0x8: ("ADDMOD", 0, 3, 1, 8, "Modulo addition operation."),
    0x9: ("MULMOD", 0, 3, 1, 8, "Modulo multiplication operation."),
    0xA: ("EXP", 0, 2, 1, 10, "Exponential operation."),
    0xB: (
        "SIGNEXTEND",
        0,
        2,
        1,
        5,
        "Extend length of two's complement signed integer.",
    ),
    0x10: ("LT", 0, 2, 1, 3, "Less-than comparison."),
    0x11: ("GT", 0, 2, 1, 3, "Greater-than comparison."),
    0x12: ("SLT", 0, 2, 1, 3, "Signed less-than comparison."),
    0x13: ("SGT", 0, 2, 1, 3, "Signed greater-than comparison."),
    0x14: ("EQ", 0, 2, 1, 3, "Simple not operator."),
    0x15: ("ISZERO", 0, 1, 1, 3, "Equals zero comparison."),
    0x16: ("AND", 0, 2, 1, 3, "Bitwise AND operation."),
    0x17: ("OR", 0, 2, 1, 3, "Bitwise OR operation."),
    0x18: ("XOR", 0, 2, 1, 3, "Bitwise XOR operation."),
    0x19: ("NOT", 0, 1, 1, 3, "Bitwise NOT operation."),
    0x1A: ("BYTE", 0, 2, 1, 3, "Retrieve single byte from word."),
    0x20: ("SHA3", 0, 2, 1, 30, "Compute Keccak-256 hash."),
    0x30: ("ADDRESS", 0, 0, 1, 2, "Get addr of currently executing account"),
    0x31: ("BALANCE", 0, 1, 1, 20, "Get balance of the given account."),
    0x32: ("ORIGIN", 0, 0, 1, 2, "Get execution origination address."),
    0x33: ("CALLER", 0, 0, 1, 2, "Get caller address."),
    0x34: (
        "CALLVALUE",
        0,
        0,
        1,
        2,
        "Get deposited value by the instruction/transaction responsible for " \
        "this execution.",
    ),
    0x35: ("CALLDATALOAD", 0, 1, 1, 3, "Get input data of current environmnt"),
    0x36: (
        "CALLDATASIZE",
        0,
        0,
        1,
        2,
        "Get size of input data in current environment.",
    ),
    0x37: (
        "CALLDATACOPY",
        0,
        3,
        0,
        3,
        "Copy input data in current environment to memory.",
    ),
    0x38: ("CODESIZE", 0, 0, 1, 2,
           "Get size of code running in current environment."),
    0x39: (
        "CODECOPY",
        0,
        3,
        0,
        3,
        "Copy code running in current environment to memory.",
    ),
    0x3A: ("GASPRICE", 0, 0, 1, 2, "Get price of gas in current environment."),
    0x3B: ("EXTCODESIZE", 0, 1, 1, 20, "Get size of an account's code."),
    0x3C: ("EXTCODECOPY", 0, 4, 0, 20, "Copy an account's code to memory."),
    0x40: (
        "BLOCKHASH",
        0,
        1,
        1,
        20,
        "Get the hash of one of the 256 most recent complete blocks.",
    ),
    0x41: ("COINBASE", 0, 0, 1, 2, "Get the block's beneficiary address."),
    0x42: ("TIMESTAMP", 0, 0, 1, 2, "Get the block's timestamp."),
    0x43: ("NUMBER", 0, 0, 1, 2, "Get the block's number."),
    0x44: ("DIFFICULTY", 0, 0, 1, 2, "Get the block's difficulty."),
    0x45: ("GASLIMIT", 0, 0, 1, 2, "Get the block's gas limit."),
    0x50: ("POP", 0, 1, 0, 2, "Remove item from stack."),
    0x51: ("MLOAD", 0, 1, 1, 3, "Load word from memory."),
    0x52: ("MSTORE", 0, 2, 0, 3, "Save word to memory."),
    0x53: ("MSTORE8", 0, 2, 0, 3, "Save byte to memory."),
    0x54: ("SLOAD", 0, 1, 1, 50, "Load word from storage."),
    0x55: ("SSTORE", 0, 2, 0, 0, "Save word to storage."),
    0x56: ("JUMP", 0, 1, 0, 8, "Alter the program counter."),
    0x57: ("JUMPI", 0, 2, 0, 10, "Conditionally alter the program counter."),
    0x58: (
        "GETPC",
        0,
        0,
        1,
        2,
        "Get the value of the program counter prior to the increment.",
    ),
    0x59: ("MSIZE", 0, 0, 1, 2, "Get the size of active memory in bytes."),
    0x5A: (
        "GAS",
        0,
        0,
        1,
        2,
        "Get the amount of available gas, including the corresponding " \
        "reduction the amount of available gas.",
    ),
    0x5B: ("JUMPDEST", 0, 0, 0, 1, "Mark a valid destination for jumps."),
    0x60: ("PUSH", 1, 0, 1, 3, "Place 1 byte item on stack."),
    0x61: ("PUSH", 2, 0, 1, 3, "Place 2-byte item on stack."),
    0x62: ("PUSH", 3, 0, 1, 3, "Place 3-byte item on stack."),
    0x63: ("PUSH", 4, 0, 1, 3, "Place 4-byte item on stack."),
    0x64: ("PUSH", 5, 0, 1, 3, "Place 5-byte item on stack."),
    0x65: ("PUSH", 6, 0, 1, 3, "Place 6-byte item on stack."),
    0x66: ("PUSH", 7, 0, 1, 3, "Place 7-byte item on stack."),
    0x67: ("PUSH", 8, 0, 1, 3, "Place 8-byte item on stack."),
    0x68: ("PUSH", 9, 0, 1, 3, "Place 9-byte item on stack."),
    0x69: ("PUSH", 10, 0, 1, 3, "Place 10-byte item on stack."),
    0x6A: ("PUSH", 11, 0, 1, 3, "Place 11-byte item on stack."),
    0x6B: ("PUSH", 12, 0, 1, 3, "Place 12-byte item on stack."),
    0x6C: ("PUSH", 13, 0, 1, 3, "Place 13-byte item on stack."),
    0x6D: ("PUSH", 14, 0, 1, 3, "Place 14-byte item on stack."),
    0x6E: ("PUSH", 15, 0, 1, 3, "Place 15-byte item on stack."),
    0x6F: ("PUSH", 16, 0, 1, 3, "Place 16-byte item on stack."),
    0x70: ("PUSH", 17, 0, 1, 3, "Place 17-byte item on stack."),
    0x71: ("PUSH", 18, 0, 1, 3, "Place 18-byte item on stack."),
    0x72: ("PUSH", 19, 0, 1, 3, "Place 19-byte item on stack."),
    0x73: ("PUSH", 20, 0, 1, 3, "Place 20-byte item on stack."),
    0x74: ("PUSH", 21, 0, 1, 3, "Place 21-byte item on stack."),
    0x75: ("PUSH", 22, 0, 1, 3, "Place 22-byte item on stack."),
    0x76: ("PUSH", 23, 0, 1, 3, "Place 23-byte item on stack."),
    0x77: ("PUSH", 24, 0, 1, 3, "Place 24-byte item on stack."),
    0x78: ("PUSH", 25, 0, 1, 3, "Place 25-byte item on stack."),
    0x79: ("PUSH", 26, 0, 1, 3, "Place 26-byte item on stack."),
    0x7A: ("PUSH", 27, 0, 1, 3, "Place 27-byte item on stack."),
    0x7B: ("PUSH", 28, 0, 1, 3, "Place 28-byte item on stack."),
    0x7C: ("PUSH", 29, 0, 1, 3, "Place 29-byte item on stack."),
    0x7D: ("PUSH", 30, 0, 1, 3, "Place 30-byte item on stack."),
    0x7E: ("PUSH", 31, 0, 1, 3, "Place 31-byte item on stack."),
    0x7F: ("PUSH", 32, 0, 1, 3, "Place 32-byte (full word) item on stack."),
    0x80: ("DUP", 0, 1, 2, 3, "Duplicate 1st stack item."),
    0x81: ("DUP", 0, 2, 3, 3, "Duplicate 2nd stack item."),
    0x82: ("DUP", 0, 3, 4, 3, "Duplicate 3rd stack item."),
    0x83: ("DUP", 0, 4, 5, 3, "Duplicate 4th stack item."),
    0x84: ("DUP", 0, 5, 6, 3, "Duplicate 5th stack item."),
    0x85: ("DUP", 0, 6, 7, 3, "Duplicate 6th stack item."),
    0x86: ("DUP", 0, 7, 8, 3, "Duplicate 7th stack item."),
    0x87: ("DUP", 0, 8, 9, 3, "Duplicate 8th stack item."),
    0x88: ("DUP", 0, 9, 10, 3, "Duplicate 9th stack item."),
    0x89: ("DUP", 0, 10, 11, 3, "Duplicate 10th stack item."),
    0x8A: ("DUP", 0, 11, 12, 3, "Duplicate 11th stack item."),
    0x8B: ("DUP", 0, 12, 13, 3, "Duplicate 12th stack item."),
    0x8C: ("DUP", 0, 13, 14, 3, "Duplicate 13th stack item."),
    0x8D: ("DUP", 0, 14, 15, 3, "Duplicate 14th stack item."),
    0x8E: ("DUP", 0, 15, 16, 3, "Duplicate 15th stack item."),
    0x8F: ("DUP", 0, 16, 17, 3, "Duplicate 16th stack item."),
    0x90: ("SWAP", 0, 2, 2, 3, "Exchange 1st and 2nd stack items."),
    0x91: ("SWAP", 0, 3, 3, 3, "Exchange 1st and 3rd stack items."),
    0x92: ("SWAP", 0, 4, 4, 3, "Exchange 1st and 4th stack items."),
    0x93: ("SWAP", 0, 5, 5, 3, "Exchange 1st and 5th stack items."),
    0x94: ("SWAP", 0, 6, 6, 3, "Exchange 1st and 6th stack items."),
    0x95: ("SWAP", 0, 7, 7, 3, "Exchange 1st and 7th stack items."),
    0x96: ("SWAP", 0, 8, 8, 3, "Exchange 1st and 8th stack items."),
    0x97: ("SWAP", 0, 9, 9, 3, "Exchange 1st and 9th stack items."),
    0x98: ("SWAP", 0, 10, 10, 3, "Exchange 1st and 10th stack items."),
    0x99: ("SWAP", 0, 11, 11, 3, "Exchange 1st and 11th stack items."),
    0x9A: ("SWAP", 0, 12, 12, 3, "Exchange 1st and 12th stack items."),
    0x9B: ("SWAP", 0, 13, 13, 3, "Exchange 1st and 13th stack items."),
    0x9C: ("SWAP", 0, 14, 14, 3, "Exchange 1st and 14th stack items."),
    0x9D: ("SWAP", 0, 15, 15, 3, "Exchange 1st and 15th stack items."),
    0x9E: ("SWAP", 0, 16, 16, 3, "Exchange 1st and 16th stack items."),
    0x9F: ("SWAP", 0, 17, 17, 3, "Exchange 1st and 17th stack items."),
    0xA0: ("LOG", 0, 2, 0, 375, "Append log record with no topics."),
    0xA1: ("LOG", 0, 3, 0, 750, "Append log record with one topic."),
    0xA2: ("LOG", 0, 4, 0, 1125, "Append log record with two topics."),
    0xA3: ("LOG", 0, 5, 0, 1500, "Append log record with three topics."),
    0xA4: ("LOG", 0, 6, 0, 1875, "Append log record with four topics."),
    0xF0: ("CREATE", 0, 3, 1, 32000,
           "Create a new account with associated code."),
    0xF1: ("CALL", 0, 7, 1, 40, "Message-call into an account."),
    0xF2: (
        "CALLCODE",
        0,
        7,
        1,
        40,
        "Message-call into this account with alternative account's code.",
    ),
    0xF3: ("RETURN", 0, 2, 0, 0, "Halt execution returning output data."),
    0xFE: ("INVALID", 0, 0, 0, 0, "Designated invalid instruction."),
    0xFF: (
        "SELFDESTRUCT",
        0,
        1,
        0,
        0,
        "Halt execution and register account for later deletion.",
    ),
}
opcodes_count = len(opcodes)
# opcodes_list = list(opcodes)
opcodes_list = [(x, opcodes[x][2], opcodes[x][3]) for x in opcodes]
# opcodes_list = [x for x in opcodes]


def random_bytecode(bytes_len=32):
    # bytecode = "0x6080604052"
    bytecode = "0x"
    bytes_left = bytes_len
    # for _ in range(bytes_len):
    while bytes_left > 0:
        i = random.randint(0, opcodes_count-1)
        op = opcodes_list[i][0]
        stack_in = opcodes_list[i][1]
        # stack_out = opcodes_list[i][2]
        for _ in range(stack_in):
            bytecode += f"60{i:02x}"
            bytes_left -= 2
        bytecode += f"{op:02x}"
        bytes_left -= 1

    return bytecode


def all_valid_bytecode_combinations(bytes_len, start=None):
    import itertools

    if not start:
        start = "0x"
        for _ in range(bytes_len):
            start += "00"

    bytes_list = [opcodes_list[i][0] for i in range(opcodes_count)]
    combinations = itertools.product(bytes_list, repeat=bytes_len)
    bytecodes = []
    started = False
    for comb in combinations:
        bytecode = "0x"
        for b in comb:
            bytecode += f"{b:02x}"
        if started or (bytecode == start):
            bytecodes.append(bytecode)
            started = True

    return bytecodes


def all_bytecode_combinations(bytes_len, start=None, end=None):
    import itertools

    if not start:
        start = "0x"
        for _ in range(bytes_len):
            start += "00"

    bytes_list = [f"{i:02x}" for i in range(256)]
    combinations = itertools.product(bytes_list, repeat=bytes_len)
    bytecodes = []
    started = False
    for comb in combinations:
        bytecode = "0x"
        for b in comb:
            bytecode += b
        if started or (bytecode == start):
            bytecodes.append(bytecode)
            started = True
        if end and (bytecode == end):
            break

    return bytecodes
