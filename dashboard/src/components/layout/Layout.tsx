import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { ScrollArea } from "@/components/ui/scroll-area";

export function Layout() {
  return (
    <div className="dark min-h-screen bg-background">
      <Sidebar />
      <main className="ml-60">
        <ScrollArea className="h-screen">
          <div className="p-6">
            <Outlet />
          </div>
        </ScrollArea>
      </main>
    </div>
  );
}
