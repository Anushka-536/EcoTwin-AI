#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ---------------------------------------------------------
// EcoTwin-AI ESP32 + DHT22 + LED integration
// Sends REAL ambient temperature + humidity only.
// All other solar values come from demo_simulation.py.
// LEDs follow the worse of: twin health status OR
// telemetry thresholds (module temperature / vibration).
// ---------------------------------------------------------

const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_IP = "YOUR_LAPTOP_IP";

const int SERVER_PORT = 5000;
const int FACILITY_ID = 1;

// DHT22
#define DHT_PIN 4
#define DHT_TYPE DHT22
DHT dht(DHT_PIN, DHT_TYPE);

// Status LEDs
const int GREEN_LED = 25;
const int YELLOW_LED = 26;
const int RED_LED = 27;

const unsigned long SEND_INTERVAL_MS = 5000;
unsigned long lastSend = 0;

String makeUrl(String path) {
  return String("http://") + SERVER_IP + ":" +
         String(SERVER_PORT) + path;
}

void setLeds(bool green, bool yellow, bool red) {
  digitalWrite(GREEN_LED, green ? HIGH : LOW);
  digitalWrite(YELLOW_LED, yellow ? HIGH : LOW);
  digitalWrite(RED_LED, red ? HIGH : LOW);
}

void showFallbackStatus(float temperature) {
  // Fallback only: prototype demo thresholds, not solar safety limits.
  if (temperature < 35.0) {
    setLeds(true, false, false);
    Serial.println("LED status: GREEN (temperature fallback)");
  } else if (temperature < 45.0) {
    setLeds(false, true, false);
    Serial.println("LED status: YELLOW (temperature fallback)");
  } else {
    setLeds(false, false, true);
    Serial.println("LED status: RED (temperature fallback)");
  }
}

// Sends the REAL DHT22 reading to the backend mailbox endpoint
bool sendTelemetry(float ambientTemperature, float humidity) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected; reading not sent.");
    return false;
  }

  HTTPClient http;
  http.begin(makeUrl("/api/telemetry/esp32"));
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);

  StaticJsonDocument<128> doc;
  doc["ambient_temperature"] = ambientTemperature;  // REAL (DHT22)
  doc["humidity"] = humidity;                       // REAL (DHT22)

  String body;
  serializeJson(doc, body);

  Serial.println();
  Serial.println("Sending ESP32 reading:");
  Serial.println(body);

  int code = http.POST(body);
  Serial.printf("ESP32 reading HTTP status: %d\n", code);

  http.end();
  return code >= 200 && code < 300;
}

// Returns 0 = normal, 1 = warning, 2 = critical, -1 = unavailable.
// Demo thresholds based on module temperature and vibration.
int levelFromTelemetry() {
  HTTPClient http;
  http.begin(makeUrl(
    "/api/telemetry/latest?facility_id=" + String(FACILITY_ID)
  ));
  http.setTimeout(5000);

  int code = http.GET();
  String response = http.getString();
  http.end();

  if (code < 200 || code >= 300) return -1;

  StaticJsonDocument<1536> doc;
  if (deserializeJson(doc, response)) return -1;

  float moduleTemp =
    doc["telemetry"]["module_temperature"]["value"] | 0.0;
  float vibration =
    doc["telemetry"]["vibration"]["value"] | 0.0;

  Serial.printf("Module temp: %.1f C, vibration: %.2f mm/s\n",
                moduleTemp, vibration);

  if (moduleTemp >= 80.0 || vibration >= 4.0) return 2;
  if (moduleTemp >= 65.0 || vibration >= 2.5) return 1;
  return 0;
}

// Reads the twin status + telemetry and sets the LEDs
bool updateLedsFromDigitalTwin() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  http.begin(makeUrl(
    "/api/digital-twin?facility_id=" + String(FACILITY_ID)
  ));
  http.setTimeout(5000);

  int code = http.GET();
  String response = http.getString();
  http.end();

  if (code < 200 || code >= 300) {
    Serial.printf("Digital Twin status request failed: HTTP %d\n", code);
    return false;
  }

  StaticJsonDocument<4096> doc;
  if (deserializeJson(doc, response)) {
    Serial.println("Could not parse Digital Twin JSON.");
    return false;
  }

  const char* status = doc["digital_twin"]["health"]["status"] | "";
  String healthStatus(status);
  healthStatus.toLowerCase();

  Serial.print("Digital Twin health status: ");
  Serial.println(status);

  // Level from the twin's own status
  int twinLevel = 0;
  if (healthStatus.indexOf("critical") >= 0 ||
      healthStatus.indexOf("high") >= 0 ||
      healthStatus.indexOf("fail") >= 0) {
    twinLevel = 2;
  } else if (healthStatus.indexOf("warn") >= 0 ||
             healthStatus.indexOf("degrad") >= 0 ||
             healthStatus.indexOf("moderate") >= 0 ||
             healthStatus.indexOf("medium") >= 0) {
    twinLevel = 1;
  }

    // The twin now includes the rule layer, so use its status directly
  int level = twinLevel;

  if (level == 2) {
    setLeds(false, false, true);
    Serial.println("LED: RED");
  } else if (level == 1) {
    setLeds(false, true, false);
    Serial.println("LED: YELLOW");
  } else {
    setLeds(true, false, false);
    Serial.println("LED: GREEN");
  }

  return true;
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to Wi-Fi");
  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("Wi-Fi connected.");
    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("Backend: ");
    Serial.println(makeUrl("/api/telemetry/esp32"));
  } else {
    Serial.println("Wi-Fi connection failed. Check credentials.");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(GREEN_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  setLeds(false, false, false);

  dht.begin();
  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();

    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();

    if (isnan(temperature) || isnan(humidity)) {
      Serial.println("DHT22 read failed. Check wiring and sensor.");
      return;
    }

    Serial.printf(
      "\nDHT22 measurement: %.1f C, %.1f%% RH\n",
      temperature, humidity
    );

    bool sent = sendTelemetry(temperature, humidity);

    if (sent) {
      bool twinStatusRead = updateLedsFromDigitalTwin();

      if (!twinStatusRead) {
        Serial.println(
          "Twin status unavailable; using local temperature fallback."
        );
        showFallbackStatus(temperature);
      }
    } else {
      Serial.println("Reading not sent; using local fallback.");
      showFallbackStatus(temperature);
    }
  }
}
