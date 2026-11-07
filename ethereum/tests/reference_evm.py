"""Frozen Python assembler oracle; tests only. Production assembly is PLAN."""
from eth_utils import keccak

ALLOWED = {1, 2, 3, 4, 16, 17, 20, 21, 53, 81, 82, 86, 87}
TOPIC = keccak(text='Result(uint256,uint256)')


def push(n):
    if type(n) is not int or not 0 <= n < 2**256:
        raise ValueError('PUSH value outside uint256')
    data = n.to_bytes(max(1, (n.bit_length() + 7) // 8), 'big')
    return bytes([0x5f + len(data)]) + data


def assemble(tokens):
    labels, pc = {}, 0
    for t in tokens:
        if isinstance(t, int):
            pc += 1
        elif t[0] == 0:
            pc += len(push(t[1]))
        elif t[0] == 1:
            if t[1] in labels:
                raise ValueError('Duplicate label')
            labels[t[1]] = pc
            pc += 1
        elif t[0] == 2:
            pc += 3
        else:
            raise ValueError('Unknown assembly token')
    out = bytearray()
    for t in tokens:
        if isinstance(t, int):
            out.append(t)
        elif t[0] == 0:
            out.extend(push(t[1]))
        elif t[0] == 1:
            out.append(0x5b)
        else:
            out.extend(b'\x61' + labels[t[1]].to_bytes(2, 'big'))
    return bytes(out)


def signature(name, arity):
    return name + '(' + ','.join(['uint256'] * arity) + ')'


def calldata(name, args):
    return keccak(text=signature(name, len(args)))[:4] + b''.join(
        x.to_bytes(32, 'big') for x in args)


def wrap(report):
    arity = report['arity']
    if type(arity) is not int or not 1 <= arity <= 16:
        raise ValueError('Unsupported ABI arity')
    body = report['instructions']
    for t in body:
        if isinstance(t, int):
            if t not in ALLOWED:
                raise ValueError('Unsupported backend opcode')
        elif not (isinstance(t, list) and len(t) == 2 and t[0] in (0, 1, 2)
                  and type(t[1]) is int and t[1] >= 0):
            raise ValueError('Invalid backend instruction')
    evaluate = int.from_bytes(keccak(text=signature('evaluate', arity))[:4], 'big')
    record = int.from_bytes(keccak(text=signature('record', arity))[:4], 'big')
    if evaluate == record:
        raise ValueError('ABI selector collision')
    prefix = [0x34, 0x15, [2, 'value-ok'], 0x57, [0, 0], [0, 0], 0xfd,
              [1, 'value-ok'], 0x36, [0, 4 + 32 * arity], 0x14,
              [2, 'size-ok'], 0x57, [0, 0], [0, 0], 0xfd,
              [1, 'size-ok'], [0, 0], 0x35, [0, 224], 0x1c,
              0x80, [0, evaluate], 0x14, [2, 'evaluate'], 0x57,
              [0, record], 0x14, [2, 'record'], 0x57,
              [0, 0], [0, 0], 0xfd,
              [1, 'evaluate'], 0x50, [0, 0], [0, 64], 0x52, [2, 'body'], 0x56,
              [1, 'record'], [0, 1], [0, 64], 0x52, [1, 'body']]
    suffix = [[0, 64], 0x51, 0x15, [2, 'return'], 0x57,
              [0, int.from_bytes(TOPIC, 'big')], [0, 64], [0, 0], 0xa1,
              [1, 'return'], [0, 64], [0, 0], 0xf3]
    runtime = assemble(prefix + body + suffix)
    if len(runtime) > 24576:
        raise ValueError('Runtime exceeds EIP-170 code size limit')
    size = len(runtime).to_bytes(2, 'big')
    # A 12-byte nonpayable guard precedes the 15-byte copy/return program.
    guard = bytes.fromhex('341561000b5760006000fd5b')
    init = guard + b'\x61' + size + b'\x61\x00\x1b\x60\x00\x39\x61' + size + b'\x60\x00\xf3'
    inputs = [{'name': f'arg{i}', 'type': 'uint256'} for i in range(arity)]
    outputs = [{'name': 'status', 'type': 'uint256'}, {'name': 'value', 'type': 'uint256'}]
    abi = [{'type': 'function', 'name': name, 'inputs': inputs, 'outputs': outputs,
            'stateMutability': mode} for name, mode in [('evaluate', 'pure'), ('record', 'nonpayable')]]
    abi += [{'type': 'constructor', 'inputs': [], 'stateMutability': 'nonpayable'},
            {'type': 'event', 'name': 'Result', 'anonymous': False,
             'inputs': [dict(x, indexed=False) for x in outputs]}]
    return {'format': 'shrine-contract/0', 'arity': arity, 'abi': abi,
            'runtime': '0x' + runtime.hex(), 'bytecode': '0x' + (init + runtime).hex(),
            'runtimeKeccak': '0x' + keccak(runtime).hex()}
