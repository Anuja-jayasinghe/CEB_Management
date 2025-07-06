# ESP32-CAM Security System

A simple security camera system using ESP32-CAM that automatically captures images during working hours and uploads them to a private GitHub repository.

## Features

- 📸 Automatic image capture during configured hours
- 🔒 Secure upload to private GitHub repository
- 🔋 Power-efficient with deep sleep mode
- 🕒 Configurable working hours and photo intervals
- 📊 Image quality settings
- 🌐 WiFi connectivity

## Project Structure

```
esp32-cam-security/
├── esp32/
│   ├── main/
│   │   ├── cam_http_client.ino    # Main ESP32-CAM code
│   │   ├── secrets.h              # Your credentials (not in repo)
│   │   └── secrets.example.h      # Example configuration
│   └── platformio.ini             # PlatformIO configuration
├── .gitignore                     # Security file exclusions
└── README.md                      # This file
```

## Hardware Requirements

- ESP32-CAM (AI-Thinker model)
- MicroSD card (optional, for local storage)
- 5V power supply
- FTDI programmer (for initial setup)

## Setup Instructions

### 1. GitHub Repository Setup

1. Create a new **private** repository on GitHub for storing images
2. Generate a Personal Access Token:
   - Go to GitHub → Settings → Developer settings → Personal access tokens
   - Generate new token with `repo` permissions
   - Copy the token (starts with `ghp_`)

### 2. ESP32-CAM Configuration

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/esp32-cam-security.git
   cd esp32-cam-security
   ```

2. Copy the example configuration:
   ```bash
   cp esp32/main/secrets.example.h esp32/main/secrets.h
   ```

3. Edit `esp32/main/secrets.h` with your credentials:
   ```cpp
   const char* WIFI_SSID = "YourWiFiName";
   const char* WIFI_PASSWORD = "YourWiFiPassword";
   const char* GITHUB_TOKEN = "ghp_your_token_here";
   const char* GITHUB_OWNER = "your-github-username";
   const char* GITHUB_REPO = "your-repo-name";
   ```

4. Configure camera settings:
   ```cpp
   const int WORK_START_HOUR = 7;    // 7:00 AM
   const int WORK_END_HOUR = 18;     // 6:00 PM
   const int PHOTO_INTERVAL = 3;     // Every 3 hours
   ```

### 3. Programming the ESP32-CAM

#### Using Arduino IDE:
1. Install ESP32 board support
2. Install required libraries:
   - ArduinoJson
   - Base64
3. Select "AI Thinker ESP32-CAM" board
4. Connect FTDI programmer and upload

#### Using PlatformIO:
1. Open project in VS Code with PlatformIO
2. Build and upload:
   ```bash
   pio run --target upload
   ```

### 4. Deployment

1. Power the ESP32-CAM with 5V supply
2. The device will:
   - Connect to WiFi
   - Sync time with NTP server
   - Take photos during working hours
   - Upload images to GitHub
   - Enter deep sleep between captures

## Configuration Options

### Working Hours
- `WORK_START_HOUR`: Start of surveillance (24-hour format)
- `WORK_END_HOUR`: End of surveillance (24-hour format)
- `PHOTO_INTERVAL`: Hours between photos during working time

### Image Quality
- `JPEG_QUALITY`: 1-63 (lower = better quality, larger file)
- `FRAME_SIZE`: Image resolution (FRAMESIZE_UXGA = 1600x1200)

### Time Zone
- `GMT_OFFSET_SEC`: Timezone offset in seconds (Sri Lanka: +5:30 = 19800)
- `NTP_SERVER`: Time server for synchronization

## Security Features

- ✅ Credentials stored in `secrets.h` (excluded from git)
- ✅ HTTPS upload to GitHub API
- ✅ Personal access token authentication
- ✅ Private repository storage
- ✅ Deep sleep mode reduces power consumption

## Troubleshooting

### WiFi Connection Issues
- Check SSID and password in `secrets.h`
- Ensure 2.4GHz WiFi (ESP32 doesn't support 5GHz)
- Check signal strength

### Camera Initialization Failed
- Verify camera connections
- Check power supply (5V recommended)
- Ensure camera model is set correctly

### Upload Failures
- Verify GitHub token has correct permissions
- Check repository name and owner
- Ensure internet connectivity

### Time Sync Issues
- Check NTP server accessibility
- Verify timezone settings
- Ensure stable internet connection

## Power Consumption

- Active (taking photo): ~160mA
- Deep sleep: ~10µA
- Battery life estimate: 2-3 months with 18650 battery

## Image Storage

Images are stored in your GitHub repository under the `images/` folder with timestamp filenames:
- Format: `photo_YYYYMMDD_HHMMSS.jpg`
- Example: `photo_20240125_143022.jpg`

## License

This project is open source. Use at your own risk.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

If you encounter issues, please:
1. Check the troubleshooting section
2. Review serial monitor output
3. Open an issue with details

---

**⚠️ Important Security Notes:**
- Never commit `secrets.h` to version control
- Use a private repository for image storage
- Regularly rotate your GitHub tokens
- Consider using environment variables for production deployments