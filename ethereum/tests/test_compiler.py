import json
import random
import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3, EthereumTesterProvider
from reference_evm import wrap, calldata, TOPIC
from plan import compile_contract, run


@pytest.fixture(scope='module')
def reports():
    words = [0, 1, 2, 7, 2**128, 2**255, 2**256 - 1]
    pairs = [[x, y] for x in words for y in words]
    rng = random.Random(107)
    pairs += [[rng.randrange(2**256), rng.randrange(2**256)] for _ in range(30)]
    encoded = '[' + ' '.join(f'[{a} {b}]' for a, b in pairs) + ']'
    return run(f'''(#bind build (#module contract-build))
(#bind lower (#module contract-lower))
(#bind json (#module wire-json))
(#bind std (#module std))
(#import std)
(#bind reef (#module reef))
(#import reef)
(print ["CONTRACT-OUTPUT" (json:jarr
  (map (lambda (tag) (build:report (lower:lower [2 [tag [0 0] [0 1]]]) {encoded}))
    [2 3 4 5 6 7]))])''')


def deployed(report):
    w3 = Web3(EthereumTesterProvider())
    artifact = report['artifact']
    receipt = w3.eth.wait_for_transaction_receipt(w3.eth.send_transaction(
        {'from': w3.eth.accounts[0], 'data': artifact['bytecode'], 'gas': 4_000_000}))
    assert receipt.status == 1
    assert w3.eth.get_code(receipt.contractAddress).hex() == artifact['runtime'][2:]
    return w3, receipt.contractAddress


@pytest.mark.parametrize('index', range(6))
def test_plan_evm_differential(reports, index):
    report = reports[index]
    w3, address = deployed(report)
    for args, reference in report['reference']:
        data = w3.eth.call({'to': address, 'data': calldata('evaluate', args)})
        assert len(data) == 64
        assert [int.from_bytes(data[:32], 'big'), int.from_bytes(data[32:], 'big')] == reference


def test_foil_contract_abi_and_events():
    cases = [[6, 7, 7], [2**255, 2, 0], [2**255, 2, 1], [2**256 - 1, 1, 1], [0, 0, 2]]
    report = compile_contract(cases=cases)
    w3, address = deployed(report)
    with pytest.raises(TransactionFailed):
        w3.eth.call({'from': w3.eth.accounts[0], 'data': wrap(report)['bytecode'], 'value': 1})
    for args, reference in report['reference']:
        result = w3.eth.call({'to': address, 'data': calldata('evaluate', args)})
        assert list(w3.codec.decode(['uint256', 'uint256'], result)) == reference
        receipt = w3.eth.wait_for_transaction_receipt(w3.eth.send_transaction(
            {'from': w3.eth.accounts[0], 'to': address, 'data': calldata('record', args)}))
        assert len(receipt.logs) == 1
        assert receipt.logs[0]['topics'] == [TOPIC]
        assert list(w3.codec.decode(['uint256', 'uint256'], receipt.logs[0]['data'])) == reference
    for data in [b'', b'\xff' * 100, calldata('evaluate', [1, 2]), calldata('evaluate', [1, 2, 3]) + b'\x00']:
        with pytest.raises(TransactionFailed):
            w3.eth.call({'to': address, 'data': data})
    with pytest.raises(TransactionFailed):
        w3.eth.call({'from': w3.eth.accounts[0], 'to': address,
                    'data': calldata('evaluate', [1, 2, 3]), 'value': 1})


def test_lazy_helpers_and_fault_order():
    report = run('''(#bind build (#module contract-build))
(#bind rp (#module restricted-plan))
(#bind lower (#module contract-lower))
(#bind std (#module std))
(#import std)
(#bind reef (#module reef))
(#import reef)
(define ignored (lower:expression 1 [5 [1 1] [1 0]] 0))
(define first (Law 1 "first" 1))
(define body (lower:call first [(lower:call rp:lift [1]) ignored]))
(define entry (Law 0 "lazy" body))
(define artifact ["restricted-plan/0" entry
  [[entry [rp:WORD] rp:RESULT] [first [rp:RESULT rp:RESULT] rp:RESULT]]])
(print ["CONTRACT-OUTPUT" (build:report artifact [[9] [0]])])''')
    w3, address = deployed(report)
    for args, reference in report['reference']:
        value = w3.eth.call({'to': address, 'data': calldata('evaluate', args)})
        assert list(w3.codec.decode(['uint256', 'uint256'], value)) == reference
    ordered = run('''(#bind build (#module contract-build))
(#bind lower (#module contract-lower))
(#bind std (#module std))
(#import std)
(print ["CONTRACT-OUTPUT" (build:report
  (lower:lower [1 [2 [3 [1 0] [1 1]] [5 [1 1] [1 0]]]]) [[0]])])''')
    w3, address = deployed(ordered)
    assert w3.codec.decode(['uint256', 'uint256'], w3.eth.call(
        {'to': address, 'data': calldata('evaluate', [0])})) == (1, 3)


def test_reject_bad_dsl_and_effectful_plan():
    # These checks execute in the same compiler runtime as production builds.
    result = run('''(#bind build (#module contract-build))
(#bind lower (#module contract-lower))
(#bind evm (#module contract-evm))
(#bind rp (#module restricted-plan))
(#bind std (#module std))
(#import std)
(#bind reef (#module reef))
(#import reef)
(define bad [[0 [1 0]] [17 [1 0]] [1 [0 1]] [1 [1 (Bex 256)]] [1 [99 0]] [1 [2 [1 0]]]])
assert(all (lambda (manifest) (Eq 1 (Hd (Try lower:lower manifest)))) bad)
(define effect (Law 0 "effect" (0 Now (0 0))))
assert(Eq 1 (Hd (Try evm:compile ["restricted-plan/0" effect [[effect [rp:WORD] rp:RESULT]]])))
(print ["CONTRACT-OUTPUT" "[1]"])''')
    assert result == [1]


def test_assembler_rejects_duplicate_and_oversized_code():
    result = run('''(#bind asm (#module contract-assemble))
(#bind std (#module std))
(#import std)
(#bind reef (#module reef))
(#import reef)
assert(Eq 1 (Hd (Try asm:assemble [[1 0] [1 0]])))
assert(Eq 1 (Hd (Try asm:assemble [[2 99]])))
assert(Eq 1 (Hd (Try asm:assemble [[0 (Bex 256)]])))
assert(Eq 1 (Hd (Try (asm:runtime 1) [241])))
assert(Eq 1 (Hd (Try (asm:runtime 1) [[3 0]])))
assert(Eq 1 (Hd (Try (asm:runtime 1) (gen 24576 (lambda (i) 1)))))
(print ["CONTRACT-OUTPUT" "[1]"])''')
    assert result == [1]


def test_choose_condition_and_expansion_budget():
    report = run('''(#bind build (#module contract-build))
(#bind lower (#module contract-lower))
(#bind evm (#module contract-evm))
(#bind rp (#module restricted-plan))
(#bind std (#module std))
(#import std)
(#bind reef (#module reef))
(#import reef)
(define duplicate (Law 0 "duplicate" (lower:call rp:plus [1 1])))
(define (nested n e) (Ifz n e (nested (Dec n) (lower:call duplicate [e]))))
(define entry (Law 0 "expansion" (nested 16 (lower:call rp:lift [1]))))
(define huge ["restricted-plan/0" entry
  [[entry [rp:WORD] rp:RESULT] [duplicate [rp:RESULT] rp:RESULT]]])
assert(Eq 1 (_0 (rp:validate huge)))
assert(Eq 1 (Hd (Try evm:compile huge)))
(print ["CONTRACT-OUTPUT" (build:report
  (lower:lower [1 [8 [0 0] [1 7] [5 [1 1] [1 0]]]]) [[0] [1] [2]])])''')
    w3, address = deployed(report)
    for args, reference in report['reference']:
        got = w3.eth.call({'to': address, 'data': calldata('evaluate', args)})
        assert list(w3.codec.decode(['uint256', 'uint256'], got)) == reference


def test_native_artifact_matches_deployed_and_python_oracle():
    from plan import ROOT
    artifact = compile_contract()['artifact']
    historical = json.loads((ROOT / 'ethereum/artifacts/checked.json').read_text())
    for key in ('runtime', 'bytecode', 'runtimeKeccak', 'abi'):
        assert artifact[key] == historical[key]
    report = compile_contract()
    reference = wrap(report)
    for key in ('runtime', 'bytecode', 'runtimeKeccak', 'abi'):
        assert report['artifact'][key] == reference[key]


def test_native_keccak_padding_and_multiblock_vectors():
    from eth_utils import keccak
    vectors = [bytes(i % 256 for i in range(n)) for n in (0, 1, 31, 32, 64, 135, 136, 137, 271, 272, 400)]
    rows = '[' + ' '.join('[' + ' '.join(map(str, v)) + ']' for v in vectors) + ']'
    hashes = run(f'''(#bind source (#module contract-source))
(#bind foil (#module foil-new-env))
(#bind build (#module contract-build))
(#bind std (#module std))
(#import std)
(#bind reef (#module reef))
(#import reef)
(#bind json (#module wire-json))
(define crypto (source:load "ethereum_keccak"))
(define digest (foil:source-entry-val ["ethereum_keccak" "digest"] crypto))
(print ["CONTRACT-OUTPUT" (json:jarr (map (lambda (bytes) (build:numbers (digest bytes))) {rows}))])''')
    assert [bytes(h) for h in hashes] == [keccak(v) for v in vectors]
