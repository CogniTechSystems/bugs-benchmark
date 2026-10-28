import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { Layout } from "./components/Layout";
import { BugHuntsPage } from "./pages/BugHuntsPage";
import { ChatPage } from "./pages/ChatPage";
import { DeploymentsPage } from "./pages/DeploymentsPage";
import { JobDetailPage } from "./pages/JobDetailPage";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import { ModelsPage } from "./pages/ModelsPage";
import { RuntimesPage } from "./pages/RuntimesPage";
import "./styles.css";

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/chat" replace /> },
      { path: "chat/:sessionId?", element: <ChatPage /> },
      { path: "bug-hunts", element: <BugHuntsPage /> },
      { path: "jobs/:jobId", element: <JobDetailPage /> },
      { path: "leaderboard", element: <LeaderboardPage /> },
      { path: "admin/models", element: <ModelsPage /> },
      { path: "admin/runtimes", element: <RuntimesPage /> },
      { path: "admin/deployments", element: <DeploymentsPage /> },
      { path: "*", element: <Navigate to="/chat" replace /> },
    ],
  },
]);

const root = document.getElementById("root");
if (!root) {
  throw new Error("Root element not found.");
}

createRoot(root).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
