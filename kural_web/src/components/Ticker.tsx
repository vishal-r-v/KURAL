import React from "react";

export default function Ticker() {
  const tickerItems = [
    { text: "Road repair in Teynampet escalated to PWD", color: "bg-amber-500" },
    { text: "Water logging in Velachery resolved", color: "bg-green-500" },
    { text: "Streetlight issue in Adyar logged", color: "bg-blue-500" },
    { text: "Drainage block in Mylapore resolved", color: "bg-green-500" },
    { text: "Pothole repair on Mount Road dispatched", color: "bg-amber-500" }
  ];

  return (
    <div className="w-full bg-white border-y border-gray-200 py-3 relative overflow-hidden my-4" id="ticker-section">
      <div className="absolute left-0 top-0 bottom-0 w-12 bg-gradient-to-r from-white to-transparent z-10"></div>
      <div className="absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-white to-transparent z-10"></div>
      <div className="flex whitespace-nowrap overflow-hidden">
        <div className="animate-[marquee_30s_linear_infinite] flex gap-12 text-sm font-medium text-gray-600">
          {/* Double list for smooth infinite scrolling */}
          {[...tickerItems, ...tickerItems, ...tickerItems].map((item, idx) => (
            <span key={idx} className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${item.color}`}></span>
              {item.text}
            </span>
          ))}
        </div>
      </div>
      <style>{`
        @keyframes marquee {
          0% { transform: translateX(0%); }
          100% { transform: translateX(-33.33%); }
        }
      `}</style>
    </div>
  );
}
