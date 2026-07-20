import React from "react";
import { Phone, Heart, Shield, HelpCircle } from "lucide-react";

interface FooterProps {
  language: "English" | "Tamil";
}

export default function Footer({ language }: FooterProps) {
  return (
    <footer className="bg-white border-t border-gray-100 mt-auto shadow-sm" id="footer">
      <div className="max-w-7xl mx-auto px-6 py-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-start">
          
          {/* Column 1: Branding & Description */}
          <div className="flex flex-col gap-3 text-center md:text-left">
            <span className="text-xl font-bold text-[#00274c]">KURAL</span>
            <p className="text-sm text-gray-500 leading-relaxed">
              {language === "English" 
                ? "Chennai's premier AI-assisted civic action and routing platform. Connecting citizens with municipal authorities transparently."
                : "சென்னையின் அதிநவீன AI அடிப்படையிலான மக்கள் குறைதீர்ப்பு தளம். குடிமக்களையும் அரசு அதிகாரிகளையும் வெளிப்படையாக இணைக்கிறது."}
            </p>
            <p className="text-xs text-gray-400 mt-2">
              &copy; {new Date().getFullYear()} KURAL Civic Authority Platform. All rights reserved.
            </p>
          </div>

          {/* Column 2: Tamil Nadu Helpline Numbers */}
          <div className="flex flex-col gap-3 text-center md:text-left">
            <span className="text-[15px] font-bold text-[#00274c] uppercase tracking-wider flex items-center justify-center md:justify-start gap-1.5">
              <Phone className="w-4 h-4" />
              {language === "English" ? "Tamil Nadu Helplines" : "அரசு உதவி எண்கள்"}
            </span>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm text-gray-600">
              <span className="font-semibold">PWD (Highways): <span className="text-[#00274c] font-bold">1913</span></span>
              <span className="font-semibold">GCC (Corporation): <span className="text-[#00274c] font-bold">155333</span></span>
              <span className="font-semibold">CMWSSB (Water): <span className="text-[#00274c] font-bold">1916</span></span>
              <span className="font-semibold">TANGEDCO (Power): <span className="text-[#00274c] font-bold">1912</span></span>
            </div>
          </div>

          {/* Column 3: Legal & Support links */}
          <div className="flex flex-col gap-3 text-center md:text-left">
            <span className="text-[15px] font-bold text-[#00274c] uppercase tracking-wider flex items-center justify-center md:justify-start gap-1.5">
              <Shield className="w-4 h-4" />
              {language === "English" ? "Policy & Contact" : "கொள்கை & தொடர்பு"}
            </span>
            <div className="flex flex-wrap justify-center md:justify-start gap-x-6 gap-y-2 text-sm text-gray-600">
              <a href="#privacy" className="hover:underline hover:text-[#00274c] transition-all">
                {language === "English" ? "Privacy Policy" : "தனியுரிமைக் கொள்கை"}
              </a>
              <a href="#terms" className="hover:underline hover:text-[#00274c] transition-all">
                {language === "English" ? "Terms of Service" : "சேவை விதிமுறைகள்"}
              </a>
              <a href="#contact" className="hover:underline hover:text-[#00274c] transition-all">
                {language === "English" ? "Contact Us" : "தொடர்பு கொள்ள"}
              </a>
            </div>
          </div>

        </div>
      </div>
    </footer>
  );
}
