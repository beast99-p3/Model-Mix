import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DebateMode } from "./pages/DebateMode";
import { Home } from "./pages/Home";
import { ResumeMode } from "./pages/ResumeMode";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/chat" element={<Navigate to="/debate" replace />} />
        <Route path="/debate" element={<DebateMode />} />
        <Route path="/resume" element={<ResumeMode />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
