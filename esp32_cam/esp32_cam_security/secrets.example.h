#pragma once

// WiFi Configuration
struct WiFiCredentials {
  const char* ssid;
  const char* password;
};

WiFiCredentials WIFI_CREDENTIALS[] = {
  {"SSID1", "PASSWORD1"}, //Change with actual passwords
  {"SSID2", "PASSWORD2"}
 
};
const int NUM_WIFI_CREDENTIALS = sizeof(WIFI_CREDENTIALS) / sizeof(WIFI_CREDENTIALS[0]);

// Device Configuration
const char* DEVICE_PASSWORD = "admin";  // Change this for security!
const char* DEVICE_HOSTNAME = "esp32-cam-security";

// GitHub Configuration
const char* GITHUB_TOKEN = "GITHUB_PERSONAL_ACCESS_TOKEN"; //Change with actual Github PAT
const char* GITHUB_OWNER = "Anuja-jayasinghe";
const char* GITHUB_REPO = "REPO_NAME";
const char* GITHUB_BRANCH = "main";  // or "master"

// Time Configuration for Sri Lanka
const long GMT_OFFSET_SEC = 19800;  // +5:30 hours (5.5 * 3600)
const int DAYLIGHT_OFFSET_SEC = 0;   // No daylight saving in Sri Lanka
const char* NTP_SERVER = "pool.ntp.org";

// Image Quality Settings
const int JPEG_QUALITY = 10;     // 1-63, lower is better quality
const int FRAME_SIZE = 13;       // FRAMESIZE_UXGA (1600x1200)

// Pin Definitions (for reference)
#define CAMERA_MODEL_AI_THINKER  // Define camera model