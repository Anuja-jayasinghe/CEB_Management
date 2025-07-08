#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <Base64.h>
#include "time.h"

// WiFi credentials
const char* ssid = "Area_34";
const char* ssid = "ssid";
const char* password = "password";

// GitHub Personal Access Token
const char* githubToken = "Github_PAT";
const char* githubRepo = "usename/reponame";
const char* githubFolder = "folderName";

// NTP Server config
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 19800; // Sri Lanka time
const int daylightOffset_sec = 0;

void startCamera() {
  Serial.println("🔧 Initializing camera...");
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = 5;
  config.pin_d1       = 18;
  config.pin_d2       = 19;
  config.pin_d3       = 21;
  config.pin_d4       = 36;
  config.pin_d5       = 39;
  config.pin_d6       = 34;
  config.pin_d7       = 35;
  config.pin_xclk     = 0;
  config.pin_pclk     = 22;
  config.pin_vsync    = 25;
  config.pin_href     = 23;
  config.pin_sscb_sda = 26;
  config.pin_sscb_scl = 27;
  config.pin_pwdn     = 32;
  config.pin_reset    = -1;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if(psramFound()) {
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 10;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_CIF;
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("❌ Camera init failed! Error 0x%x\n", err);
  } else {
    Serial.println("✅ Camera initialized successfully.");
  }
}

String getTimestampFilename() {
  Serial.println("⏱ Getting timestamp...");
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("❌ Failed to obtain time. Using fallback filename.");
    return "photo_unknown.jpg";
  }

  char buffer[30];
  strftime(buffer, sizeof(buffer), "photo_%Y%m%d_%H%M%S.jpg", &timeinfo);
  Serial.print("📸 Filename generated: ");
  Serial.println(buffer);
  return String(buffer);
}

void uploadToGitHub(camera_fb_t* fb, const String& filename) {
  if (!fb) {
    Serial.println("❌ Camera frame is null. Skipping upload.");
    return;
  }

  Serial.print("🧪 Encoding image to base64... ");
  String imageBase64 = base64::encode(fb->buf, fb->len);
  Serial.println("Done.");

  Serial.println("📦 Preparing JSON payload...");
  String jsonPayload = "{";
  jsonPayload += "\"message\": \"ESP32-CAM upload\",";
  jsonPayload += "\"content\": \"" + imageBase64 + "\"";
  jsonPayload += "}";

  String url = "https://api.github.com/repos/" + String(githubRepo) + "/contents/" + String(githubFolder) + "/" + filename;

  Serial.println("🌐 Sending PUT request to GitHub API...");
  HTTPClient http;
  http.begin(url);
  http.addHeader("Authorization", "token " + String(githubToken));
  http.addHeader("Content-Type", "application/json");

  int httpCode = http.PUT(jsonPayload);
  Serial.printf("📡 HTTP Response Code: %d\n", httpCode);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.println("📨 GitHub API Response:");
    Serial.println(response);
  } else {
    Serial.println("❌ Upload failed: " + http.errorToString(httpCode));
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n🔌 Booting...");

  WiFi.begin(ssid, password);
  Serial.print("📶 Connecting to WiFi");

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi connected.");
    Serial.print("📡 IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n❌ WiFi connection failed.");
    return;
  }

  Serial.println("🕓 Syncing time from NTP...");
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  delay(2000);

  // Start camera
  startCamera();
  delay(1000);

  Serial.println("📷 Capturing photo...");
  camera_fb_t* fb = esp_camera_fb_get();

  if (fb) {
    Serial.println("✅ Photo captured.");
    String filename = getTimestampFilename();
    uploadToGitHub(fb, filename);
    esp_camera_fb_return(fb);
  } else {
    Serial.println("❌ Failed to capture photo.");
  }

  Serial.println("🛑 Task complete. Entering idle mode.");
}

void loop() {
  // Idle — do nothing
}
