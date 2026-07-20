import React, { useState } from "react";
import { Mic, Menu, X } from "lucide-react";
import CitizenLogin from "./CitizenLogin.tsx";

interface NavbarProps {
  currentTab: string;
  setTab: (tab: string) => void;
  language: "English" | "Tamil";
  setLanguage: (lang: "English" | "Tamil") => void;
}

export default function Navbar({ currentTab, setTab, language, setLanguage }: NavbarProps) {
  const [isOpen, setIsOpen] = useState(false);

  const navItems = [
    { id: "home", label: language === "English" ? "Home" : "முகப்பு" },
    { id: "file", label: language === "English" ? "File Complaint" : "புகார் அளிக்கவும்" },
    { id: "track", label: language === "English" ? "Track" : "பின்தொடரவும்" },
    { id: "dashboard", label: language === "English" ? "Dashboard" : "தரவுத்தளம்" },
    { id: "history", label: language === "English" ? "History" : "பதிவேடு" },
    { id: "about", label: language === "English" ? "About" : "எங்களை பற்றி" },
  ];

  return (
    <nav className="fixed top-0 left-0 w-full z-50 bg-white border-b border-gray-100 shadow-sm h-[72px]" id="navbar">
      <div className="max-w-7xl mx-auto h-full px-6 flex justify-between items-center">
        {/* Brand Logo & Title */}
        <div 
          className="flex items-center gap-2.5 cursor-pointer text-2xl font-bold text-[#00274c] select-none"
          onClick={() => setTab("home")}
          id="brand-logo"
        >
          <div className="w-9 h-9 rounded-full bg-[#00274c] text-white flex items-center justify-center shadow-md">
            <Mic className="w-5 h-5" />
          </div>
          <span className="tracking-wide">KURAL</span>
        </div>

        {/* Desktop Nav Items */}
        <div className="hidden md:flex space-x-8 h-full items-center">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setTab(item.id);
                setIsOpen(false);
              }}
              className={`text-[15px] font-semibold transition-all h-full px-1 border-b-2 flex items-center ${
                currentTab === item.id
                  ? "text-[#00274c] border-[#00274c] opacity-100"
                  : "text-gray-500 border-transparent hover:text-[#00274c] hover:border-gray-200 opacity-85"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Language Switcher, Citizen Login & Hamburger */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setLanguage(language === "English" ? "Tamil" : "English")}
            className="text-sm font-bold text-[#00274c] border border-[#00274c]/20 hover:bg-gray-50 px-3.5 py-1.5 rounded-full transition-all"
            id="lang-btn"
          >
            {language === "English" ? "English / தமிழ்" : "தமிழ் / English"}
          </button>

          <CitizenLogin language={language} />

          <button 
            onClick={() => setIsOpen(!isOpen)}
            className="md:hidden text-gray-700 hover:text-[#00274c] transition-colors p-1"
            aria-label="Toggle Menu"
          >
            {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {isOpen && (
        <div className="md:hidden absolute top-[72px] left-0 w-full bg-white border-b border-gray-200 shadow-lg py-4 px-6 flex flex-col space-y-3 z-40 animate-fadeIn">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setTab(item.id);
                setIsOpen(false);
              }}
              className={`w-full text-left py-2 px-3 rounded-lg text-base font-semibold transition-all ${
                currentTab === item.id
                  ? "bg-[#00274c]/5 text-[#00274c]"
                  : "text-gray-600 hover:bg-gray-50 hover:text-[#00274c]"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </nav>
  );
}
