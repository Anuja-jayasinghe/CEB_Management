#pragma once

// WiFi Configuration
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Device Configuration
const char* DEVICE_PASSWORD = "admin123";  // Change this for security!
const char* DEVICE_HOSTNAME = "esp32-cam-security";

// GitHub Configuration
const char* GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx";
const char* GITHUB_OWNER = "your-username";
const char* GITHUB_REPO = "security-camera-images";
const char* GITHUB_BRANCH = "main";  // or "master"

// Time Configuration for Sri Lanka
const long GMT_OFFSET_SEC = 19800;  // +5:30 hours (5.5 * 3600)
const int DAYLIGHT_OFFSET_SEC = 0;   // No daylight saving in Sri Lanka
const char* NTP_SERVER = "pool.ntp.org";

// Camera Schedule Configuration
const int WORK_START_HOUR = 7;   // 7:00 AM
const int WORK_END_HOUR = 18;    // 6:00 PM
const int PHOTO_INTERVAL = 3;    // Every 3 hours

// Image Quality Settings
const int JPEG_QUALITY = 10;     // 1-63, lower is better quality
const int FRAME_SIZE = 13;       // FRAMESIZE_UXGA (1600x1200)

// Pin Definitions (for reference)
#define CAMERA_MODEL_AI_THINKER  // Define camera model