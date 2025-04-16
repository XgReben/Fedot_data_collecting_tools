#include <Arduino.h>
#include <FunctionalInterrupt.h>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include "FS.h"
#include <LittleFS.h>
#include "esp_attr.h"
#include <Wifi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>

#if __has_include("ArduinoJson.h")
#include <ArduinoJson.h>
#include <AsyncJson.h>
#include <AsyncMessagePack.h>
#endif

using namespace std;

#define DATA_PORT 80
#define FORMAT_LITTLEFS_IF_FAILED true
#define SIMULTANIOUS_STIMULATION false
#define TESTING false
// PIN FOP POWER BOARD SETUP
#define TRIGGER 4    // SEND PULSE TO ELECTRODE
#define VSPI_SS1 5   // POWER SPI SS1
#define VSPI_SS0 13  // POWER SPI SS0
#define VSPI_CLK 18  // POWER SPI CLK
#define VSPI_MISO 19 // POWER SPI MISO
#define VSPI_MOSI 23 // POWER SPI MOSI
// ANALOG MUX ADDRES
#define A_2 17
#define A_0 15
#define A_1 16

#ifdef CONFIG_IDF_TARGET_ESP32
#define CUR_SENSE_0 32 // CURRENT SENSOR ADC PIN
#define MIC_SENSE_0 33 // MIC SENSOR ADC PIN
#define VIBRO_SENSE_0 35   // LEGASY


// INTERFACE SETUP
#define BUTTON1 22 // MAIN BUTTON
#define BUTTON0 0  // SIDE BUTTON
#define LED0 14    // CENTER LED
#define LED1 27    // RIGHT LED
#define LED2 26    // LEFT LED

// ADC DMA SETTINGS
#define CONVERSIONS_PER_PIN 1
#define ADC_CLK 240000
#define SENSE_RES 100 // sense resistor value
#define SAMPLE_SIZE 80000 //count of adc values for one sample

JsonDocument sensors_data_to_send;

uint8_t sense_r = SENSE_RES;

uint8_t adc_pins[] = {CUR_SENSE_0, MIC_SENSE_0, VIBRO_SENSE_0};
uint8_t adc_pins_count = sizeof(adc_pins) / sizeof(uint8_t);
adc_continuous_data_t *adc_bufer;
std::array<uint16_t,SAMPLE_SIZE> current_data_0;
std::array<uint16_t,SAMPLE_SIZE> mic_data_0;
std::array<uint16_t,SAMPLE_SIZE> vibro_data_0;
volatile bool adc_coversion_done = false;

void ARDUINO_ISR_ATTR adcComplete() {
  adc_coversion_done = true;
}

const char* ssid = "Wirenboard";
const char* password = "Wirenboard";
const char* mqttServer = "192.168.0.67";
const int mqttPort = 1883;
const char* mqttUser = "Fedot_collector_ADC";
const char* mqttPassword = "";

WiFiClient espClient;
PubSubClient client(espClient);

uint16_t LOG_COUNTER = 100; // numper of periods befor log will be recorded

int chip_id = 0;
std::string device_URL = "0";
uint8_t data_ready = false;
uint8_t status_timer = 0;    // waiting before shutdown counter
bool first_start = true;     // first start falag

// Set web server port number to 80
AsyncWebServer  server(DATA_PORT);

// Variable to store the HTTP request
String header;

// LiteFS USAGE print files in dirrectory
void listDir(fs::FS &fs, const char *dirname, uint8_t levels)
{
  Serial.printf("Listing directory: %s\r\n", dirname);

  File root = fs.open(dirname);
  if (!root)
  {
    Serial.println("- failed to open directory");
    return;
  }
  if (!root.isDirectory())
  {
    Serial.println(" - not a directory");
    return;
  }

  File file = root.openNextFile();
  while (file)
  {
    if (file.isDirectory())
    {
      Serial.print("  DIR : ");
      Serial.println(file.name());
      if (levels)
      {
        listDir(fs, file.path(), levels - 1);
      }
    }
    else
    {
      Serial.print("  FILE: ");
      Serial.print(file.name());
      Serial.print("\tSIZE: ");
      Serial.println(file.size());
    }
    file = root.openNextFile();
  }
}
// String splitter with delimets as std::string
std::vector<std::string> split(std::string stringToBeSplitted, std::string delimeter)
{
  std::vector<std::string> splittedString;
  int startIndex = 0;
  int endIndex = 0;
  while ((endIndex = stringToBeSplitted.find(delimeter, startIndex)) < stringToBeSplitted.size())
  {
    std::string val = stringToBeSplitted.substr(startIndex, endIndex - startIndex);
    splittedString.push_back(val);
    startIndex = endIndex + delimeter.size();
  }
  if (startIndex < stringToBeSplitted.size())
  {
    std::string val = stringToBeSplitted.substr(startIndex);
    splittedString.push_back(val);
  }
  return splittedString;
}

String generateHTML() {
  String html = R"rawliteral(
<!DOCTYPE html><html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FEDOT.INDUSTRIAL_ESP_DATA_COLLECTOR_MQTT</title>
  <style>
    html {font-family: Helvetica; display: inline-block; margin: 0px auto; text-align: center;}
    body {margin-top: 50px;} 
    h1 {color: #444444; margin: 50px auto 30px;} 
    h3 {color: #444444; margin-bottom: 50px;}
    .button {
      display: block; width: 80px; background-color: #3498db; border: none;
      color: white; padding: 13px 30px; text-decoration: none; font-size: 25px;
      margin: 0px auto 35px; cursor: pointer; border-radius: 4px;
    }
    .button-on {background-color: #3498db;}
    .button-on:active {background-color: #2980b9;}
    .button-off {background-color: #34495e;}
    .button-off:active {background-color: #2c3e50;}
    p {font-size: 14px; color: #888; margin-bottom: 10px;}
  </style>
</head>
<body>
  <h1>FEDOT SENSOR DATA</h1>
  <h3>Current: <span id="currentData">Loading...</span></h3>
  <h3>Mic: <span id="micData">Loading...</span></h3>
  <h3>Vibration: <span id="vibData">Loading...</span></h3>
  <script>
    function fetchData() {
      fetch('/get_data')
        .then(response => response.json())
        .then(data => {
          document.getElementById('currentData').textContent = data.current;
          document.getElementById('micData').textContent = data.mic;
          document.getElementById('vibData').textContent = data.vibration;
        });
    }
    setInterval(fetchData, 2000); // Fetch data every 2 seconds
  </script>
</body>
)rawliteral";
  return html;
}

void setup()
{
  Serial.begin(115200); // serial communication
  //SETUP WIFI AND WEB SERVER
  while (!Serial)
    delay(10);
  WiFi.begin(ssid, password);
  Serial.println("...................................");
  Serial.print("Connecting to WiFi.");
  while (WiFi.status() != WL_CONNECTED)
       {  delay(500);
          Serial.print(".") ;
       }
  Serial.println("Connected to the WiFi network");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  device_URL = WiFi.localIP() + "/" + DATA_PORT;
  
  //MQTT BROCKER setup
  client.setServer(mqttServer, mqttPort);
  while (!client.connected())
  { Serial.println("Connecting to MQTT...");
    if (client.connect("ESP32Client", mqttUser, mqttPassword ))
        Serial.println("connected");
    else
      { Serial.print("failed with state ");
        Serial.print(client.state());
        delay(2000);
      }
  }
  // INITIAL MQTT MESSAGE  
  client.publish( "URL", device_URL);
  client.publish( "Data", String(data_ready).c_str());
  
  //WEB server setup
    // Route handlers
    server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
      Serial.println("GPIO4 Status: OFF | GPIO5 Status: OFF");
      request->send(200, "text/html", generateHTML());
    });
  
    server.on("/get_data", HTTP_GET, [](AsyncWebServerRequest *request){
      if (sensors_data_to_send.isNull()) {
        request->send(500, "text/plain", "No data is ready");
      } else {
        AsyncMessagePackResponse *response = new AsyncMessagePackResponse();
        JsonObject root = sensors_data_to_send.as<JsonObject>();
        serializeJson(root, *response);
        // Use mutex/semaphore for thread-safe flag update (if in a multi-threaded environment)
        data_ready = 0; 
        client.publish("Data", String(data_ready).c_str());
        request->send(response);
      }
    });
    server.onNotFound([](AsyncWebServerRequest *request){
      request->send(404, "text/plain", "Not found");
    });
  
    server.begin();
    Serial.println("HTTP async server started");

  
  
  // start ADC
  analogContinuousSetWidth(12);
  if (sense_r == 100)
  {
    analogContinuousSetAtten(ADC_11db); // SET ATTENUATION TO MAX FOR 100 OHM sense resistor
  }
  else
  {
    analogContinuousSetAtten(ADC_0db); // DISABLE ATTENUATION FOR <5 OHM sense resiostor
  }
  analogContinuous(adc_pins, adc_pins_count, CONVERSIONS_PER_PIN, ADC_CLK,  &adcComplete);
  Serial.println("ADC TEST__1");
  analogContinuousStart();
  Serial.println("ADC TEST__2");
  delay(10);

  Serial.println("Starting . . . . .");
  selftest(); // test internal system
  status_timer = 0;
  first_start = true;
  Serial.println("Setup done.");
}
// STATE MACHINE loops
void loop()
{
uint8_t data_counter = 0;
while (data_counter < SAMPLE_SIZE)
{
  if (adc_coversion_done) {
    // Set ISR flag back to false
    adc_coversion_done = false;
    // Read data from ADC
    if (analogContinuousRead(&result, 0)) {
      // Optional: Stop ADC Continuous conversions to have more time to process (print) the data
        if (result != nullptr) {
          current_data_0.push_back(result[0].avg_read_raw);
          mic_data_0.push_back(result[1].avg_read_raw);
          vibro_data_0.push_back(result[2].avg_read_raw);
        }
      }
    } 
    else {
      Serial.println("Error occurred during reading data. Set Core Debug Level to error or lower for more information.");
    }
    data_counter++;
}

//Convert message buffer to json
JsonArray json_current = sensors_data_to_send["current"].to<JsonArray>();
for (uint16_t measurement : current_data_0) {
  json_current.add(measurement);
}
JsonArray json_mic = sensors_data_to_send["mic"].to<JsonArray>();
for (uint16_t measurement : mic_data_0) {
  json_mic.add(measurement);
}
JsonArray json_vibro = sensors_data_to_send["vibro"].to<JsonArray>();
for (uint16_t measurement : vibro_data_0) {
  json_vibro.add(measurement);
}
JsonObject meta = sensors_data_to_send.createNestedObject("metadata");
meta["sample_rate"] = ADC_CLK; // 240000
meta["resolution"] = 12;
meta["timestamp"] = getISOTimestamp(); // Функция для времени
meta["device_id"] = String(ESP.getEfuseMac(), HEX);


data_ready = 1;
client.publish( "Data", String(data_ready).c_str());
}

void system_halt() {
  Serial.println("System halted due to fatal error. Restart the device.");
  while (true) {} // Infinite loop
}

// DO SELF TEST
void selftest()
{
  Serial.println("Start self testing........");
  chip_id = ESP.getEfuseMac();
  Serial.printf("DEVICE MAC: ");
  Serial.println(chip_id);
  // Check battery status
  analogContinuousStop();
  // Check file system
  if (!LittleFS.begin(FORMAT_LITTLEFS_IF_FAILED))
  {
    Serial.println("LittleFS Mount Failed");
    system_halt();
  }

  listDir(LittleFS, "/", 0); // print list of files

  File file = LittleFS.open("/config.txt", "r"); // check configuration file
  if (!file)
  {
    Serial.println("Failed to open config for reading");
    system_halt();
  }
  String Config_line = file.readString();
  Serial.println("CURRENT CONFIG: ");
  Serial.println(Config_line);
  std::string data(Config_line.c_str(), Config_line.length()); // convert data to std::string
  std::vector<std::string> splittedData = split(data, "\n");   // split data by lines
  min_pwm = atoi(splittedData[1].c_str());
  Serial.print("MIN POWER: ");
  Serial.println(min_pwm);
  max_pwm = atoi(splittedData[2].c_str());
  Serial.print("MAX POWER: ");
  Serial.println(max_pwm);
  sense_r = atoi(splittedData[4].c_str());
  Serial.print("SENSE RESISTANCE: ");
  Serial.println(sense_r);
  file.close();
  analogContinuousStart();
  Serial.println("SELF CHECK FINISHED");
}
