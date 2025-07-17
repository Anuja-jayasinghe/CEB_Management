#include <WiFi.h>
#include "esp_camera.h"
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <time.h>
#include "secrets.h"
#include <esp_sleep.h>
#include <Base64.h>

// === Scheduled times ===
struct ScheduleTime {
  int hour;
  int minute;
};

ScheduleTime photo_schedule[] = {
  {8, 0},
  {10, 30},
  {12, 0},
  {14, 0},
  {16, 15}
};
const int NUM_SCHEDULES = sizeof(photo_schedule) / sizeof(photo_schedule[0]);

// === Function Prototypes ===
void connectWiFi();
void syncTime();
bool take_and_upload_photo();
void take_and_upload_photo_with_retry();
int get_seconds_until_next_schedule(struct tm current_time);
void go_to_sleep_until_next_schedule(int sleep_seconds);
bool is_scheduled_now(struct tm timeinfo);
String getTimestampFilename();
bool upload_to_github(const uint8_t* image_data, size_t image_len, const String& filename);
bool resolve_dns(const char* hostname);

void setup() {
  Serial.begin(115200);
  delay(1000);

  // === Camera Model & Pins ===
#define CAMERA_MODEL_AI_THINKER
#if defined(CAMERA_MODEL_AI_THINKER)
  #define PWDN_GPIO_NUM    32
  #define RESET_GPIO_NUM   -1
  #define XCLK_GPIO_NUM     0
  #define SIOD_GPIO_NUM    26
  #define SIOC_GPIO_NUM    27
  #define Y9_GPIO_NUM      35
  #define Y8_GPIO_NUM      34
  #define Y7_GPIO_NUM      39
  #define Y6_GPIO_NUM      36
  #define Y5_GPIO_NUM      21
  #define Y4_GPIO_NUM      19
  #define Y3_GPIO_NUM      18
  #define Y2_GPIO_NUM       5
  #define VSYNC_GPIO_NUM   25
  #define HREF_GPIO_NUM    23
  #define PCLK_GPIO_NUM    22
#else
  #error "Camera model not selected!"
#endif

  // Initialize camera
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
  config.frame_size = FRAMESIZE_UXGA;
  config.jpeg_quality = JPEG_QUALITY;
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    go_to_sleep_until_next_schedule(300); // Sleep for 5 minutes and retry
    return;
  }

  connectWiFi();
  syncTime();

  // Always take a photo on boot (power restored)
  Serial.println("Power-up detected! Taking immediate photo...");
  take_and_upload_photo_with_retry();
}

void loop() {
  // After boot photo, check schedule
  time_t now = time(nullptr);
  struct tm timeinfo;
  localtime_r(&now, &timeinfo);

  // Check if current time matches any schedule
  if (is_scheduled_now(timeinfo)) {
    Serial.println("Scheduled time reached, taking photo...");
    take_and_upload_photo_with_retry();
  }

  // After handling schedule, sleep until next one
  int sleep_seconds = get_seconds_until_next_schedule(timeinfo);
  go_to_sleep_until_next_schedule(sleep_seconds);
}

// === WiFi Connection ===
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  bool connected = false;

  for (int i = 0; i < NUM_WIFI_CREDENTIALS; i++) {
    Serial.printf("Attempting to connect to WiFi SSID: %s\n", WIFI_CREDENTIALS[i].ssid);
    WiFi.begin(WIFI_CREDENTIALS[i].ssid, WIFI_CREDENTIALS[i].password);
    int retries = 0;
    while (WiFi.status() != WL_CONNECTED && retries < 30) {
      delay(500);
      Serial.print(".");
      retries++;
    }
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\nWiFi connected!");
      connected = true;
      break;
    }
    WiFi.disconnect();
    delay(1000); // Brief delay before trying next network
  }

  if (!connected) {
    Serial.println("\nAll WiFi connections failed, will retry later");
  }
}

// === Time Sync ===
void syncTime() {
  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
  Serial.println("Syncing time...");
  delay(2000);
  time_t now = time(nullptr);
  while (now < 100000) {
    delay(500);
    now = time(nullptr);
  }
  Serial.println("Time synced!");
}

// === Photo capture & upload retry ===
void take_and_upload_photo_with_retry() {
  bool success = false;
  int max_retries = 3; // Maximum retry attempts
  int retry_count = 0;

  while (!success && retry_count < max_retries) {
    success = take_and_upload_photo();
    if (!success) {
      Serial.println("Upload failed, retrying in 5 minutes...");
      delay(5 * 60 * 1000);
      connectWiFi(); // Attempt to reconnect to WiFi before retry
      retry_count++;
    }
  }

  if (!success) {
    Serial.println("Max retries reached, will try again at next schedule");
  }
}

// === Take and upload photo ===
bool take_and_upload_photo() {
  Serial.println("Capturing photo...");

  // Capture and discard initial photos to stabilize camera
  for (int i = 0; i < 3; i++) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Warm-up capture failed");
      continue;
    }
    esp_camera_fb_return(fb);
    delay(100); // Brief delay between warm-up captures
  }

  // Capture final photo
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    return false;
  }

  String filename = getTimestampFilename();
  bool upload_success = upload_to_github(fb->buf, fb->len, filename);

  esp_camera_fb_return(fb);
  return upload_success;
}

// === DNS Resolution Check ===
bool resolve_dns(const char* hostname) {
  IPAddress ip;
  if (WiFi.hostByName(hostname, ip)) {
    Serial.printf("DNS resolved: %s -> %s\n", hostname, ip.toString().c_str());
    return true;
  } else {
    Serial.printf("DNS resolution failed for %s\n", hostname);
    return false;
  }
}

// === GitHub upload function ===
bool upload_to_github(const uint8_t* image_data, size_t image_len, const String& filename) {
  // Check WiFi connection and attempt to reconnect if needed
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, attempting to reconnect...");
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("WiFi reconnection failed, cannot upload");
      return false;
    }
  }

  // Check DNS resolution for GitHub API
  if (!resolve_dns("api.github.com")) {
    Serial.println("DNS resolution failed, cannot upload");
    return false;
  }

  // Convert to Base64
  String base64_image;
  base64_image.reserve((image_len * 4 / 3) + 100); // Reserve space for Base64
  base64_image = base64::encode(image_data, image_len);

  // Create JSON payload
  String url = "https://api.github.com/repos/" + String(GITHUB_OWNER) + "/" + 
              String(GITHUB_REPO) + "/contents/images/" + String(filename);
  String json_payload = "{\"message\": \"ESP32-CAM upload " + filename + "\", \"content\": \"" + base64_image + "\"}";

  WiFiClientSecure client;
  client.setInsecure(); // Temporary for debugging SSL issues
  HTTPClient http;
  if (!http.begin(client, url)) {
    Serial.println("HTTP client initialization failed");
    return false;
  }

  http.setTimeout(10000); // Increase timeout to 10 seconds
  http.addHeader("Authorization", "token " + String(GITHUB_TOKEN));
  http.addHeader("Content-Type", "application/json");
  http.addHeader("User-Agent", "ESP32-CAM");

  Serial.println("Sending PUT request to GitHub...");
  int httpCode = http.PUT(json_payload);
  String response = http.getString();

  if (httpCode > 0) {
    Serial.printf("HTTP response code: %d\n", httpCode);
    Serial.println("Response: " + response);
    if (httpCode == 201 || httpCode == 200) {
      Serial.println("Upload successful!");
      http.end();
      return true;
    }
  } else {
    Serial.printf("GitHub upload failed, code: %d\n", httpCode);
    Serial.println("Error: " + response);
  }

  http.end();
  return false;
}

// === Timestamped filename ===
String getTimestampFilename() {
  time_t now = time(nullptr);
  struct tm timeinfo;
  localtime_r(&now, &timeinfo);

  char buffer[64];
  strftime(buffer, sizeof(buffer), "%Y-%m-%d_%H-%M.jpg", &timeinfo);
  return String(buffer);
}

// === Find if current time matches any schedule ===
bool is_scheduled_now(struct tm timeinfo) {
  for (int i = 0; i < NUM_SCHEDULES; i++) {
    if (timeinfo.tm_hour == photo_schedule[i].hour &&
        timeinfo.tm_min == photo_schedule[i].minute) {
      return true;
    }
  }
  return false;
}

// === Find next schedule in seconds ===
int get_seconds_until_next_schedule(struct tm current_time) {
  for (int i = 0; i < NUM_SCHEDULES; i++) {
    int sched_hour = photo_schedule[i].hour;
    int sched_min = photo_schedule[i].minute;
    if ((current_time.tm_hour < sched_hour) ||
        (current_time.tm_hour == sched_hour && current_time.tm_min < sched_min)) {
      int diff_hours = sched_hour - current_time.tm_hour;
      int diff_mins = sched_min - current_time.tm_min;
      return diff_hours * 3600 + diff_mins * 60;
    }
  }
  // No more times today, pick first tomorrow
  int tomorrow_hour = photo_schedule[0].hour;
  int tomorrow_min = photo_schedule[0].minute;
  int remaining_today = (23 - current_time.tm_hour) * 3600 + (59 - current_time.tm_min) * 60;
  int next_day_offset = tomorrow_hour * 3600 + tomorrow_min * 60;
  return remaining_today + 60 + next_day_offset;
}

// === Deep Sleep ===
void go_to_sleep_until_next_schedule(int sleep_seconds) {
  Serial.printf("Going to deep sleep for %d seconds...\n", sleep_seconds);
  esp_sleep_enable_timer_wakeup((uint64_t)sleep_seconds * 1000000ULL);
  esp_camera_deinit(); // Deinitialize camera before sleep
  esp_deep_sleep_start();
}