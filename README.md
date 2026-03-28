# 🚨 Pikud Ha'Or (פיקוד האור)

**Pikud Ha'Or** is a lightweight, background-running Python service that links Israel's Home Front Command (Pikud Ha'Oref) real-time API directly to your Yeelight RGB smart bulb. Keep yourself and your family safe with immediate, highly visible visual alerts whenever a siren is triggered in your area.

> **⚠️ DISCLAIMER: This script is 100% vibe-coded.**  
> It was built with the help of AI, caffeine, and good intentions. While it accurately polls the official API and does its absolute best to keep you informed, **do not rely on this as your sole life-saving alerting system.** Always keep the official Pikud Ha'Oref app installed on your phone and listen for physical sirens!

---

## ✨ Features

- 🔵 **Early Warnings (התרעה מקדימה):** If an early warning is issued for your area, the bulb will flash blue 10 times and then return to normal.
- 🔴 **Active Sirens (צבע אדום):** Turns your bulb blindingly bright red immediately upon an alert in your zone.
- ⏳ **Official All-Clear Timer:** Automatically tracks when the siren disappears from the API, starts the mandatory 10-minute shelter countdown, and safely restores your bulb to its original color/power state when it's safe to leave.
- 🖱️ **Silent Background Process:** Sits quietly in your Windows system tray (taskbar) with zero terminal windows or pop-ups.
- 📝 **Live Configuration:** Update your location or IP address via a simple text file and reload it instantly from the taskbar.

---

## 🚀 Setup & Usage

### 1. Prerequisites
You will need Python installed on your computer. Install the required libraries by running:
```bash
pip install pystray Pillow requests yeelight
```

**IMPORTANT (Yeelight App):**  
Open your Yeelight app on your phone, navigate to your bulb's settings, and **Enable LAN Control** (sometimes called Developer Mode). The script cannot communicate with the bulb without this!

### 2. First Run & Configuration
1. Run `YeelightAlert.pyw`. A target-shaped icon will appear in your system tray.
2. Right-click the tray icon and select **Edit Configuration**.
3. A text file (`pikud_config.json`) will open. Fill in your Yeelight's local IP address and your exact zone exactly as it appears in the Home Front Command (e.g., `"להבים"` or `"תל אביב - דרום"`).
4. Save the file and close it.
5. Right-click the tray icon and select **Test Configuration**. The bulb should flash green three times if connected properly!

### 3. Run Automatically on Windows Startup
Want this to protect you silently in the background every time you turn on your PC?
1. Make sure your file is named `YeelightAlert.pyw` (the `w` tells Windows to run it silently without a black console window).
2. Right-click `YeelightAlert.pyw` and select **Create shortcut**.
3. Press `Win + R` on your keyboard, type `shell:startup`, and press Enter.
4. Drag and drop the newly created shortcut into that folder.  
*Note: If Windows ever asks you "How do you want to open this file?" on startup, choose `pythonw.exe` from your Python installation folder and check "Always use this app".*

---

## 🤝 Contributing

Contributions are absolutely welcome! Whether you want to add support for other smart home ecosystems (Philips Hue, Tuya, Home Assistant), optimize the polling logic, or just fix a typo—feel free to open an Issue or submit a Pull Request. Let's make this tool better for everyone.

---

## 🇮🇱 תקציר בעברית (Hebrew Summary)

**פיקוד האור** הוא סקריפט פייתון שרץ ברקע (System Tray) ומחבר בין מערכת ההתרעות של פיקוד העורף לנורות חכמות מסוג Yeelight. 

**איך זה עובד?**
* ברגע שיש **התרעה מקדימה** באזור שהגדרתם, הנורה תהבהב בצבע כחול 10 פעמים כדי להסב את תשומת ליבכם.
* בזמן **אזעקת אמת**, הנורה תידלק מיד בצבע אדום בוהק.
* הסקריפט מזהה מתי ההתרעה יורדת משרתי פיקוד העורף, מפעיל טיימר אוטומטי של 10 דקות (זמן ההמתנה הרשמי בממ"ד), ובסיומו מחזיר את הנורה בדיוק למצב ולצבע שהייתה בו לפני האזעקה!

**שימו לב:** יש לוודא שהפעלתם "LAN Control" בהגדרות המנורה באפליקציה של Yeelight, אחרת הסקריפט לא יוכל לשלוט בה. כמו כן, הפרויקט נכתב באווירה טובה ("vibe-coded") בעזרת בינה מלאכותית – השתמשו בו ככלי עזר בלבד ואל תסתמכו עליו כתחליף לאפליקציה הרשמית של פיקוד העורף או לצופרים.

שימרו על עצמכם! 🙏