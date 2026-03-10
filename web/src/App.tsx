import { Route, Routes } from "react-router";
import { UploadPage } from "./pages/UploadPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadPage />} />
    </Routes>
  );
}
