import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { expect, it } from "vitest";

import { I18nProvider } from "../i18n";
import { AsoBand } from "./AsoBand";

it("renders ASO readiness and score", () => {
  render(
    <I18nProvider>
      <AsoBand
        readiness={{
          readiness_level: "ready",
          agent_ready: true,
          has_webmcp: true,
          has_action_schema: false,
          has_agent_forms: false,
          has_openapi: false,
          action_signals: 1,
          ai_discovery_endpoints: 1,
          has_nlweb: false,
          brand_coherence_score: null,
          blocked_agent_bots: [],
        }}
        score={82}
      />
    </I18nProvider>,
  );
  expect(screen.getByText(/82/)).toBeInTheDocument();
});

it("renders the absent webMCP detail without a score", () => {
  render(<I18nProvider><AsoBand readiness={{ readiness_level: "partial", has_webmcp: false, ai_discovery_endpoints: 0 } as never} score={null} /></I18nProvider>);
  expect(screen.getByText(/webMCP|discovery/i)).toBeInTheDocument();
  expect(screen.queryByText(/score:/i)).not.toBeInTheDocument();
});
