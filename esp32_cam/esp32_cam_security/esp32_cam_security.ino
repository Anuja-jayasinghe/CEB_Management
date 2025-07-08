#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <time.h>
#include <base64.h>
#include "esp_sleep.h"
#include "secrets.h"
#include <WebServer.h>
#include <WiFiClient.h>

// Camera pins for AI-Thinker ESP32-CAM
#if defined(CAMERA_MODEL_AI_THINKER)
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
#endif

// Global variables
bool camera_initialized = false;
RTC_DATA_ATTR int boot_count = 0;
RTC_DATA_ATTR unsigned long last_photo_time = 0;
WebServer server(80);
bool live_stream_active = false;
unsigned long live_stream_start_time = 0;
const unsigned long LIVE_STREAM_TIMEOUT = 300000; // 5 minutes

void goToSleep(int seconds);
bool initCamera();
bool isWorkingHours();
void takeScheduledPhoto();
bool uploadToGitHub(uint8_t* data, size_t len, const char* filename);
void calculateSleepTime();
void handleRoot();
void handleStream();
void handleVideoFeed();
void handleLogin();
void handleLogout();

void setup() {
  Serial.begin(115200);
  boot_count++;
  
  Serial.printf("Boot count: %d\n", boot_count);
  
  // Connect to WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  WiFi.setHostname(DEVICE_HOSTNAME);
  
  Serial.print("Connecting to WiFi");
  int wifi_attempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifi_attempts < 30) {
    delay(500);
    Serial.print(".");
    wifi_attempts++;
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection failed, going to sleep");
    goToSleep(300); // Try again in 5 minutes
    return;
  }
  
  Serial.println();
  Serial.print("WiFi connected! IP: ");
  Serial.println(WiFi.localIP());
  
  // Initialize time (critical for GitHub API)
  configTime(0, 0, "pool.ntp.org");
  time_t now = time(nullptr);
  while (now < 24 * 3600) {
    delay(500);
    now = time(nullptr);
  }
  Serial.println("Time synced");

  // Initialize camera
  if (!initCamera()) {
    Serial.println("Camera init failed");
    goToSleep(300); // Try again in 5 minutes
    return;
  }
  
  // Take a picture immediately on boot
  takeScheduledPhoto();
  
  // Setup web server routes
  server.on("/", HTTP_GET, handleRoot);
  server.on("/stream", HTTP_GET, handleStream);
  server.on("/video_feed", HTTP_GET, handleVideoFeed);
  server.on("/login", HTTP_POST, handleLogin);
  server.on("/logout", HTTP_GET, handleLogout);

  server.begin();
  Serial.println("HTTP server started");

  // Calculate sleep time and go to sleep
  calculateSleepTime();
}

void loop() {
  server.handleClient();

  // If live stream is active but client disconnected
  if (live_stream_active && !server.client().connected()) {
    live_stream_active = false;
    Serial.println("Client disconnected, stopping stream");

    // Put camera back to sleep if not during working hours
    if (!isWorkingHours()) {
      esp_camera_deinit();
      camera_initialized = false;
    }
  }

  // If during working hours and not streaming, take scheduled photos
  if (isWorkingHours() && !live_stream_active) {
    if (millis() - last_photo_time >= PHOTO_INTERVAL * 3600 * 1000) {
      takeScheduledPhoto();
      last_photo_time = millis();
    }
  }
}

bool initCamera() {
  if (camera_initialized) return true;
  
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  if (psramFound()) {
    config.frame_size = FRAMESIZE_UXGA;
    config.jpeg_quality = JPEG_QUALITY;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }
  
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return false;
  }
  
  camera_initialized = true;
  
  // Camera settings for better quality
  sensor_t * s = esp_camera_sensor_get();
  s->set_brightness(s, 0);
  s->set_contrast(s, 0);
  s->set_saturation(s, 0);
  s->set_special_effect(s, 0);
  s->set_whitebal(s, 1);
  s->set_awb_gain(s, 1);
  s->set_wb_mode(s, 0);
  s->set_exposure_ctrl(s, 1);
  s->set_aec2(s, 0);
  s->set_ae_level(s, 0);
  s->set_aec_value(s, 300);
  s->set_gain_ctrl(s, 1);
  s->set_agc_gain(s, 0);
  s->set_gainceiling(s, (gainceiling_t)0);
  s->set_bpc(s, 0);
  s->set_wpc(s, 1);
  s->set_raw_gma(s, 1);
  s->set_lenc(s, 1);
  s->set_hmirror(s, 0);
  s->set_vflip(s, 0);
  s->set_dcw(s, 1);
  s->set_colorbar(s, 0);
  
  return true;
}

bool isWorkingHours() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("Failed to obtain time");
    return false;
  }
  
  int current_hour = timeinfo.tm_hour;
  // Working hours: 6 AM to 4 AM (next day)
  return (current_hour >= 6 || current_hour < 4);
}

void takeScheduledPhoto() {
  Serial.println("Taking photo...");
  
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    return;
  }
  
  // Create filename with timestamp
  struct tm timeinfo;
  char filename[50];
  if (getLocalTime(&timeinfo)) {
    strftime(filename, sizeof(filename), "photo_%Y%m%d_%H%M%S.jpg", &timeinfo);
  } else {
    snprintf(filename, sizeof(filename), "photo_%lu.jpg", millis());
  }
  
  Serial.printf("Captured image size: %d bytes\n", fb->len);
  
  // Upload to GitHub
  bool upload_success = uploadToGitHub(fb->buf, fb->len, filename);
  
  if (upload_success) {
    Serial.println("Photo uploaded successfully to GitHub");
  } else {
    Serial.println("Photo upload failed");
  }
  
  esp_camera_fb_return(fb);
}

bool uploadToGitHub(uint8_t* data, size_t len, const char* filename) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, skipping upload");
    return false;
  }

  Serial.println("\n=== GitHub Upload Debug ===");
  Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
  
  // Memory check
  if (ESP.getFreeHeap() < 50000) {
    Serial.println("Low memory - skipping upload");
    return false;
  }

  // Base64 encode
  String base64Image = base64::encode(data, len);
  base64Image.replace("\n", "");
  Serial.printf("Image: %d bytes -> Base64: %d chars\n", len, base64Image.length());

  // Create payload
  DynamicJsonDocument doc(3072);
  doc["message"] = "ESP32-CAM Upload";
  doc["content"] = base64Image;
  doc["branch"] = GITHUB_BRANCH;

  String jsonString;
  serializeJson(doc, jsonString);
  Serial.printf("JSON size: %d bytes\n", jsonString.length());

  // Configure client
  WiFiClientSecure client;
  client.setInsecure();
  // client.setBufferSizes(4096, 4096); // Critical for large payloads

  HTTPClient http;
  http.setReuse(true);
  http.setTimeout(15000);

  String url = "https://api.github.com/repos/" + String(GITHUB_OWNER) + 
              "/" + String(GITHUB_REPO) + "/contents/images/" + String(filename);
  
  if (!http.begin(client, url)) {
    Serial.println("HTTP begin failed");
    return false;
  }

  http.addHeader("Authorization", "token " + String(GITHUB_TOKEN));
  http.addHeader("Content-Type", "application/json");
  http.addHeader("User-Agent", "ESP32-CAM");

  // Send request
  Serial.println("Uploading...");
  int httpCode = http.PUT(jsonString);
  
  // Handle response
  if (httpCode > 0) {
    Serial.printf("HTTP Code: %d\n", httpCode);
    Serial.println("Response: " + http.getString());
  } else {
    Serial.printf("HTTP Error: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();
  return (httpCode == 201);
}

void calculateSleepTime() {
  if (live_stream_active) {
    // Don't sleep while streaming
    return;
  }

  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    goToSleep(3600); // Default 1 hour if time sync fails
    return;
  }
  
  int current_hour = timeinfo.tm_hour;
  int sleep_seconds;
  
  if (current_hour >= 4 && current_hour < 6) {
    // Between 4 AM and 6 AM - sleep until 6 AM
    sleep_seconds = (6 - current_hour) * 3600;
  } else if (current_hour >= 6) {
    // After 6 AM - sleep for interval
    sleep_seconds = PHOTO_INTERVAL * 3600;
  } else {
    // Before 4 AM (overnight) - sleep until 6 AM
    sleep_seconds = (6 + (24 - current_hour)) * 3600;
  }
  
  goToSleep(sleep_seconds);
}

void goToSleep(int seconds) {
  Serial.printf("Going to sleep for %d seconds\n", seconds);
  
  // Configure timer wakeup
  esp_sleep_enable_timer_wakeup(seconds * 1000000ULL);
  
  // Put camera to sleep
  esp_camera_deinit();
  camera_initialized = false;
  
  // Enter deep sleep
  esp_deep_sleep_start();
}

// --- Web server handlers ---

void handleRoot() {
  if (!server.authenticate("admin", DEVICE_PASSWORD)) {
    return server.requestAuthentication();
  }
  
  String html = R"=====(
<html>
<head>
  <title>ESP32-CAM Live Stream</title>
  <style>
    body { margin: 0; padding: 0; background: #000; color: #fff; text-align: center; }
    .container { max-width: 800px; margin: 0 auto; padding: 20px; }
    .stream-container { position: relative; padding-bottom: 56.25%; }
    #stream { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
    .controls { margin: 20px 0; }
    .btn { 
      background: #f00; color: #fff; padding: 10px 20px; 
      text-decoration: none; border-radius: 5px; margin: 0 10px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>ESP32-CAM Live Stream</h1>
    <div class="stream-container">
      <img id="stream" src="/video_feed">
    </div>
    <div class="controls">
      <a href="/logout" class="btn">Stop Stream & Logout</a>
    </div>
  </div>
</body>
</html>
)=====";
  
  server.send(200, "text/html", html);
}

void handleStream() {
  if (!server.authenticate("admin", DEVICE_PASSWORD)) {
    return server.requestAuthentication();
  }

  // Wake camera if not already awake
  if (!camera_initialized) {
    if (!initCamera()) {
      server.send(500, "text/plain", "Camera init failed");
      return;
    }
  }

  live_stream_active = true;
  live_stream_start_time = millis();
  Serial.println("Live stream started");

  // Redirect to root which will show the stream
  server.sendHeader("Location", "/");
  server.send(303);
}

void handleVideoFeed() {
  Serial.println("Starting video feed handler");
  
  WiFiClient client = server.client();
  
  // Send headers
  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: multipart/x-mixed-replace; boundary=frame");
  client.println();
  
  unsigned long last_frame = 0;
  const unsigned long frame_delay = 1000 / 15; // 15 FPS
  
  while (live_stream_active && client.connected()) {
    if (millis() - live_stream_start_time > LIVE_STREAM_TIMEOUT) {
      Serial.println("Stream timeout reached");
      live_stream_active = false;
      break;
    }
    
    unsigned long now = millis();
    if (now - last_frame < frame_delay) {
      delay(5);
      continue;
    }
    last_frame = now;

    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      continue;
    }

    client.println("--frame");
    client.println("Content-Type: image/jpeg");
    client.println("Content-Length: " + String(fb->len));
    client.println();
    client.write(fb->buf, fb->len);
    client.println();

    esp_camera_fb_return(fb);
    
    // Small delay to prevent watchdog triggers
    delay(1);
  }
  
  Serial.println("Video feed handler ended");
  
  // Put camera back to sleep if not during working hours
  if (!isWorkingHours()) {
    esp_camera_deinit();
    camera_initialized = false;
  }
}

void handleLogin() {
  if (server.hasArg("username") && server.hasArg("password")) {
    if (server.arg("username") == "admin" &&
        server.arg("password") == DEVICE_PASSWORD) {
      server.sendHeader("Location", "/");
      server.send(303);
      return;
    }
  }
  server.send(401, "text/plain", "Login Failed");
}

void handleLogout() {
  live_stream_active = false;
  server.sendHeader("Location", "/");
  server.send(303);
  Serial.println("User logged out, stream stopped");
}