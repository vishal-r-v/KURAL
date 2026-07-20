import React from "react";
import { Building2, Timer, Radio } from "lucide-react";

interface StatsGridProps {
  language: "English" | "Tamil";
}

export default function StatsGrid({ language }: StatsGridProps) {
  const stats = [
    {
      icon: <Building2 className="w-9 h-9 text-[#00274c]" />,
      value: "38 Wards",
      label: language === "English" ? "Covered Across City" : "மாநகர வார்டுகள்"
    },
    {
      icon: <Timer className="w-9 h-9 text-[#feae2c]" />,
      value: "48h Avg",
      label: language === "English" ? "Resolution Time" : "சராசரி தீர்வு நேரம்"
    },
    {
      icon: <Radio className="w-9 h-9 text-[#ba1a1a] animate-pulse" />,
      value: "Live",
      label: language === "English" ? "Issue Tracking" : "நேரடி கண்காணிப்பு"
    }
  ];

  return (
    <section className="w-full py-2" id="stats-section">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        {stats.map((stat, idx) => (
          <div 
            key={idx} 
            className="bg-white rounded-2xl p-6 flex flex-col items-center justify-center text-center gap-3 border border-gray-200 hover:border-[#00274c] hover:shadow-md transition-all duration-300"
          >
            <div className="p-3 bg-gray-50 rounded-full">
              {stat.icon}
            </div>
            <h3 className="text-2xl font-bold text-gray-900">{stat.value}</h3>
            <p className="text-sm font-semibold text-gray-500 uppercase tracking-wider">{stat.label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
