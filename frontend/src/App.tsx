import { Toaster } from "react-hot-toast";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import Layout from "./components/Layout";

import Analytics from "./pages/Analytics";
import Brain from "./pages/Brain";
import Channels from "./pages/Channels";
import Create from "./pages/Create";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import OAuthCallback from "./pages/OAuthCallback";
import Publishing from "./pages/Publishing";
import Register from "./pages/Register";
import Research from "./pages/Research";
import Settings from "./pages/Settings";
import Videos from "./pages/Videos";

function App() {
  return (
    <AuthProvider>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: "#1e293b",
            color: "#f8fafc",
            border: "1px solid #334155",
          },
        }}
      />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/oauth/callback" element={<OAuthCallback />} />
        <Route
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/" element={<Dashboard />} />
          <Route path="/channels" element={<Channels />} />
          <Route path="/brain" element={<Brain />} />
          <Route path="/research" element={<Research />} />
          <Route path="/create" element={<Create />} />
          <Route path="/videos" element={<Videos />} />
          <Route path="/publishing" element={<Publishing />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;
