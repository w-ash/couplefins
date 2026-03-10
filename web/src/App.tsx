import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Route, Routes } from "react-router";
import { ThemeToggle } from "./components/ThemeToggle";
import { SetupPage } from "./pages/SetupPage";
import { UploadPage } from "./pages/UploadPage";

interface Person {
  id: string;
  name: string;
}

async function fetchPersons(): Promise<Person[]> {
  const res = await fetch("/api/v1/persons/");
  if (!res.ok) throw new Error("Failed to fetch persons");
  return res.json();
}

export function App() {
  const { data: persons, isLoading } = useQuery({
    queryKey: ["persons"],
    queryFn: fetchPersons,
  });

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const needsSetup = !persons || persons.length < 2;

  if (needsSetup) {
    return <SetupPage />;
  }

  return (
    <>
      <div className="fixed top-4 right-4 z-50">
        <ThemeToggle />
      </div>
      <Routes>
        <Route path="/" element={<UploadPage />} />
      </Routes>
    </>
  );
}
