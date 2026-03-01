from dataclasses import dataclass, asdict
from functools import lru_cache
from typing import List, Dict, Any, Tuple
import re

import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)


@dataclass
class Step:
    """Represents a single step in equation solving."""
    description: str
    expression: str
    rule: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _validate_raw_input(text: str) -> None:
    """
    Perform basic validation on the raw input string to guard against
    obviously unsafe patterns. This does not execute any code, it only
    rejects suspicious substrings.
    """
    if not isinstance(text, str):
        raise ValueError("Input must be a string.")

    # Basic size guard to prevent extremely large payloads
    if len(text) > 2000:
        raise ValueError("Input expression is too long.")

    lowered = text.lower()
    blocked = [
        "__",
        "import",
        "lambda",
        "eval",
        "exec",
        "os.",
        "sys.",
        "subprocess",
        "open(",
        "read(",
        "write(",
        "input(",
    ]
    if any(b in lowered for b in blocked):
        raise ValueError("Input contains unsafe or unsupported patterns.")


@lru_cache(maxsize=256)
def _parse_expression(expr_str: str, variable: str = "x") -> sp.Expr:
    """
    Parse a user-entered expression string into a SymPy expression using
    sympy.parsing.sympy_parser.parse_expr with a restricted symbol set.
    """
    _validate_raw_input(expr_str)

    # Restrict allowed symbolic variables to a small, known set.
    if variable not in ("x", "y", "z"):
        raise ValueError("Only variables x, y, and z are supported.")

    x, y, z = sp.symbols("x y z")
    local_dict = {
        "x": x,
        "y": y,
        "z": z,
        variable: {"x": x, "y": y, "z": z}[variable],
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "exp": sp.exp,
        "ln": sp.log,
        "log": sp.log,
        "sqrt": sp.sqrt,
        "pi": sp.pi,
        "e": sp.E,
        "Matrix": sp.Matrix,
    }

    transformations = standard_transformations + (implicit_multiplication_application,)
    return parse_expr(expr_str, local_dict=local_dict, transformations=transformations)


def _analyze_structure(expr: sp.Expr, variable: str) -> Tuple[str, str]:
    """
    Inspect the expression and return (rule_name, human_explanation).
    """
    x = sp.symbols(variable)
    simplified = sp.simplify(expr)
    num, den = sp.fraction(simplified)

    if den != 1 and num.has(x) and den.has(x):
        return (
            "Quotient rule",
            "This expression is a quotient f(x)/g(x) where both numerator and denominator depend on x.",
        )

    if isinstance(simplified, sp.Mul) and any(arg.has(x) for arg in simplified.args):
        return (
            "Product rule",
            "This expression is a product of functions of x: f(x)·g(x).",
        )

    if isinstance(simplified, sp.Pow) and simplified.base.has(x) and not simplified.exp.has(x):
        return (
            "Power rule",
            "This is a power of x of the form [f(x)]^n with constant n, so we can use the power rule.",
        )

    if simplified.is_Function and simplified.args and simplified.args[0].has(x):
        return (
            "Chain rule",
            "This is a composition of an outer function and an inner function of x, so we use the chain rule.",
        )

    if isinstance(simplified, sp.Add):
        return (
            "Sum rule",
            "This is a sum of terms; differentiate each term separately and then add the results.",
        )

    return (
        "General differentiation",
        "Differentiate the expression using standard differentiation rules term by term.",
    )


def _rule_formula_explanation(rule_name: str) -> str:
    """
    Short mathematical explanation for the chosen rule.
    """
    if rule_name == "Product rule":
        return "Using the product rule: d/dx [f(x)·g(x)] = f'(x)·g(x) + f(x)·g'(x)."
    if rule_name == "Quotient rule":
        return "Using the quotient rule: d/dx [f(x)/g(x)] = (f'(x)·g(x) - f(x)·g'(x)) / [g(x)]²."
    if rule_name == "Chain rule":
        return "Using the chain rule: d/dx [f(g(x))] = f'(g(x))·g'(x)."
    if rule_name == "Power rule":
        return "Using the power rule: d/dx [xⁿ] = n·xⁿ⁻¹ (combined with other rules if needed)."
    if rule_name == "Sum rule":
        return "Differentiate each term of the sum separately and then add the derivatives."
    return "Apply the appropriate differentiation rules to each part of the expression."


def _safe_latex(expr: sp.Expr) -> str:
    """
    Best-effort conversion of a SymPy expression to LaTeX.
    """
    try:
        return sp.latex(expr)
    except Exception:
        return ""


def _strip_derivative_notation(expr_str: str, variable: str) -> Tuple[str, str]:
    """
    Handle inputs like 'd/dx (x^3*exp(x^2))' by extracting the inner expression
    and the variable. If no such pattern is found, return the original string.
    """
    text = expr_str.strip()

    # Pattern 1: d/dx ( ... )
    match = re.match(r"^d/d([a-zA-Z])\s*\((.*)\)\s*$", text)
    if match:
        var = match.group(1)
        inner = match.group(2).strip()
        return inner, var

    # Pattern 2: d/dx  ...   (no parentheses)
    match = re.match(r"^d/d([a-zA-Z])\s+(.+)$", text)
    if match:
        var = match.group(1)
        inner = match.group(2).strip()
        return inner, var

    return expr_str, variable


def _clean_derivative(expr: sp.Expr) -> sp.Expr:
    """
    Apply a consistent cleanup pipeline to derivative expressions to
    reduce leftover Derivative/Subs nodes.
    """
    expr = expr.doit()
    expr = sp.simplify(expr)
    expr = sp.expand(expr)

    if expr.has(sp.Derivative) or expr.has(sp.Subs):
        expr = expr.doit()
        expr = sp.simplify(expr)
        expr = sp.expand(expr)

    return expr


def differentiate(expr_str: str, variable: str = "x", mode: str = "detailed") -> Dict[str, Any]:
    """
    Differentiate an expression with respect to a variable and return
    a structured, symbolic, step-by-step explanation.

    - If the input looks like 'd/dx ( ... )', only the inner expression
      is differentiated.
    - Uses sympy.diff + .doit() + simplify + expand to avoid leftover
      Derivative(...) or Subs(...) objects where possible.
    """
    original_input = expr_str

    # Handle explicit derivative notation like "d/dx (...)"
    cleaned_expr_str, var_from_input = _strip_derivative_notation(expr_str, variable)
    variable = var_from_input

    x = sp.symbols(variable)
    expr = _parse_expression(cleaned_expr_str, variable)

    steps: List[Dict[str, Any]] = []

    # Step 1: identify structure of the inner expression
    rule_name, structure_explanation = _analyze_structure(expr, variable)
    steps.append(
        {
            "index": 1,
            "title": "Identify structure",
            "expression": str(expr),
            "latex": _safe_latex(expr),
            "explanation": structure_explanation,
        }
    )

    # Explicit handling for common rules
    simplified_expr = sp.simplify(expr)
    current_index = 2

    # Product rule: f(x) * g(x)
    if rule_name == "Product rule" and isinstance(simplified_expr, sp.Mul):
        args = list(simplified_expr.args)
        if len(args) == 1:
            f = args[0]
            g = sp.Integer(1)
        else:
            f = args[0]
            g = sp.Mul(*args[1:])

        f_prime = sp.diff(f, x)
        g_prime = sp.diff(g, x)

        steps.append(
            {
                "index": current_index,
                "title": "Identify f(x) and g(x)",
                "expression": f"f(x) = {f},    g(x) = {g}",
                "latex": "",
                "explanation": "View the product as two functions multiplied together: f(x) and g(x).",
            }
        )
        current_index += 1

        steps.append(
            {
                "index": current_index,
                "title": "Compute f'(x)",
                "expression": f"f'(x) = {f_prime}",
                "latex": "",
                "explanation": "Differentiate f(x) with respect to the variable.",
            }
        )
        current_index += 1

        steps.append(
            {
                "index": current_index,
                "title": "Compute g'(x)",
                "expression": f"g'(x) = {g_prime}",
                "latex": "",
                "explanation": "Differentiate g(x) with respect to the variable.",
            }
        )
        current_index += 1

        raw_derivative = f_prime * g + f * g_prime
        cleaned = _clean_derivative(raw_derivative)

        steps.append(
            {
                "index": current_index,
                "title": "Apply product rule formula",
                "expression": str(raw_derivative),
                "latex": _safe_latex(raw_derivative),
                "explanation": _rule_formula_explanation(rule_name),
            }
        )
        current_index += 1

        if cleaned != raw_derivative:
            steps.append(
                {
                    "index": current_index,
                    "title": "Simplify derivative",
                    "expression": str(cleaned),
                    "latex": _safe_latex(cleaned),
                    "explanation": "Simplify the expression obtained from the product rule.",
                }
            )
        final_expr = cleaned

    # Quotient rule: f(x) / g(x)
    elif rule_name == "Quotient rule":
        num, den = sp.fraction(simplified_expr)
        f = num
        g = den
        f_prime = sp.diff(f, x)
        g_prime = sp.diff(g, x)

        steps.append(
            {
                "index": current_index,
                "title": "Identify numerator and denominator",
                "expression": f"f(x) = {f},    g(x) = {g}",
                "latex": "",
                "explanation": "Treat the expression as a quotient f(x)/g(x).",
            }
        )
        current_index += 1

        steps.append(
            {
                "index": current_index,
                "title": "Differentiate f(x) and g(x)",
                "expression": f"f'(x) = {f_prime},    g'(x) = {g_prime}",
                "latex": "",
                "explanation": "Differentiate numerator and denominator separately.",
            }
        )
        current_index += 1

        raw_derivative = (f_prime * g - f * g_prime) / g**2
        cleaned = _clean_derivative(raw_derivative)

        steps.append(
            {
                "index": current_index,
                "title": "Apply quotient rule",
                "expression": str(raw_derivative),
                "latex": _safe_latex(raw_derivative),
                "explanation": _rule_formula_explanation(rule_name),
            }
        )
        current_index += 1

        if cleaned != raw_derivative:
            steps.append(
                {
                    "index": current_index,
                    "title": "Simplify derivative",
                    "expression": str(cleaned),
                    "latex": _safe_latex(cleaned),
                    "explanation": "Simplify the expression obtained from the quotient rule.",
                }
            )
        final_expr = cleaned

    # Chain rule: f(g(x))
    elif rule_name == "Chain rule" and simplified_expr.is_Function and simplified_expr.args:
        inner = simplified_expr.args[0]
        outer = simplified_expr.func
        u = sp.Symbol("u")

        steps.append(
            {
                "index": current_index,
                "title": "Identify inner and outer functions",
                "expression": f"u(x) = {inner},    f(u) = {outer.__name__}(u)",
                "latex": "",
                "explanation": "View the expression as a composition f(u(x)) with inner function u(x) and outer function f.",
            }
        )
        current_index += 1

        du_dx = sp.diff(inner, x)
        f_prime_u = sp.diff(outer(u), u)

        steps.append(
            {
                "index": current_index,
                "title": "Differentiate inner and outer functions",
                "expression": f"du/dx = {du_dx},    f'(u) = {f_prime_u}",
                "latex": "",
                "explanation": "Differentiate u(x) with respect to x and f(u) with respect to u.",
            }
        )
        current_index += 1

        raw_derivative = f_prime_u.subs(u, inner) * du_dx
        cleaned = _clean_derivative(raw_derivative)

        steps.append(
            {
                "index": current_index,
                "title": "Apply chain rule",
                "expression": str(raw_derivative),
                "latex": _safe_latex(raw_derivative),
                "explanation": _rule_formula_explanation(rule_name),
            }
        )
        current_index += 1

        if cleaned != raw_derivative:
            steps.append(
                {
                    "index": current_index,
                    "title": "Simplify derivative",
                    "expression": str(cleaned),
                    "latex": _safe_latex(cleaned),
                    "explanation": "Simplify the expression obtained from the chain rule.",
                }
            )
        final_expr = cleaned

    # Generic differentiation path (sum, power, general)
    else:
        raw_derivative = sp.diff(expr, x)
        cleaned = _clean_derivative(raw_derivative)

        steps.append(
            {
                "index": current_index,
                "title": f"Differentiate expression",
                "expression": str(raw_derivative),
                "latex": _safe_latex(raw_derivative),
                "explanation": _rule_formula_explanation(rule_name),
            }
        )
        current_index += 1

        if cleaned != raw_derivative:
            steps.append(
                {
                    "index": current_index,
                    "title": "Simplify derivative",
                    "expression": str(cleaned),
                    "latex": _safe_latex(cleaned),
                    "explanation": "Simplify the derivative to obtain a cleaner final expression.",
                }
            )
        final_expr = cleaned

    if mode == "concise":
        # In concise mode, keep only the first and last steps.
        if len(steps) > 2:
            steps = [steps[0], steps[-1]]

    return {
        "type": "differentiation",
        "input": original_input,
        "cleaned_expression": cleaned_expr_str,
        "variable": variable,
        "rule": rule_name,
        "steps": steps,
        "final_answer": str(final_expr),
    }


def simplify_expression(expr_str: str, variable: str = "x") -> Dict[str, Any]:
    """
    Simplify an expression symbolically.
    """
    expr = _parse_expression(expr_str, variable)
    simplified = sp.simplify(expr)
    expanded = sp.expand(simplified)

    steps: List[Dict[str, Any]] = [
        {
            "index": 1,
            "title": "Interpret expression",
            "expression": str(expr),
            "latex": _safe_latex(expr),
            "explanation": "Treat the input as a symbolic expression in the given variable.",
        },
        {
            "index": 2,
            "title": "Simplify expression",
            "expression": str(expanded),
            "latex": _safe_latex(expanded),
            "explanation": "Use SymPy to algebraically simplify and expand the expression.",
        },
    ]

    return {
        "type": "simplify",
        "input": expr_str,
        "variable": variable,
        "steps": steps,
        "final_answer": str(expanded),
    }


def solve_equation(equation_str: str, variable: str = "x") -> Dict[str, Any]:
    """
    Solve a single-variable equation and return a structured explanation.

    equation_str can be of the form:
      - 'x^2 - 5*x + 6 = 0'
      - 'x^2 - 5*x + 6'  (implicitly '= 0')
    """
    x = sp.symbols(variable)

    # Split into left and right sides if an equals sign is present
    if "=" in equation_str:
        left_str, right_str = equation_str.split("=", 1)
        left = _parse_expression(left_str, variable)
        right = _parse_expression(right_str, variable)
        eq = sp.Eq(left, right)
    else:
        left = _parse_expression(equation_str, variable)
        eq = sp.Eq(left, 0)

    steps: List[Step] = []

    steps.append(
        Step(
            description="Interpret the problem as an equation to be solved for the given variable.",
            expression=str(eq),
            rule="Equation setup",
        )
    )

    # Bring everything to one side: f(x) = 0
    poly_form = sp.simplify(eq.lhs - eq.rhs)
    steps.append(
        Step(
            description="Rearrange the equation so that all terms are on one side and the other side is zero.",
            expression=f"{poly_form} = 0",
            rule="Rearrangement",
        )
    )

    # Solve the equation
    solutions = sp.solve(sp.Eq(poly_form, 0), x)

    if not solutions:
        steps.append(
            Step(
                description="No solutions were found for this equation.",
                expression=str(sp.Eq(poly_form, 0)),
                rule="Solving",
            )
        )
    else:
        steps.append(
            Step(
                description="Solve the simplified equation for the variable.",
                expression=", ".join(str(s) for s in solutions),
                rule="Solving",
            )
        )

    return {
        "type": "equation_solving",
        "input": equation_str,
        "variable": variable,
        "steps": [step.to_dict() for step in steps],
        "solutions": [str(s) for s in solutions],
    }


def integrate_expression(expr_str: str, variable: str = "x") -> Dict[str, Any]:
    """
    Integrate an expression with respect to the given variable.
    """
    x = sp.symbols(variable)
    expr = _parse_expression(expr_str, variable)
    integral = sp.integrate(expr, x)

    steps: List[Dict[str, Any]] = [
        {
            "index": 1,
            "title": "Interpret integrand",
            "expression": str(expr),
            "latex": _safe_latex(expr),
            "explanation": "Treat the input as a function to be integrated with respect to the given variable.",
        },
        {
            "index": 2,
            "title": "Compute antiderivative",
            "expression": str(integral),
            "latex": _safe_latex(integral),
            "explanation": "Use symbolic integration rules to find an antiderivative.",
        },
    ]

    # Represent the arbitrary constant of integration symbolically
    C = sp.Symbol("C")
    final_expr = integral + C

    steps.append(
        {
            "index": 3,
            "title": "Add constant of integration",
            "expression": str(final_expr),
            "latex": _safe_latex(final_expr),
            "explanation": "Attach the constant of integration C to represent the family of antiderivatives.",
        }
    )

    return {
        "type": "integration",
        "input": expr_str,
        "variable": variable,
        "steps": steps,
        "final_answer": str(final_expr),
    }


def evaluate_limit(expr_str: str, variable: str = "x") -> Dict[str, Any]:
    """
    Evaluate a limit. If the input parses as a SymPy Limit object, evaluate it.
    Otherwise, attempt limit as x -> 0.
    """
    expr = _parse_expression(expr_str, variable)

    x = sp.symbols(variable)

    # If user wrote something like Limit(f(x), x, a)
    if isinstance(expr, sp.Limit):
        limit_value = expr.doit()
        point = expr.args[1]
    else:
        # Fallback: interpret as limit of expr as x -> 0
        point = sp.Integer(0)
        limit_value = sp.limit(expr, x, point)

    steps: List[Dict[str, Any]] = [
        {
            "index": 1,
            "title": "Interpret limit expression",
            "expression": str(expr),
            "latex": _safe_latex(expr),
            "explanation": "View the input as a limit expression or as a function whose limit we study.",
        },
        {
            "index": 2,
            "title": "Evaluate limit",
            "expression": str(limit_value),
            "latex": _safe_latex(limit_value),
            "explanation": f"Evaluate the limit as {variable} approaches {point}.",
        },
    ]

    return {
        "type": "limit",
        "input": expr_str,
        "variable": variable,
        "steps": steps,
        "final_answer": str(limit_value),
    }


def factor_polynomial(expr_str: str, variable: str = "x") -> Dict[str, Any]:
    """
    Factor a polynomial in the given variable and report its degree.
    """
    x = sp.symbols(variable)
    expr = _parse_expression(expr_str, variable)
    poly = sp.Poly(expr, x)
    factored = sp.factor(poly.as_expr())

    degree = poly.degree()

    steps: List[Dict[str, Any]] = [
        {
            "index": 1,
            "title": "Interpret polynomial",
            "expression": str(expr),
            "latex": _safe_latex(expr),
            "explanation": f"Treat the input as a polynomial in {variable}.",
        },
        {
            "index": 2,
            "title": "Determine degree",
            "expression": f"degree = {degree}",
            "latex": "",
            "explanation": "Find the highest power of the variable appearing in the polynomial.",
        },
        {
            "index": 3,
            "title": "Factor polynomial",
            "expression": str(factored),
            "latex": _safe_latex(factored),
            "explanation": "Factor the polynomial into irreducible factors over the rationals.",
        },
    ]

    return {
        "type": "factor",
        "input": expr_str,
        "variable": variable,
        "degree": degree,
        "steps": steps,
        "final_answer": str(factored),
    }


def taylor_series(expr_str: str, variable: str = "x", point: Any = 0, order: int = 4) -> Dict[str, Any]:
    """
    Compute a Taylor series expansion of the expression around a point up to
    the given order (inclusive).
    """
    x = sp.symbols(variable)
    expr = _parse_expression(expr_str, variable)
    series = sp.series(expr, x, point, order + 1)  # SymPy includes higher order term
    truncated = sp.series(expr, x, point, order + 1).removeO()

    steps: List[Dict[str, Any]] = [
        {
            "index": 1,
            "title": "Interpret function",
            "expression": str(expr),
            "latex": _safe_latex(expr),
            "explanation": "Treat the input as a function to be approximated near a point.",
        },
        {
            "index": 2,
            "title": "Compute Taylor series",
            "expression": str(series),
            "latex": _safe_latex(series),
            "explanation": f"Compute the Taylor series of the function around {point} up to order {order}.",
        },
        {
            "index": 3,
            "title": "Truncate higher-order terms",
            "expression": str(truncated),
            "latex": _safe_latex(truncated),
            "explanation": "Drop the big-O term to obtain a polynomial approximation.",
        },
    ]

    return {
        "type": "taylor",
        "input": expr_str,
        "variable": variable,
        "point": str(point),
        "order": order,
        "steps": steps,
        "final_answer": str(truncated),
    }


def matrix_operations(expr_str: str) -> Dict[str, Any]:
    """
    Compute basic properties of a matrix: determinant, inverse (if it exists),
    and eigenvalues.
    """
    mat = _parse_expression(expr_str, "x")
    if not isinstance(mat, (sp.MatrixBase, sp.Matrix)):
        raise ValueError("Input is not a valid Matrix expression.")

    det = mat.det()
    steps: List[Dict[str, Any]] = [
        {
            "index": 1,
            "title": "Interpret matrix",
            "expression": str(mat),
            "latex": _safe_latex(mat),
            "explanation": "Treat the input as a square matrix.",
        },
        {
            "index": 2,
            "title": "Compute determinant",
            "expression": str(det),
            "latex": _safe_latex(det),
            "explanation": "Use symbolic matrix operations to compute the determinant.",
        },
    ]

    inverse_str = None
    eigenvalues_str = None

    if det != 0:
        inv = mat.inv()
        steps.append(
            {
                "index": 3,
                "title": "Compute inverse",
                "expression": str(inv),
                "latex": _safe_latex(inv),
                "explanation": "Since the determinant is non-zero, the matrix is invertible.",
            }
        )
        inverse_str = str(inv)

        eigenvals = mat.eigenvals()
        steps.append(
            {
                "index": 4,
                "title": "Compute eigenvalues",
                "expression": str(eigenvals),
                "latex": _safe_latex(sp.Matrix(list(eigenvals.keys()))),
                "explanation": "Compute eigenvalues of the matrix symbolically.",
            }
        )
        eigenvalues_str = str(eigenvals)
    else:
        steps.append(
            {
                "index": 3,
                "title": "Check invertibility",
                "expression": "determinant = 0",
                "latex": "",
                "explanation": "A zero determinant indicates that the matrix is not invertible.",
            }
        )

    return {
        "type": "matrix",
        "input": expr_str,
        "steps": steps,
        "determinant": str(det),
        "inverse": inverse_str,
        "eigenvalues": eigenvalues_str,
    }


def classify_expression(raw_input: str, variable: str = "x") -> Dict[str, Any]:
    """
    Classify the type of mathematical problem suggested by the raw input and
    provide basic metadata such as polynomial degree, variable count, etc.
    """
    s = (raw_input or "").strip()
    lower = s.lower()

    meta: Dict[str, Any] = {}

    # Explicit textual hints take precedence
    if "d/d" in lower or "diff(" in lower or lower.startswith("derivative"):
        problem_type = "differentiate"
    elif "integrate" in lower or "∫" in s or "int(" in lower:
        problem_type = "integrate"
    elif "limit" in lower:
        problem_type = "limit"
    elif "matrix(" in lower:
        problem_type = "matrix"
    else:
        # Symbolic inspection
        try:
            expr = _parse_expression(s, variable)
        except Exception:
            # Fall back to simple heuristics based on '='
            if "=" in s:
                problem_type = "equation"
            else:
                problem_type = "simplify"
            return {
                "problem_type": problem_type,
                "meta": meta,
            }

        symbols = sorted(str(sym) for sym in expr.free_symbols)
        meta["variables"] = symbols
        meta["variable_count"] = len(symbols)

        # Piecewise detection
        meta["is_piecewise"] = bool(expr.has(sp.Piecewise))

        # Equation / system detection via '=' in text
        if "=" in s:
            equations = [part for part in s.split(";") if part.strip()]
            meta["equation_count"] = len(equations)
            if len(equations) > 1 or meta["variable_count"] > 1:
                problem_type = "system"
            else:
                problem_type = "equation"
        else:
            # Polynomial degree (single variable)
            try:
                x = sp.symbols(variable)
                poly = sp.Poly(expr, x)
                meta["polynomial_degree"] = poly.degree()
            except Exception:
                meta["polynomial_degree"] = None

            if meta["polynomial_degree"] is not None and meta["polynomial_degree"] > 1:
                problem_type = "factor_candidate"
            else:
                problem_type = "simplify"

        meta["has_implicit_diff_pattern"] = "dy/dx" in lower

    return {
        "problem_type": problem_type,
        "meta": meta,
    }

