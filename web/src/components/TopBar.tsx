// Seryvon — top bar. AGPL-3.0-or-later.

import { Link } from "react-router-dom";

export function TopBar() {
  return (
    <header className="topbar">
      <Link to="/">
        <h1>Seryvon</h1>
      </Link>
      <span className="tagline">Audit déterministe · SEO · GEO · GSO · AEO · ASO</span>
    </header>
  );
}
