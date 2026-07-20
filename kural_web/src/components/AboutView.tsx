import React from "react";
import { Mic, CheckCircle, Brain, Radio, Landmark, ShieldCheck } from "lucide-react";

interface AboutViewProps {
  language: "English" | "Tamil";
}

export default function AboutView({ language }: AboutViewProps) {
  return (
    <div className="space-y-10 animate-fadeIn" id="about-view">
      
      {/* Narrative Intro Hero */}
      <section className="text-center space-y-4 max-w-2xl mx-auto py-4">
        <h1 className="text-4xl font-extrabold text-[#00274c]">
          {language === "English" ? "Civic Action, Simplified." : "மக்கள் குறைதீர்ப்பு, எளிமையாக்கப்பட்டது."}
        </h1>
        <p className="text-gray-500 leading-relaxed text-base">
          {language === "English"
            ? "KURAL is built to transform the relationship between Chennai's citizens and local authorities. By removing bureaucratic hurdles, we ensure every voice gets routed, analyzed, and solved with absolute transparency."
            : "குரல் தளம் சென்னை குடிமக்களுக்கும் மாநகராட்சிக்கும் இடையிலான இடைவெளியைக் குறைக்கிறது. அரசு நடைமுறைகளை எளிதாக்கி, ஒவ்வொரு புகாருக்கும் தகுந்த நேரத்தில் தீர்வு கிடைக்கச் செய்கிறோம்."}
        </p>
      </section>

      {/* Isometric City view Banner */}
      <div className="w-full rounded-3xl overflow-hidden border border-gray-100 shadow-xl shadow-gray-100 h-64 md:h-80 relative">
        <div 
          className="bg-cover bg-center w-full h-full opacity-90"
          style={{ backgroundImage: `url('https://lh3.googleusercontent.com/aida-public/AB6AXuColO84OoH1uiQyyHKwaCDT6GwhHDtfDPNTwgB0zcDLNoTnzfaW_oLDWepAyDnwWAUvxW3Y1bitSt72zJrd7EHgNnB61s0DF1S4OAO6ku1ZxKFj-saL8XLERkLwPNfjz-UsrPGySXnVesRBxFqd0ZMwNip8YBkk6pSRcWxG-V12E1iju4fcMzjRhSlku99jRqKDWRh4S32poBZ-XKbspulVThmbXb-HZuO3g3fmVrV_VfvHLIiNWOXUGeeyrkSJr8G-e7nhBghKLSjD')` }}
        ></div>
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent flex items-end p-8">
          <div className="text-white space-y-1.5">
            <h3 className="text-lg sm:text-xl font-bold tracking-tight">Chennai Intelligent City Dashboard</h3>
            <p className="text-xs sm:text-sm text-gray-200 font-semibold">Empowered by KURAL Automated SLA Routing</p>
          </div>
        </div>
      </div>

      {/* Core Narrative Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-lg shadow-gray-50 flex flex-col gap-4">
          <div className="w-12 h-12 rounded-xl bg-[#00274c]/5 text-[#00274c] flex items-center justify-center">
            <Mic className="w-6 h-6" />
          </div>
          <h3 className="font-extrabold text-gray-900 text-lg">
            {language === "English" ? "Speak Your Mind" : "குரல் மூலம் சமர்ப்பிக்க"}
          </h3>
          <p className="text-sm text-gray-500 leading-relaxed">
            {language === "English"
              ? "Submit complex issues through seamless voice transcription. No technical terminology required — describe the leak, garbage, or pothole in simple terms."
              : "மைக் பொத்தானை அழுத்திப் பேசுங்கள். உங்களது எளிய சொற்களை எங்களது அதிநவீன டிரான்ஸ்கிரைபர் துல்லியமாக உரையாக மாற்றும்."}
          </p>
        </div>

        <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-lg shadow-gray-50 flex flex-col gap-4">
          <div className="w-12 h-12 rounded-xl bg-[#feae2c]/10 text-[#6b4500] flex items-center justify-center">
            <Brain className="w-6 h-6" />
          </div>
          <h3 className="font-extrabold text-gray-900 text-lg">
            {language === "English" ? "AI Intelligence Routing" : "AI அடிப்படையிலான பகுப்பாய்வு"}
          </h3>
          <p className="text-sm text-gray-500 leading-relaxed">
            {language === "English"
              ? "Our backend uses server-side Claude (Anthropic) to automatically detect category, assess urgency, isolate the ward location, and dispatch corresponding helpline codes."
              : "மாநிலத்தின் முன்னணி AI மாடல்கள் உங்களது புகாரை பகுப்பாய்வு செய்து தானாகவே வார்டு மற்றும் தகுந்த மாநகராட்சி அதிகாரிகளுக்கு அனுப்பிவைக்கும்."}
          </p>
        </div>

        <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-lg shadow-gray-50 flex flex-col gap-4">
          <div className="w-12 h-12 rounded-xl bg-green-50 text-green-700 flex items-center justify-center">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h3 className="font-extrabold text-gray-900 text-lg">
            {language === "English" ? "Guaranteed Escalation" : "உறுதியான தீர்வுகள்"}
          </h3>
          <p className="text-sm text-gray-500 leading-relaxed">
            {language === "English"
              ? "If a grievance remains unresolved beyond the 48-hour Service Level Agreement window, our system automatically triggers secondary escalation channels directly to zonal chiefs."
              : "நிர்ணயிக்கப்பட்ட 48 மணிநேரத்திற்குள் புகாருக்கு தீர்வு காணாவிடில், அது தானாகவே உயர் அதிகாரிக்கு மாற்றப்படும்."}
          </p>
        </div>

      </div>

    </div>
  );
}
