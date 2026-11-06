"""Closed arithmetic feature language. Parse Python-shaped text; NEVER eval/import it.

Candidates append 1..3 row-local interactions to the ten unchanged input columns.
There is no fitting, label argument, mutable state, file access or Python execution.
"""
import ast
import math
import operator
import random
import statistics

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
FUNCS = {'abs': abs, 'min': min, 'max': max, 'sqrt': math.sqrt, 'log1p': math.log1p}


def parse(source):
    if not isinstance(source, str) or not 1 <= len(source.encode()) <= 8192:
        raise ValueError('Candidate must be <=8 KiB of arithmetic feature code')
    try: tree = ast.parse(source)
    except (SyntaxError, RecursionError) as exc: raise ValueError('Invalid feature syntax') from exc
    if len(list(ast.walk(tree))) > 160: raise ValueError('Feature expression too complex')
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError('Only def augment(row): return [expressions] is supported')
    fn = tree.body[0]
    args = fn.args
    if (fn.name != 'augment' or fn.decorator_list or fn.returns or fn.type_comment
            or len(args.args) != 1 or args.args[0].arg != 'row' or args.args[0].annotation
            or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults
            or len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return)
            or not isinstance(fn.body[0].value, ast.List)):
        raise ValueError('Only unannotated augment(row) with one literal return list is supported')
    expressions = fn.body[0].value.elts
    if not 1 <= len(expressions) <= 3: raise ValueError('Append one to three fixed interactions only')

    def check(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float) and math.isfinite(node.value) and abs(node.value) <= 10:
            return set()
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'row'
                and isinstance(node.slice, ast.Constant) and type(node.slice.value) is int and 0 <= node.slice.value < 10):
            return {node.slice.value}
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return check(node.left) | check(node.right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return check(node.operand)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS
                and not node.keywords and len(node.args) == (2 if node.func.id in ('min', 'max') else 1)):
            return set().union(*(check(arg) for arg in node.args))
        raise ValueError('Unsupported feature expression; no imports, attributes, loops, state or arbitrary calls')
    for expression in expressions:
        if len(check(expression)) < 2: raise ValueError('Each feature must interact with at least two original columns')
    return expressions


def evaluate(expressions, row):
    if len(row) != 10: raise ValueError('Expected ten original columns')
    def visit(node):
        if isinstance(node, ast.Constant): return node.value
        if isinstance(node, ast.Subscript): return row[node.slice.value]
        if isinstance(node, ast.BinOp): return OPS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp): return -visit(node.operand) if isinstance(node.op, ast.USub) else visit(node.operand)
        return FUNCS[node.func.id](*(visit(arg) for arg in node.args))
    try: values = [float(visit(node)) for node in expressions]
    except (ValueError, OverflowError, ZeroDivisionError) as exc: raise ValueError('Feature is undefined on an input row') from exc
    if not all(math.isfinite(value) for value in values): raise ValueError('Non-finite engineered feature')
    return list(row) + values


def review(source):
    """Synthetic structural probe only. Does not certify useful or novel science."""
    expressions = parse(source)
    rng=random.Random(1801)
    # Respect one-hot sex: invalid categorical rows would hide identities such as M+F+I=1.
    rows=[[float(j==sex) for j in range(3)]+[0.]*7 for sex in range(3)]
    rows += [[float(j==i%3) for j in range(3)]+[rng.random() for _ in range(7)] for i in range(60)]
    outputs = [evaluate(expressions,row)[10:] for row in rows]
    seen = set()
    for col, expression in enumerate(expressions):
        values = tuple(output[col] for output in outputs)
        if max(values)-min(values) < 1e-12 or values in seen:
            raise ValueError('Constant or duplicate feature: reject without repair')
        if any(all(abs(v-row[j]) < 1e-12 for v,row in zip(values,rows)) for j in range(10)):
            raise ValueError('Feature duplicates an existing column')
        for j in range(10):
            groups={}
            for value,row in zip(values,rows): groups.setdefault(row[j],[]).append(value)
            if any(max(g)-min(g)>1e-12 for g in groups.values()): continue
            ordered=[statistics.mean(groups[key]) for key in sorted(groups)]
            if all(a<=b for a,b in zip(ordered,ordered[1:])) or all(a>=b for a,b in zip(ordered,ordered[1:])):
                raise ValueError('Probe found a redundant single-column monotone feature')
        active = set()
        for row in rows[1:]:
            original = evaluate([expression],row)[-1]
            for j in range(10):
                altered = list(row)
                if j<3: altered[:3]=[float(k==j) for k in range(3)]
                else: altered[j] += .037
                if abs(evaluate([expression],altered)[-1]-original) > 1e-12: active.add(j)
        if len(active) < 2: raise ValueError('Probe found fewer than two effective feature inputs')
        seen.add(values)
    return {'language':'row-arithmetic-v1','appended_features':len(expressions),
            'canonical':ast.dump(ast.Expression(body=ast.List(elts=expressions,ctx=ast.Load())),include_attributes=False),
            'synthetic_probe_passed':True,'limit':'Finite probes reject obvious no-ops; no proof of novelty or benefit'}
