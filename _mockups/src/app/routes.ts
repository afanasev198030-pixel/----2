import { createBrowserRouter } from "react-router";
import { DashboardPage } from "./pages/DashboardPage";
import { DeclarationDashboardPage } from "./pages/DeclarationDashboardPage";
import { DTSPage } from "./pages/DTSPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: DashboardPage,
  },
  {
    path: "/dashboard/:id",
    Component: DeclarationDashboardPage,
  },
  {
    path: "/dts",
    Component: DTSPage,
  },
  {
    path: "/declaration",
    lazy: async () => {
      const { DeclarationPage } = await import("./components/declaration/DeclarationPage");
      return { Component: DeclarationPage };
    },
  },
]);