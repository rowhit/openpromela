import logging
from nose.tools import assert_raises
from openpromela import logic, bitvector
import openpromela.bdd


BIT_LOG = 'bitblaster.txt'
# bit blasting log
bit_log = logging.getLogger('openpromela.bitvector')
h = logging.FileHandler(BIT_LOG, mode='w')
h.setLevel(logging.DEBUG)
bit_log.addHandler(h)

h = logging.StreamHandler()

log = logging.getLogger('openpromela.slugs')
# log.setLevel(5)
# log.addHandler(h)

log = logging.getLogger('openpromela.logic')
log.setLevel(1)

log = logging.getLogger('promela.ast')
log.setLevel(1)

# Promela parser
log = logging.getLogger('promela.yacc.parser')
log.setLevel('ERROR')
#
# avoid nose dumping PDFs
logging.getLogger('promela.ast').setLevel('ERROR')
logging.getLogger('astutils').setLevel('ERROR')


def test_conj():
    f = logic.conj
    assert f(['a', 'b']) == '(a) & (b)'
    assert f(['a', 'b', 'c', 'd']) == '((a) & (b)) & ((c) & (d))'
    assert f(['a', 'True']) == 'a'
    assert f(['a', 'False']) == 'False'
    assert f(['True', 'True', 'b', 'c']) == '(b) & (c)'
    assert f([]) == 'True'
    assert f(str(x) for x in xrange(1)) == '0'
    assert f(str(x) for x in []) == 'True'
    assert f(['', 'a', 'b']) == '(a) & (b)'


def test_disj():
    f = logic.disj
    assert f(['a', 'b']) == '(a) | (b)'
    assert f(['a', 'b', 'c', 'd']) == '((a) | (b)) | ((c) | (d))'
    assert f(['a', 'False']) == 'a'
    assert f(['a', 'True']) == 'True'
    assert f(['False', 'False', 'b', 'c']) == '(b) | (c)'
    assert f([]) == 'False'
    assert f(str(x) for x in xrange(1)) == '0'
    assert f(str(x) for x in []) == 'False'
    assert f(['', 'a', 'b']) == '(a) | (b)'


def test_trivial_unrealizable():
    """If realizable, then the assumption is False."""
    c = '''
    assert ltl { []<> false }
    '''
    assert logic.synthesize(c) is None


def test_false_assumption():
    c = '''
    assume ltl { false }

    assert ltl { []<> false }
    '''
    # slugs returns empty strategy if assumption is False
    # an `tulip.synth.stratgy2mealy` raises Exception
    with assert_raises(Exception):
        logic.synthesize(c)


def test_trivial_realizable():
    c = '''
    assert ltl { []<> true }
    '''
    assert logic.synthesize(c) is not None


parser = logic.Parser()
code = dict()
code['terminate'] = '''
active proctype main(){
    byte x;
    x = 1;
    true
}
'''
code['stutter'] = '''
active proctype main(){
    byte x;
    x = 1;
    x = x + 3;
    do
    :: true
    od
}
'''
code['model check triv'] = '''
assert active env proctype main(){
    do
    :: true
    od
}
'''
code['model check triv 2'] = '''
assert active env proctype main(){
    do
    :: true
    :: true
    od
}
'''
code['model check loose'] = '''
assert active env proctype main(){
    do
    :: true
    :: true; false
    od
}
'''
code['sys again'] = '''
assert active sys proctype main(){
    do
    :: true
    :: true; false
    od
}
'''


def test_assume_assert_realizability():
    realizable = {
        'stutter', 'model check triv', 'model check triv 2',
        'sys again'}
    win = {k: True for k in realizable}
    win.update({k: False for k in code if k not in realizable})
    for k, v in code.iteritems():
        print k
        mealy = logic.synthesize(v)
        assert win[k] != (mealy is None), (k, mealy)
    # print mealy
    # mealy.dump()


def run_single():
    mealy = logic.synthesize(code['sys again'])
    print mealy


def test_executability():
    # test primed var owner vs context
    p = '''
    env bool x;
    sys bool y;

    ltl { x && y && x' && y' }
    '''
    guard, primed = to_guard(p, 'sys')
    assert guard == '(((pid0_x && pid0_y) && (X pid0_x)) && (X True))', guard
    # raise Exception if primed sys variable in assumption
    with assert_raises(AssertionError):
        to_guard(p, 'env')
    # test primed var owner vs context
    p = '''
    env bool x;
    sys bool y;

    ltl { x && y && x' }
    '''
    guard, primed = to_guard(p, 'env')
    assert guard == '((pid0_x && pid0_y) && (X True))', guard
    # test negation context
    p = '''
    env bool x;
    sys bool y;

    ltl { ! x && ! y && x' && ! y' }
    '''
    guard, primed = to_guard(p, 'sys')
    assert guard == (
        '((((! pid0_x) && (! pid0_y)) && '
        '(X pid0_x)) && (! (X False)))'), guard
    # test double negation
    p = '''
    env bool x;
    sys bool y;

    ltl { ! ! x && ! y && x' && ! ! y' }
    '''
    guard, primed = to_guard(p, 'sys')
    assert guard == (
        '((((! (! pid0_x)) && (! pid0_y)) && '
        '(X pid0_x)) && (! (! (X True))))'), guard
    # test positive arithmetic context
    p = '''
    env int(0, 10) x;
    sys int(0, 5) y;

    ltl { (x == 1) && (y > 0) | (y' <= 2 + x) }
    '''
    guard, primed = to_guard(p, 'sys')
    assert guard == (
        '((pid0_x = 1) && ((pid0_y > 0) | True))'), guard
    # test negative arithmetic context
    p = '''
    env int(0, 10) x;
    sys int(0, 5) y;

    ltl { (x == 1) && (y > 0) | ! (y' <= 2 + x') }
    '''
    guard, primed = to_guard(p, 'sys')
    assert guard == (
        '((pid0_x = 1) && ((pid0_y > 0) | (! False)))'), guard
    # test primed sys var in assumptin arithmeti context
    with assert_raises(AssertionError):
        to_guard(p, 'env')
    # test synthesis of whole programs
    c = '''
    free env bool x;

    assert active sys proctype main(){
        bool y;
        do
        :: x && y' /* x */
        od
    }
    '''
    assert logic.synthesize(c) is None
    # guard of: `x || y' = true`
    # but init to false, and is imperative var
    c = '''
    free env bool x;

    assert active sys proctype main(){
        bool y;
        do
        :: x || y /* true */
        od
    }
    '''
    assert logic.synthesize(c) is None
    # y is primed, so deconstrained
    c = '''
    free env bool x;

    assert active sys proctype main(){
        free bool y;
        do
        :: x || y' /* true */
        od
    }
    '''
    assert logic.synthesize(c) is not None
    # y is free, but initially `false`
    c = '''
    free env bool x;

    assert active sys proctype main(){
        free bool y = false;
        do
        :: x || y /* true */
        od
    }
    '''
    assert logic.synthesize(c) is None
    # y is free
    c = '''
    free env bool x;

    assert active sys proctype main(){
        free bool y;
        do
        :: x || y /* true */
        od
    }
    '''
    assert logic.synthesize(c) is not None
    c = '''
    free env bool x;

    assert active sys proctype main(){
        bool y;
        do
        :: y && y' /* y */
        od
    }
    '''
    assert logic.synthesize(c) is None


def to_guard(p, assume):
    program = parser.parse(p)
    global_defs, products, ltl_blocks = program.to_table()
    (ltl,) = ltl_blocks
    f = ltl.formula
    t = logic.Table()
    logic.add_variables_to_table(
        t, global_defs, pid=0, assume_context='sys')
    guard, primed = f.to_guard(
        t, pid=0, assume=assume, primed=False, negated=False)
    return guard, primed


def test_assume_assert():
    # unconditioned ltl block
    c = "ltl { []<> x }"
    program = parser.parse(c)
    global_defs, products, ltl_blocks = program.to_table()
    (ltl,) = ltl_blocks
    assert hasattr(ltl, 'assume'), ltl
    assert ltl.assume == 'assert', ltl.assume
    # asserted ltl block
    c = "assert ltl { []<> x }"
    program = parser.parse(c)
    global_defs, products, ltl_blocks = program.to_table()
    (ltl,) = ltl_blocks
    assert hasattr(ltl, 'assume'), ltl
    assert ltl.assume == 'assert', ltl.assume
    # assumed ltl block
    c = "assume ltl { []<> x }"
    program = parser.parse(c)
    global_defs, products, ltl_blocks = program.to_table()
    (ltl,) = ltl_blocks
    assert hasattr(ltl, 'assume'), ltl
    assert ltl.assume == 'assume', ltl.assume
    # unconditioned: default to assertion owned by sys
    c = '''
    proctype foo(){
        bool x;
    }
    '''
    check_assume_owner(c, 'sys', 'sys')
    # env proctype
    c = '''
    env proctype foo(){
        bool x;
    }
    '''
    check_assume_owner(c, 'env', 'env')
    # assumption
    c = '''
    assume proctype foo(){
        bool x;
    }
    '''
    check_assume_owner(c, 'env', 'env')
    # assume sys
    c = '''
    assume sys proctype foo(){
        bool x;
    }
    '''
    check_assume_owner(c, 'env', 'sys')
    # sys pc
    c = '''
    sys proctype foo(){
        bool x;
    }
    '''
    check_assume_owner(c, 'sys', 'sys')
    # assertion
    c = '''
    assert proctype foo(){
        bool x;
    }
    '''
    check_assume_owner(c, 'sys', 'sys')
    # assertion env pc
    c = '''
    assert env proctype foo(){
        bool x;
    }
    '''
    check_assume_owner(c, 'sys', 'env')


def check_assume_owner(c, assume, owner):
    program = parser.parse(c)
    global_defs, products, ltl_blocks = program.to_table()
    (proc,) = products
    assert hasattr(proc, 'assume'), proc
    assert hasattr(proc, 'owner'), proc
    assert proc.assume == assume, proc.assume
    assert proc.owner == owner, proc.owner


def test_assume_sys():
    c = '''
    env bool x;

    assume sys proctype foo(){
        do
        :: x = ! x
        od
    }

    assert ltl { []<> x }
    '''
    assert logic.synthesize(c) is not None
    # sys must help env
    c = '''
    env bool x = false;

    assume sys proctype foo(){
        do
        :: x = ! x
        :: skip
        od
    }

    assert ltl { [] ! x }
    '''
    assert logic.synthesize(c) is not None
    # must not be trivially realizable
    c += ' assert ltl { []<> false }'
    assert logic.synthesize(c) is None
    # sys cannot avoid "[] x"
    c = '''
    env bool x = false;

    assume sys proctype foo(){
        do
        :: x = true
        od
    }

    assert ltl { [] ! x}
    '''
    assert logic.synthesize(c) is None
    # sys has to alternate
    c = '''
    env bool x = false;

    assume sys proctype foo(){
        do
        :: x = true
        :: x = false
        od
    }

    assert ltl { []<> x && []<> !x }
    '''
    assert logic.synthesize(c) is not None
    # not trivially
    c += ' assert ltl { []<> false }'
    assert logic.synthesize(c) is None
    # a larger graph
    c = '''
    env int(0, 5) x = 0;

    assume sys proctype foo(){
        do
        :: (x < 5); x = x + 1
        :: (x > 0); x = x - 1
        od
    }
    '''
    assert logic.synthesize(c) is not None
    c += ' assert ltl { []<> false }'
    assert logic.synthesize(c) is None
    # env deadlocked at init
    c = '''
    env bit x = 0;

    assume env proctype foo(){
        do
        :: x = 0
        od
    }

    assume sys proctype frozen(){
        do
        :: false; x = 1
        od
    }

    assert ltl { [](x == 0) }
    '''
    assert logic.synthesize(c) is not None
    c += 'assert ltl { []<> false }'
    assert logic.synthesize(c) is None


def test_env_sys_key():
    """Keys are named by conditioning and owner.

    This avoids the key used for assumption processes
    controlled by env to coincide with the key used for
    assertion processes controlled by sys.
    """
    c = '''
    env bit x;
    env bit y;
    bit z;

    /* env top async product = ps0 */
    assume ltl { []<>(ps0 == 0) && []<>(ps0 == 1) }

    assume active env proctype producer_0(){
        bit x;
        do
        :: x = 0; x = 1
        od
    }

    assume active env proctype producer_1(){
        bit y;
        do
        :: y = 0; y = 1
        od
    }

    assert active env proctype consumer(){
        do
        :: ((x == 0) && (y == 0)); z = 1; z = 0;
        :: !((x == 0) && (y == 0))
        od
    }

    assert ltl { []<>(z == 1) }
    '''
    assert logic.synthesize(c) is not None


def test_atomic_sys_sys():
    c = '''
    bool x;

    active sys proctype foo(){
        do
        :: atomic{ !x; x = true; x; x = false }
        od
    }

    active sys proctype spoiler(){
        do
        :: x = false; x
        od
    }


    assert ltl { []<> x }
    '''
    assert logic.synthesize(c, strict_atomic=False) is not None


def test_atomic_sys_env():
    c = '''
    env bool y;
    bool x;

    assume active env proctype one(){
        do
        :: y = true
        :: y = false
        od
    }

    assert active sys proctype two(){
        do
        :: atomic{ y'; x = true }
        :: atomic{ !y'; x = false }
        od
    }

    ltl { [] (x <-> y) }
    '''
    assert logic.synthesize(c, strict_atomic=True) is not None


def test_array():
    # single array parsed
    c = '''sys int(0, 3) x[3];'''
    program = parser.parse(c)
    (x,), _, ltlblocks = program.to_table()
    assert x.length == 3, x.length
    # single array inserted to table
    t = logic.Table()
    x.insert_logic_var(t, assume_context='sys', pid='global')
    assert 'x' in t.scopes['global'], t
    d = t.scopes['global']['x']
    assert d['length'] == 3, d
    # array ref with constant index
    c = '''
    sys int(0, 3) x[4];

    ltl { x[2] == 0}
    '''
    program = parser.parse(c)
    vardefs, _, ltlblocks = program.to_table()
    t = logic.Table()
    logic.add_variables_to_table(
        t, vardefs, pid='global', assume_context='sys')
    ltl = next(iter(ltlblocks))
    f = ltl.formula
    s, context = f.to_logic(t, pid='global')
    assert context == 'boolean', context
    assert s == '(pidglobal_x2 = 0)', s
    s, pr = f.to_guard(
        t, pid='global', assume='sys', primed=False, negated=False)
    assert not pr
    assert s == '(pidglobal_x2 = 0)', s
    s, pr = f.to_guard(
        t, pid='global', assume='sys', primed=True, negated=False)
    assert pr
    assert s == 'True', s
    s, pr = f.to_guard(
        t, pid='global', assume='sys', primed=True, negated=True)
    assert pr
    assert s == 'False', s
    # array ref with index an expr containing a var
    c = '''
    sys int(0, 3) x[3];
    sys int(0, 2) y;

    ltl { x[y] == 0 }
    '''
    program = parser.parse(c)
    vardefs, groups, ltlblocks = program.to_table()
    t = logic.Table()
    logic.add_variables_to_table(
        t, vardefs, pid='global', assume_context='sys')
    ltl = next(iter(ltlblocks))
    f = ltl.formula
    s, context = f.to_logic(t, pid='global')
    assert context == 'boolean', context
    correct = '((ite {y} = 2, {x}2, (ite {y} = 1, {x}1, {x}0)) = 0)'.format(
        x='pidglobal_x', y='pidglobal_y')
    assert s == correct, s
    s, pr = f.to_guard(
        t, pid='global', assume='sys', primed=False, negated=False)
    assert not pr
    assert s == correct
    s, pr = f.to_guard(
        t, pid='global', assume='sys', primed=True, negated=False)
    assert pr
    assert s == 'True'
    s, pr = f.to_guard(
        t, pid='global', assume='sys', primed=True, negated=True)
    assert pr
    assert s == 'False'
    # array ref with index a primed controlled var
    # raise exception if primed controlled index
    c = '''
    sys int(0, 3) x[3];
    sys int(0, 2) y;

    ltl { x[y'] == 0 }
    '''
    program = parser.parse(c)
    vardefs, groups, ltlblocks = program.to_table()
    t = logic.Table()
    logic.add_variables_to_table(
        t, vardefs, pid='global', assume_context='sys')
    ltl = next(iter(ltlblocks))
    f = ltl.formula
    s, context = f.to_logic(t, pid='global')
    correct = (
        '((ite (X {y}) = 2, {x}2, (ite (X {y}) = 1, {x}1, {x}0)) = 0)').format(
            x='pidglobal_x', y='pidglobal_y')
    assert s == correct, s
    f.to_guard(t, pid='global', assume='sys', primed=True, negated=True)
    with assert_raises(AssertionError):
        f.to_guard(t, pid='global', assume='sys', primed=False, negated=True)
    t.scopes['global']['x']['owner'] = 'env'
    with assert_raises(AssertionError):
        f.to_guard(t, pid='global', assume='sys', primed=False, negated=True)
    # realizability test
    c = '''
    active sys proctype foo(){
        int(0, 3) x[5] = 3;
        int(0, 4) y;

        x[3] = 1;

        do
        :: x[3] == 1
        od
    }
    '''
    mealy = logic.synthesize(c)
    assert mealy is not None
    c = '''
    active sys proctype foo(){
        int(0, 3) x[5] = 3;
        int(0, 4) y;

        x[3] = 1;

        do
        :: x[4] == 3
        od
    }
    '''
    mealy = logic.synthesize(c)
    assert mealy is not None
    c = '''
    active sys proctype foo(){
        int(0, 3) x[5] = 3;
        int(0, 4) y;

        x[3] = 1;

        do
        :: x[4] == 2
        od
    }
    '''
    mealy = logic.synthesize(c)
    assert mealy is None


def test_else():
    c = '''
    bit x;
    bit y;

    active sys proctype foo(){
        do
        :: x == 0
        :: y == 1
        :: else
        od
    }
    '''
    program = parser.parse(c)
    vardefs, groups, ltlblocks = program.to_table()
    t = logic.Table()
    logic.add_variables_to_table(
        t, vardefs, pid='global', assume_context='sys')
    (proc,) = groups
    g = proc.to_pg()
    for u, v, d in g.edges_iter(data=True):
        c = d['stmt']
        if not isinstance(c, logic.AST.Else):
            continue
        print c.to_logic(t, pid=0, assume='sys')
        print c.to_guard(t, pid=0, assume='sys')
    # realizability
    c = '''
    bit x;
    bit y;

    active sys proctype foo(){
        do
        :: true;
        :: else; false
        od
    }
    '''
    mealy = logic.synthesize(c)
    assert mealy is not None
    c = '''
    bit x;
    bit y;

    active sys proctype foo(){
        do
        :: true; false
        :: else;
        od
    }
    '''
    mealy = logic.synthesize(c)
    assert mealy is None
    c = '''
    bit x;
    bit y;

    active sys proctype foo(){
        do
        :: false;
        :: else;
        od
    }
    '''
    mealy = logic.synthesize(c)
    assert mealy is not None
    c = '''
    bit x;
    bit y;

    active sys proctype foo(){
        do
        :: false;
        :: else; false
        od
    }
    '''
    mealy = logic.synthesize(c)
    assert mealy is None


def test_else_bug():
    c = '''
    sys proctype foo(){
        do
        ::
            if
            :: false
            :: else
            fi
        od
    }
    '''
    assert logic.synthesize(c) is not None


def test_sync():
    c = '''
    sync{
    assert active sys proctype maintain_lock(){
        do
        :: true; false
        :: false
        od
    }

    assert active sys proctype count_burst(){
        do
        :: false
        od
    }
    }
    '''
    mealy = logic.synthesize(c)
    assert mealy is None


def slugsin_parser(s, t):
    """Helper that converts prefix to infix syntax for readability."""
    slugs_table = t.to_slugs()
    ltl_parser = bitvector.Parser()
    p = ltl_parser.parse(s)
    bitvector.add_bitnames(slugs_table)
    s = p.flatten(t=slugs_table)
    slugsin_parser = openpromela.bdd.PrefixParser()
    print slugsin_parser.parse(s)


def scaffold():
    class Parser(logic.Parser):
        start = 'full_expr'
    parser = Parser()
    e = "(x == y)'"
    tree = parser.parse(e).expr
    print(repr(tree))
    t = logic.Table()
    t.add_var(pid=0, name='x', flatname='pid0_x',
              dom='boolean', free=False, owner='sys')
    t.add_var(pid=0, name='y', flatname='pid0_y',
              dom='boolean', free=False, owner='env')
    if logic.collect_primed_vars(tree, t, pid=0, player='sys'):
        print('has next var')
    else:
        print('does not have next var')


if __name__ == '__main__':
    test_trivial_realizable()
