const mode = {
  DIFFERENTIATE: "differentiate",
  SOLVE_EQUATION: "solve-equation",
};

let currentMode = mode.DIFFERENTIATE;

const form = document.getElementById("solver-form");
const expressionInput = document.getElementById("expression-input");
const variableInput = document.getElementById("variable-input");
const submitButton = document.getElementById("submit-button");
const resultsContainer = document.getElementById("results");
const statusEl = document.getElementById("status");
const resultsCard = document.getElementById("results-card");
const expressionLabel = document.getElementById("expression-label");

const tabButtons = document.querySelectorAll(".tab-button");
const exampleChips = document.querySelectorAll(".example-chip");

function setMode(newMode) {
  currentMode = newMode;

  tabButtons.forEach((btn) => {
    if (btn.dataset.mode === newMode) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  if (newMode === mode.DIFFERENTIATE) {
    expressionLabel.textContent = "Expression";
    expressionInput.placeholder = "Example (differentiate): x^3*sin(x)";
    submitButton.textContent = "Differentiate step by step";
  } else {
    expressionLabel.textContent = "Equation";
    expressionInput.placeholder = "Example (solve): x^2 - 5*x + 6 = 0";
    submitButton.textContent = "Solve equation step by step";
  }
}

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const newMode = btn.dataset.mode;
    setMode(newMode);
    resultsContainer.innerHTML = "";
    resultsContainer.classList.add("hidden");
    statusEl.textContent = "Enter an expression and hit “Solve step by step”.";
    statusEl.className = "status status-muted";
  });
});

exampleChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    const example = chip.dataset.example;
    const chipMode = chip.dataset.mode;
    if (chipMode) {
      setMode(chipMode);
    }
    expressionInput.value = example;
  });
});

async function callApi() {
  const expr = expressionInput.value.trim();
  const variable = variableInput.value.trim() || "x";

  if (!expr) {
    statusEl.textContent = "Please enter an expression or equation.";
    statusEl.className = "status status-error";
    return;
  }

  const endpoint =
    currentMode === mode.DIFFERENTIATE ? "/differentiate" : "/solve-equation";

  const payload =
    currentMode === mode.DIFFERENTIATE
      ? { expression: expr, variable }
      : { equation: expr, variable };

  submitButton.disabled = true;
  statusEl.textContent = "Solving…";
  statusEl.className = "status status-loading";
  resultsContainer.classList.add("hidden");
  resultsContainer.innerHTML = "";

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || "Request failed");
    }

    const data = await response.json();
    renderResults(data);
  } catch (error) {
    console.error(error);
    statusEl.textContent =
      "Something went wrong while solving the problem. Please check your input.";
    statusEl.className = "status status-error";
  } finally {
    submitButton.disabled = false;
  }
}

function renderResults(data) {
  const { steps = [] } = data;

  if (!steps.length) {
    statusEl.textContent = "No detailed steps were returned for this problem.";
    statusEl.className = "status status-muted";
    resultsContainer.classList.add("hidden");
    return;
  }

  resultsContainer.classList.remove("hidden");
  statusEl.textContent = "Here is a step-by-step breakdown.";
  statusEl.className = "status status-muted";

  steps.forEach((step, index) => {
    const stepEl = document.createElement("div");
    stepEl.className = "step";

    const header = document.createElement("div");
    header.className = "step-header";

    const title = document.createElement("div");
    title.className = "step-title";
    title.textContent = `Step ${index + 1}`;

    const rule = document.createElement("div");
    rule.className = "step-rule";
    rule.textContent = step.rule || "Step";

    header.appendChild(title);
    header.appendChild(rule);

    const desc = document.createElement("div");
    desc.className = "step-description";
    desc.textContent = step.description || "";

    const expr = document.createElement("div");
    expr.className = "step-expression";
    expr.textContent = step.expression || "";

    stepEl.appendChild(header);
    stepEl.appendChild(desc);
    stepEl.appendChild(expr);

    resultsContainer.appendChild(stepEl);
  });

  const final = document.createElement("div");
  final.className = "final-answer";

  const label = document.createElement("span");
  label.className = "final-answer-label";

  const value = document.createElement("span");
  value.className = "final-answer-text";

  if (data.type === "differentiation") {
    label.textContent = "Derivative:";
    value.textContent = data.result || "";
  } else if (data.type === "equation_solving") {
    label.textContent = "Solutions:";
    const sols = data.solutions || [];
    value.textContent = sols.length ? sols.join(", ") : "No solutions found";
  } else {
    label.textContent = "Result:";
    value.textContent = JSON.stringify(data);
  }

  final.appendChild(label);
  final.appendChild(value);
  resultsContainer.appendChild(final);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  callApi();
});

setMode(mode.DIFFERENTIATE);

