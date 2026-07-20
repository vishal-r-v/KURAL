import React from "react";
import { Mic, ArrowRight, Brain, ShieldAlert, CheckCircle, ArrowRightLeft, Radio, Route, CircleDot } from "lucide-react";
import Ticker from "./Ticker.tsx";
import StatsGrid from "./StatsGrid.tsx";
import { useBackendHealth } from "../lib/useBackendHealth.ts";

interface HomeViewProps {
  language: "English" | "Tamil";
  onFileComplaintClick: () => void;
  onTrackClick: () => void;
}

export default function HomeView({ language, onFileComplaintClick, onTrackClick }: HomeViewProps) {
  const backendStatus = useBackendHealth();

  return (
    <div className="flex flex-col gap-10 animate-fadeIn" id="home-view">
      
      {/* Hero Section */}
      <section className="w-full flex flex-col lg:flex-row items-center justify-between gap-12 py-8">
        
        {/* Hero Left Content */}
        <div className="flex-1 flex flex-col items-start gap-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-[#00274c] p-2 flex items-center justify-center text-white shadow-md">
              <Mic className="w-6 h-6" />
            </div>
            <h1 className="text-3xl font-extrabold text-[#00274c] tracking-tight">KURAL</h1>
            <span
              id="backend-status-badge"
              className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full border ${
                backendStatus === "online"
                  ? "bg-green-50 text-green-700 border-green-200"
                  : backendStatus === "offline"
                  ? "bg-red-50 text-red-700 border-red-200"
                  : "bg-gray-50 text-gray-500 border-gray-200"
              }`}
              title={
                backendStatus === "online"
                  ? "Connected to the KURAL backend"
                  : backendStatus === "offline"
                  ? "Cannot reach the KURAL backend"
                  : "Checking backend connection…"
              }
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  backendStatus === "online"
                    ? "bg-green-600 animate-pulse"
                    : backendStatus === "offline"
                    ? "bg-red-600"
                    : "bg-gray-400 animate-pulse"
                }`}
              ></span>
              {backendStatus === "online"
                ? (language === "English" ? "Backend Online" : "இணைப்பு உள்ளது")
                : backendStatus === "offline"
                ? (language === "English" ? "Backend Offline" : "இணைப்பு இல்லை")
                : (language === "English" ? "Connecting…" : "இணைக்கிறது…")}
            </span>
          </div>

          <div className="space-y-4">
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-extrabold text-gray-900 leading-tight">
              {language === "English" ? "Your voice, tracked until resolved" : "உங்கள் குரல், தீர்வு காணும் வரை பின்தொடரப்படும்"}
            </h2>
            <p className="text-lg text-gray-500 max-w-xl">
              {language === "English" 
                ? "Chennai's intelligent civic grievance platform. Simply record or type your complaint, let our AI handle routing to the proper ward department, and watch progress live."
                : "சென்னையின் அதிநவீன மக்கள் குறைதீர்ப்பு தளம். உங்கள் குறைகளை குரல் பதிவாகவோ அல்லது தட்டச்சு செய்தோ சமர்ப்பிக்கலாம். எமது AI அதை தகுந்த துறைக்கு அனுப்பி தீர்வு காணும்."}
            </p>
          </div>

          <div className="pt-4 flex flex-wrap gap-4">
            <button
              onClick={onFileComplaintClick}
              className="bg-[#00274c] text-white font-semibold px-8 py-4 rounded-full hover:bg-[#0b3d6e] hover:shadow-lg transition-all flex items-center gap-2.5 group cursor-pointer"
              id="hero-file-btn"
            >
              <Mic className="w-5 h-5 group-hover:scale-110 transition-transform text-[#feae2c]" />
              {language === "English" ? "File a Complaint / புகார் அளிக்கவும்" : "புகார் அளிக்கவும் / File Complaint"}
            </button>
            <button
              onClick={onTrackClick}
              className="bg-white text-[#00274c] border border-gray-300 font-semibold px-8 py-4 rounded-full hover:bg-gray-50 transition-all flex items-center gap-2 cursor-pointer"
              id="hero-track-btn"
            >
              {language === "English" ? "Track Complaint" : "புகாரை பின்தொடர"}
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Hero Right Visuals (Status Simulator Card) */}
        <div className="flex-1 w-full max-w-md">
          <div className="aspect-square bg-white rounded-3xl p-8 relative overflow-hidden border border-gray-100 shadow-xl shadow-gray-100 flex flex-col justify-center gap-6">
            <div className="absolute top-0 right-0 bg-[#feae2c]/10 text-[#6b4500] px-4 py-1.5 rounded-bl-2xl text-xs font-bold flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#feae2c] animate-pulse"></span>
              Chennai Smart City
            </div>
            
            <div className="absolute inset-0 bg-gradient-to-br from-[#00274c]/3 to-transparent pointer-events-none"></div>
            
            {/* Step A Indicator */}
            <div className="bg-white rounded-2xl p-4.5 shadow-md border border-gray-50 transform -rotate-2 hover:rotate-0 transition-transform duration-300">
              <div className="flex items-center gap-3">
                <CircleDot className="w-6 h-6 text-[#feae2c]" />
                <div>
                  <div className="text-xs text-gray-400 font-bold uppercase tracking-wider">Step 1: Input</div>
                  <span className="font-semibold text-sm text-gray-800">Voice recorded: Pothole on Mount Road</span>
                </div>
              </div>
            </div>

            {/* Step B Indicator */}
            <div className="bg-white rounded-2xl p-4.5 shadow-md border border-gray-50 transform translate-x-4">
              <div className="flex items-center gap-3">
                <Route className="w-6 h-6 text-[#00274c]" />
                <div>
                  <div className="text-xs text-gray-400 font-bold uppercase tracking-wider">Step 2: AI Routing</div>
                  <span className="font-semibold text-sm text-gray-800">Routed to GCC Ward 112</span>
                </div>
              </div>
            </div>

            {/* Step C Indicator */}
            <div className="bg-white rounded-2xl p-4.5 shadow-md border border-gray-50 transform rotate-1 hover:rotate-0 transition-transform duration-300">
              <div className="flex items-center gap-3">
                <CheckCircle className="w-6 h-6 text-green-600" />
                <div>
                  <div className="text-xs text-gray-400 font-bold uppercase tracking-wider">Step 3: Resolve</div>
                  <span className="font-semibold text-sm text-gray-800">Resolved within 48hrs</span>
                </div>
              </div>
            </div>

          </div>
        </div>

      </section>

      {/* Live Scrolling Ticker */}
      <Ticker />

      {/* Trust Stats indicators bento grid */}
      <StatsGrid language={language} />

      {/* How it Works Diagram */}
      <section className="w-full py-10 flex flex-col items-center gap-12" id="how-it-works">
        <h2 className="text-2xl sm:text-3xl font-extrabold text-[#00274c] text-center">
          {language === "English" ? "How KURAL Works" : "குரல் எவ்வாறு செயல்படுகிறது?"}
        </h2>
        
        <div className="flex flex-col md:flex-row items-center justify-center w-full max-w-4xl gap-8 relative">
          
          {/* Connector Line (Desktop) */}
          <div className="hidden md:block absolute top-12 left-[15%] right-[15%] h-[2px] bg-gray-200 z-0"></div>
          
          {/* Step 1 */}
          <div className="flex flex-col items-center gap-4 relative z-10 w-full md:w-1/3">
            <div className="w-20 h-20 rounded-full bg-white border-2 border-[#00274c] flex items-center justify-center shadow-lg transform hover:scale-105 transition-transform">
              <Mic className="w-8 h-8 text-[#00274c]" />
            </div>
            <div className="text-center">
              <h4 className="font-bold text-gray-900 text-lg">1. {language === "English" ? "Speak / Type" : "பேசவும் / எழுதவும்"}</h4>
              <p className="text-sm text-gray-500 mt-2 max-w-[240px] mx-auto">
                {language === "English" 
                  ? "Describe your complaint in simple words. No complex technical forms required."
                  : "உங்கள் குறைகளை எளிய சொற்களில் விளக்குங்கள். கடினமான படிவங்கள் தேவையில்லை."}
              </p>
            </div>
          </div>

          {/* Step 2 */}
          <div className="flex flex-col items-center gap-4 relative z-10 w-full md:w-1/3">
            <div className="w-20 h-20 rounded-full bg-white border-2 border-[#feae2c] flex items-center justify-center shadow-lg transform hover:scale-105 transition-transform">
              <Brain className="w-8 h-8 text-[#feae2c]" />
            </div>
            <div className="text-center">
              <h4 className="font-bold text-gray-900 text-lg">2. {language === "English" ? "AI Classification" : "AI பகுப்பாய்வு"}</h4>
              <p className="text-sm text-gray-500 mt-2 max-w-[240px] mx-auto">
                {language === "English" 
                  ? "KURAL AI auto-categorizes, tags location coordinates, and assigns the correct helpline body."
                  : "KURAL AI உங்கள் புகாரை அலசி ஆராய்ந்து, தகுந்த மாநகராட்சி அதிகாரிகளுக்கு அனுப்புகிறது."}
              </p>
            </div>
          </div>

          {/* Step 3 */}
          <div className="flex flex-col items-center gap-4 relative z-10 w-full md:w-1/3">
            <div className="w-20 h-20 rounded-full bg-white border-2 border-green-600 flex items-center justify-center shadow-lg transform hover:scale-105 transition-transform">
              <CheckCircle className="w-8 h-8 text-green-600" />
            </div>
            <div className="text-center">
              <h4 className="font-bold text-gray-900 text-lg">3. {language === "English" ? "Live Tracking" : "நேரடி கண்காணிப்பு"}</h4>
              <p className="text-sm text-gray-500 mt-2 max-w-[240px] mx-auto">
                {language === "English" 
                  ? "Get your unique Complaint ID and watch the action timeline live until resolution."
                  : "தனித்துவமான புகார் எண்ணை பெற்று, அதன் மீதான நடவடிக்கைகளை நேரலையாக கண்காணிக்கலாம்."}
              </p>
            </div>
          </div>

        </div>
      </section>

    </div>
  );
}
