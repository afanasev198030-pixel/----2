import { Routes, Route } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import LandingPage from './pages/LandingPage';
import BrokerDashboard from './pages/BrokerDashboard';
import ClientsListPage from './pages/ClientsListPage';
import ClientDetailPage from './pages/ClientDetailPage';
import DeclarationsListPage from './pages/DeclarationsListPage';
import DeclarationEditPage from './pages/DeclarationEditPage';
import SettingsPage from './pages/SettingsPage';
import DeclarationViewPage from './pages/DeclarationViewPage';
import DtsViewPage from './pages/DtsViewPage';
import ProfilePage from './pages/ProfilePage';
import AdminUsersPage from './pages/AdminUsersPage';
import AdminUserEditPage from './pages/AdminUserEditPage';
import AdminAuditPage from './pages/AdminAuditPage';
import AdminKnowledgePage from './pages/AdminKnowledgePage';
import AdminChecklistPage from './pages/AdminChecklistPage';
import AdminDashboardPage from './pages/AdminDashboardPage';
import AdminStrategiesPage from './pages/AdminStrategiesPage';
import AdminAiCostsPage from './pages/AdminAiCostsPage';
import AdminParseDebugPage from './pages/AdminParseDebugPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<BrokerDashboard />} />
        <Route path="/clients" element={<ClientsListPage />} />
        <Route path="/clients/:id" element={<ClientDetailPage />} />
        <Route path="/declarations" element={<DeclarationsListPage />} />
        <Route path="/declarations/:id/edit" element={<DeclarationEditPage />} />
        <Route path="/declarations/:id/view" element={<DeclarationViewPage />} />
        <Route path="/declarations/:id/dts-view" element={<DtsViewPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/admin/users/:id" element={<AdminUserEditPage />} />
        <Route path="/admin/audit" element={<AdminAuditPage />} />
        <Route path="/admin/knowledge" element={<AdminKnowledgePage />} />
        <Route path="/admin/checklists" element={<AdminChecklistPage />} />
        <Route path="/admin/strategies" element={<AdminStrategiesPage />} />
        <Route path="/admin/ai-costs" element={<AdminAiCostsPage />} />
        <Route path="/admin/parse-debug" element={<AdminParseDebugPage />} />
      </Route>
    </Routes>
  );
}

export default App;
