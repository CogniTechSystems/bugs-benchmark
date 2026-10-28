import { NavLink, Outlet } from "react-router-dom";

const BENCHMARK_LINKS = [
  { to: "/chat", label: "Chat" },
  { to: "/bug-hunts", label: "Bug hunts" },
  { to: "/leaderboard", label: "Leaderboard" },
];

const ADMIN_LINKS = [
  { to: "/admin/models", label: "Models" },
  { to: "/admin/runtimes", label: "Runtimes" },
  { to: "/admin/deployments", label: "Deployments" },
];

function NavigationGroup({ title, links }: { title: string; links: typeof BENCHMARK_LINKS }) {
  return (
    <div className="nav-group">
      <span className="nav-title">{title}</span>
      {links.map((link) => (
        <NavLink key={link.to} to={link.to} className="nav-link">
          {link.label}
        </NavLink>
      ))}
    </div>
  );
}

export function Layout() {
  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="brand">
          <img src="/favicon.svg" alt="" width="28" height="28" />
          <span>Bug Hunt Benchmark</span>
        </div>
        <NavigationGroup title="Benchmark" links={BENCHMARK_LINKS} />
        <NavigationGroup title="Administration" links={ADMIN_LINKS} />
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
