# Sample Audio Files for KURAL Demo

Place test audio files here for demo purposes.

## Recommended test files:

### 1. garbage_adyar.wav (HERO DEMO)
- Content: Tamil/Tanglish complaint about uncollected garbage in Adyar
- Script: "Adyar area-la moonu naal aaga garbage collect pannala. 
           Near Adyar Bridge-la romba naatram. Please urgent action edungal."
- Expected extraction: category=garbage, ward=Adyar, urgency=high

### 2. water_velachery.wav
- Content: English complaint about water supply outage in Velachery
- Script: "There has been no water supply in Velachery for 2 days. 
           The pipe near Vijaya Nagar has burst. Please fix immediately."
- Expected extraction: category=water, ward=Velachery, urgency=high

### 3. pothole_tnagar.wav
- Content: Tanglish complaint about road pothole in T.Nagar
- Script: "T.Nagar Pondy Bazaar signal-kku near-la oru periya pothole iruku.
           Yesterday bike accident achu. Road repair urgent."
- Expected extraction: category=roads, ward=T.Nagar, urgency=high

## Recording tips:
- Use Audacity, Voice Memos (iPhone), or Google Recorder
- Save as WAV or MP3, 16kHz or higher, mono or stereo
- Speak clearly, include area name prominently
- 15-30 seconds is ideal

## Using without audio files:
Use the text complaint input in the Streamlit UI or POST /complaint/text API.
