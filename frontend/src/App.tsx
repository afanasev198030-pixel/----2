import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import BrokerDashboard from './pages/BrokerDashboard';
import ClientsListPage from './pages/ClientsListPage';
import ClientDetailPage from './pages/ClientDetailPage';
import DeclarationsListPage from './pages/DeclarationsListPage';
import DeclarationEditPage from './pages/DeclarationEditPage';
import SettingsPage from './pages/SettingsPage';
import DeclarationViewPage from './pages/DeclarationViewPage';
import ProfilePage from './pages/ProfilePage';
import AdminUsersPage from './pages/AdminUsersPage';
import AdminUserEditPage from './pages/AdminUserEditPage';
import AdminAuditPage from './pages/AdminAuditPage';

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<BrokerDashboard />} />
        <Route path="/clients" element={<ClientsListPage />} />
        <Route path="/clients/:id" element={<ClientDetailPage />} />
        <Route path="/declarations" element={<DeclarationsListPage />} />
        <Route path="/declarations/:id/edit" element={<DeclarationEditPage />} />
        <Route path="/declarations/:id/view" element={<DeclarationViewPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
        <Route path="/admin/users/:id" element={<AdminUserEditPage />} />
        <Route path="/admin/audit" element={<AdminAuditPage />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
