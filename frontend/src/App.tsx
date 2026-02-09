import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DeclarationsListPage from './pages/DeclarationsListPage';
import DeclarationEditPage from './pages/DeclarationEditPage';
import SettingsPage from './pages/SettingsPage';
import DeclarationViewPage from './pages/DeclarationViewPage';

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/declarations" element={<DeclarationsListPage />} />
        <Route path="/declarations/:id/edit" element={<DeclarationEditPage />} />
        <Route path="/declarations/:id/view" element={<DeclarationViewPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/" element={<Navigate to="/declarations" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
