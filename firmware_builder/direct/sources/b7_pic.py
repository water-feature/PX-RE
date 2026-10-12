# SPDX-License-Identifier: GPL-2.0-or-later
BASE = 2634022912
REGS = 'zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split()
R = dict(zip(REGS, range(32)))
PARAM = 2147484780
GATE = 2147512318
ENTRY = 2634341068
CAPTURE = 2634027552
ORDER = 2634027584
ADAPT_A = 2634027712
ADAPT_B = 2634027760
PUSH = 2634027808
BLOCKS = {}

def block(base, instructions):
    labels = {}
    pc = base
    for row in instructions:
        if row[0].endswith(':'):
            labels[row[0][:-1]] = pc
        else:
            pc += 4
    pc = base
    for row in instructions:
        if row[0].endswith(':'):
            continue
        BLOCKS[pc] = tuple((labels.get(x, x) if isinstance(x, str) else x for x in row))
        pc += 4
    return pc
CAPTURE_END = block(CAPTURE, [('sw', 'a3', 16, 'sp'), ('j', 2634341116), ('move', 's2', 'a1')])
ORDER_END = block(ORDER, [('addiu', 't0', 's0', -65), ('sltiu', 't1', 's0', 65), ('movn', 't0', 's0', 't1'), ('addiu', 't1', 't0', -7), ('andi', 't1', 't1', 65533), ('bne', 't1', 'zero', 'done'), ('nop',), ('lw', 's3', 16, 'sp'), ('addiu', 't2', 's0', 1719), ('sll', 't2', 't2', 1), ('addu', 't2', 's1', 't2'), ('addiu', 't1', 't0', -7), ('bne', 't1', 'zero', 'end'), ('nop',), ('lhu', 't3', 4, 't2'), ('sltu', 't1', 't3', 's3'), ('j', 'done'), ('movn', 's3', 't3', 't1'), ('end:',), ('lhu', 't3', -4, 't2'), ('sltu', 't1', 's3', 't3'), ('movn', 's3', 't3', 't1'), ('done:',), ('j', 2634342312), ('li', 'a0', 1)])

def adapter(base, part, yes, no):
    return block(base, [('move', 'a0', 's5'), ('li', 'a1', part), ('jal', PUSH), ('move', 'a2', 'v1'), ('bne', 's5', 'zero', 'yes'), ('nop',), ('j', no), ('nop',), ('yes:',), ('j', yes), ('nop',)])
AA_END = adapter(ADAPT_A, 0, 2634342016, 2634342000)
AB_END = adapter(ADAPT_B, 1, 2634342356, 2634342340)
PUSH_END = block(PUSH, [('addiu', 't0', 's0', -65), ('sltiu', 't1', 's0', 65), ('movn', 't0', 's0', 't1'), ('addiu', 't1', 't0', -7), ('andi', 't1', 't1', 65533), ('bne', 't1', 'zero', 'return'), ('nop',), ('addiu', 't1', 't0', -5), ('sll', 't1', 't1', 1), ('subu', 't2', 'a2', 't1'), ('lhu', 't1', 0, 't2'), ('beq', 't1', 'zero', 'return'), ('nop',), ('lhu', 'a3', 0, 'a2'), ('lhu', 't3', 20, 't2'), ('addiu', 't1', 't0', -7), ('bne', 't1', 'zero', 'end'), ('nop',), ('sltu', 't1', 't3', 'a3'), ('j', 'cross'), ('nop',), ('end:',), ('sltu', 't1', 'a3', 't3'), ('cross:',), ('beq', 't1', 'zero', 'return'), ('nop',), ('subu', 'a2', 's0', 't0'), ('j', ENTRY), ('addiu', 'a2', 'a2', 15), ('return:',), ('jr', 'ra'), ('nop',)])
assert CAPTURE_END <= ORDER and ORDER_END <= ADAPT_A
assert AA_END <= ADAPT_B and AB_END <= PUSH and (PUSH_END <= 2634028160)
GATES = {2634343120: 2634343660, 2634341572: 2634343660, 2634343636: 2634343660, 2634343456: 2634343660, 2634341864: 2634343600, 2634341372: 2634343600, 2634343576: 2634343600, 2634343516: 2634343600}
OVERLAY = {a: ('j', b) for a, b in GATES.items()}
OVERLAY.update({2634341108: ('j', CAPTURE), 2634342304: ('j', ORDER), 2634341992: ('j', ADAPT_A), 2634342332: ('j', ADAPT_B)})
