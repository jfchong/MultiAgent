import { Routes, Route } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";
import OverviewPage from "@/pages/OverviewPage";
import RequestsPage from "@/pages/RequestsPage";
import TasksPage from "@/pages/TasksPage";
import TaskDetailPage from "@/pages/TaskDetailPage";
import AgentsPage from "@/pages/AgentsPage";
import AgentDetailPage from "@/pages/AgentDetailPage";
import ReleasesPage from "@/pages/ReleasesPage";
import SkillsPage from "@/pages/SkillsPage";
import SkillDetailPage from "@/pages/SkillDetailPage";
import SessionsPage from "@/pages/SessionsPage";
import SessionDetailPage from "@/pages/SessionDetailPage";

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-foreground mb-2">{title}</h1>
        <p className="text-muted-foreground">Coming soon</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<OverviewPage />} />
        <Route path="requests" element={<RequestsPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="tasks/:id" element={<TaskDetailPage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="agents/:id" element={<AgentDetailPage />} />
        <Route path="releases" element={<ReleasesPage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="skills/:id" element={<SkillDetailPage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="sessions/:id" element={<SessionDetailPage />} />
        <Route path="improvements" element={<PlaceholderPage title="Improvements" />} />
        <Route path="settings" element={<PlaceholderPage title="Settings" />} />
      </Route>
    </Routes>
  );
}
