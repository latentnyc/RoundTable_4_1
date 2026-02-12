
import { useEffect } from 'react';
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Login from "@/pages/Login";
import CampaignStart from "@/pages/CampaignStart";
import CreateCharacterPage from "@/pages/CreateCharacter";
import CampaignDash from "@/pages/CampaignDash";
import CampaignMain from "@/pages/CampaignMain";
import UsersPage from "@/pages/Users";
import AuthGuard from "@/components/AuthGuard";
import RootRedirector from "@/components/RootRedirector";
import LogViewer from "@/pages/LogViewer";
import { useAuthStore } from "@/store/authStore";

function App() {
  const initialize = useAuthStore(state => state.initialize);

  useEffect(() => {
    const unsubscribe = initialize();
    return () => unsubscribe();
  }, [initialize]);

  return (
    <BrowserRouter>
      <Routes>
        {/* Root Redirector */}
        <Route path="/" element={<RootRedirector />} />

        {/* Public / Auth */}
        <Route path="/login" element={<Login />} />

        {/* Protected Routes */}
        <Route path="/campaign_start" element={<AuthGuard><CampaignStart /></AuthGuard>} />
        <Route path="/campaign_dash/:id" element={<AuthGuard><CampaignDash /></AuthGuard>} />
        <Route path="/campaign_main/:id" element={<AuthGuard><CampaignMain /></AuthGuard>} />

        {/* Helper Routes */}
        <Route path="/create-character" element={<AuthGuard><CreateCharacterPage /></AuthGuard>} />
        <Route path="/users" element={<AuthGuard><UsersPage /></AuthGuard>} />
        <Route path="/logs" element={<AuthGuard><LogViewer /></AuthGuard>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
