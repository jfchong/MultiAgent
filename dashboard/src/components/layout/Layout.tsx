import { Outlet } from "react-router-dom";
export function Layout() {
  return <div className="dark min-h-screen bg-background"><Outlet /></div>;
}
