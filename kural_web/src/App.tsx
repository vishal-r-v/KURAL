import React, { useState } from "react";
import Navbar from "./components/Navbar.tsx";
import Footer from "./components/Footer.tsx";
import HomeView from "./components/HomeView.tsx";
import FileComplaintView from "./components/FileComplaintView.tsx";
import TrackComplaintView from "./components/TrackComplaintView.tsx";
import DashboardView from "./components/DashboardView.tsx";
import HistoryView from "./components/HistoryView.tsx";
import AboutView from "./components/AboutView.tsx";
import { Complaint } from "./types.ts";

export default function App() {
  const [currentTab, setTab] = useState<string>("home");
  const [language, setLanguage] = useState<"English" | "Tamil">("English");
  const [searchId, setSearchId] = useState<string>("");

  // Kept as a no-op hook point in case future views want to react to a
  // freshly-submitted complaint without an extra fetch; the source of truth
  // for all complaint data is always the live KURAL backend (see src/lib/api.ts).
  const handleNewComplaint = (_newComp: Complaint) => {};
  const handleStatusUpdated = (_updatedComp: Complaint) => {};

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans selection:bg-[#00274c]/10 selection:text-[#00274c]" id="app-root">
      
      {/* Top Fixed Header Navigation */}
      <Navbar 
        currentTab={currentTab} 
        setTab={setTab} 
        language={language} 
        setLanguage={setLanguage} 
      />

      {/* Main Content Area */}
      <main className="flex-1 w-full pt-[104px] pb-16 px-4 sm:px-6 md:px-8 max-w-7xl mx-auto flex flex-col gap-6" id="main-content">
        
        {currentTab === "home" && (
          <HomeView 
            language={language} 
            onFileComplaintClick={() => setTab("file")} 
            onTrackClick={() => setTab("track")} 
          />
        )}

        {currentTab === "file" && (
          <FileComplaintView 
            language={language} 
            onComplaintSubmitted={handleNewComplaint} 
            setTab={setTab} 
            setSearchId={setSearchId} 
          />
        )}

        {currentTab === "track" && (
          <TrackComplaintView 
            language={language} 
            searchId={searchId} 
            setSearchId={setSearchId} 
            allComplaints={[]} 
            onStatusUpdated={handleStatusUpdated} 
          />
        )}

        {currentTab === "dashboard" && (
          <DashboardView 
            language={language} 
            setTab={setTab} 
            setSearchId={setSearchId} 
          />
        )}

        {currentTab === "history" && (
          <HistoryView
            language={language}
            setTab={setTab}
            setSearchId={setSearchId}
          />
        )}

        {currentTab === "about" && (
          <AboutView language={language} />
        )}

      </main>

      {/* Footer Helplines & Links */}
      <Footer language={language} />

    </div>
  );
}
