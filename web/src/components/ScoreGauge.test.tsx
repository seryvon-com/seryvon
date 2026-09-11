import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { expect, it } from "vitest";

import { ScoreGauge } from "./ScoreGauge";

it("renders a clamped score with unit and custom size", () => {
  render(<ScoreGauge score={120} size={150} unit="/ 100" />);
  expect(screen.getByText("100")).toBeInTheDocument();
  expect(screen.getByText("/ 100")).toBeInTheDocument();
});

it("renders the prism gradient for the global score", () => {
  const { container } = render(<ScoreGauge score={-5} prism />);
  expect(screen.getByText("0")).toBeInTheDocument();
  expect(container.querySelector("linearGradient")).toBeInTheDocument();
});
