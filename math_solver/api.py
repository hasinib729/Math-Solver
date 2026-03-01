from pathlib import Path
import logging
import time
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine import (
    classify_expression,
    differentiate,
    evaluate_limit,
    factor_polynomial,
    integrate_expression,
    matrix_operations,
    simplify_expression,
    solve_equation,
)


class DiffRequest(BaseModel):
    expression: str
    variable: str = "x"


class EquationRequest(BaseModel):
    equation: str
    variable: str = "x"


class SolveRequest(BaseModel):
    """
    Generic request for problem-type auto-detection.
    """
    input: str
    variable: str = "x"
    mode: str = "detailed"


logger = logging.getLogger("math_solver.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Math Solver API", version="1.0.0")
_start_time = time.time()


def _error_payload(err_type: str, message: str, details: Any = None) -> Dict[str, Any]:
    """
    Build a structured error payload matching the expected schema.
    """
    return {
        "error": {
            "type": err_type,
            "message": message,
            "details": details,
        }
    }


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """
    Redirect root to the web app.
    """
    return RedirectResponse(url="/app/")


@app.get("/health")
def health() -> Dict[str, Any]:
    """
    Simple health-check endpoint suitable for monitoring.
    """
    return {"status": "ok", "version": "1.0.0"}


@app.post("/differentiate")
def api_differentiate(payload: DiffRequest):
    """
    Differentiate an expression with respect to a variable.
    """
    start = time.perf_counter()
    logger.info("Incoming differentiate request: expr=%r, var=%s", payload.expression, payload.variable)
    try:
        result = differentiate(payload.expression, payload.variable)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_error_payload("BadRequest", str(exc), {"input": payload.expression}),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error during differentiation")
        raise HTTPException(
            status_code=500,
            detail=_error_payload(
                "InternalError",
                "Unexpected error during differentiation.",
                {"input": payload.expression},
            ),
        ) from exc

    elapsed_ms = (time.perf_counter() - start) * 1000
    exec_ms = round(elapsed_ms, 3)
    logger.info("Differentiation completed in %.3f ms", exec_ms)
    result["_meta"] = {"elapsed_ms": exec_ms, "endpoint": "/differentiate"}
    result["execution_time_ms"] = exec_ms
    return result


@app.post("/solve-equation")
def api_solve_equation(payload: EquationRequest):
    """
    Solve a single-variable equation.
    """
    start = time.perf_counter()
    logger.info("Incoming equation solve request: eq=%r, var=%s", payload.equation, payload.variable)
    try:
        result = solve_equation(payload.equation, payload.variable)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_error_payload("BadRequest", str(exc), {"input": payload.equation}),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error during equation solving")
        raise HTTPException(
            status_code=500,
            detail=_error_payload(
                "InternalError",
                "Unexpected error during equation solving.",
                {"input": payload.equation},
            ),
        ) from exc

    elapsed_ms = (time.perf_counter() - start) * 1000
    exec_ms = round(elapsed_ms, 3)
    logger.info("Equation solving completed in %.3f ms", exec_ms)
    result["_meta"] = {"elapsed_ms": exec_ms, "endpoint": "/solve-equation"}
    result["execution_time_ms"] = exec_ms
    return result


@app.post("/solve")
def api_solve(payload: SolveRequest):
    """
    Auto-detect problem type and route to the appropriate solver.
    """
    start = time.perf_counter()
    logger.info("Incoming solve request: input=%r, var=%s", payload.input, payload.variable)
    try:
        classification = classify_expression(payload.input, payload.variable)
        problem_type = classification["problem_type"]
        meta = classification.get("meta", {})

        logger.info(
            "Detected problem type: %s (meta=%s)",
            problem_type,
            meta,
        )

        if problem_type == "differentiate":
            result = differentiate(payload.input, payload.variable, mode=payload.mode)
        elif problem_type in ("equation", "system"):
            # For now, treat both as single-equation solving; systems can be added later.
            result = solve_equation(payload.input, payload.variable)
        elif problem_type == "integrate":
            result = integrate_expression(payload.input, payload.variable)
        elif problem_type == "limit":
            result = evaluate_limit(payload.input, payload.variable)
        elif problem_type == "matrix":
            result = matrix_operations(payload.input)
        elif problem_type == "factor_candidate":
            result = factor_polynomial(payload.input, payload.variable)
        else:
            result = simplify_expression(payload.input, payload.variable)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_error_payload("BadRequest", str(exc), {"input": payload.input}),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error during generic solving")
        raise HTTPException(
            status_code=500,
            detail=_error_payload(
                "InternalError",
                "Unexpected error while solving the problem.",
                {"input": payload.input},
            ),
        ) from exc

    elapsed_ms = (time.perf_counter() - start) * 1000
    exec_ms = round(elapsed_ms, 3)
    logger.info("Solve completed: type=%s in %.3f ms", problem_type, exec_ms)

    result.setdefault("_meta", {})
    result["_meta"].update(
        {
            "elapsed_ms": exec_ms,
            "endpoint": "/solve",
            "problem_type": problem_type,
            "classification_meta": meta,
        }
    )
    result["execution_time_ms"] = exec_ms
    return result


web_dir = Path(__file__).parent / "web"
app.mount("/app", StaticFiles(directory=str(web_dir), html=True), name="app")
